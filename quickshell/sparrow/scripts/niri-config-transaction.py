#!/usr/bin/env python3
"""Safely validate and commit Sparrow-owned Niri config fragments.

The public interface accepts one JSON object on stdin:
    {"fragment": "generated-colors", "content": "...KDL..."}

Callers cannot supply paths or commands. Fragment identifiers are an explicit
allowlist; add an identifier here only when Sparrow takes ownership of that
specific generated file.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Callable, Optional


MANAGED_FRAGMENTS = {
    "generated-colors": Path("sparrow/generated-colors.kdl"),
    "user-appearance": Path("sparrow/user-appearance.kdl"),
    "display-outputs": Path("sparrow/display-outputs.kdl"),
    "display-binds": Path("sparrow/display-binds.kdl"),
    "user-input": Path("sparrow/user-input.kdl"),
    "user-binds": Path("sparrow/user-binds.kdl"),
}
BACKUP_PREFIX = "niri-transaction-"
BACKUP_LIMIT = 20
MAX_CONTENT_BYTES = 1024 * 1024
DISPLAY_CONFIRM_SECONDS = 15
INCLUDE_RE = re.compile(r'^\s*include\s+(?:optional=true\s+)?(?P<path>r#+".*?"#+|"(?:\\.|[^"\\])*")\s*(?://.*)?$')
KDL_STRING_RE = r'"(?:\\.|[^"\\])*"'

# Stable IDs and shipped key assignments for the curated Keybinds surface.
# Actions are copied from the tracked/default KDL bind file, never supplied by
# the UI. User input is only a map from these IDs to a validated key chord.
KEYBIND_DEFAULTS = {
    "kitty": "Super+T", "thunar": "Super+E", "firefox": "Super+F",
    "lock": "Super+L", "screenshot": "Super+Shift+S", "recorder": "Super+D",
    "launcher": "Super+Space", "wallpaper-picker": "Super+C", "wallpaper-next": "Super+B",
    "close": "Super+Q", "floating": "Super+W",
    "volume-up": "XF86AudioRaiseVolume", "volume-down": "XF86AudioLowerVolume",
    "volume-mute": "XF86AudioMute", "mic-mute": "XF86AudioMicMute",
    "brightness-up": "XF86MonBrightnessUp", "brightness-down": "XF86MonBrightnessDown",
    **{f"workspace-{i}": f"Super+{i}" for i in range(1, 10)},
    **{f"move-workspace-{i}": f"Super+Shift+{i}" for i in range(1, 10)},
    "overview": "Super+O", "focus-left": "Super+Left", "focus-down": "Super+Down",
    "focus-up": "Super+Up", "focus-right": "Super+Right",
    "move-column-left": "Super+Shift+Left", "move-column-right": "Super+Shift+Right",
    "move-window-down": "Super+Shift+Down", "move-window-up": "Super+Shift+Up",
    "consume-left": "Super+Ctrl+Left", "consume-right": "Super+Ctrl+Right",
    "tabbed": "Super+Tab", "focus-floating-tiling": "Super+V",
    "column-width": "Super+R", "window-height": "Super+Shift+R",
    "reset-height": "Super+Ctrl+R", "maximize-column": "Super+M",
    "fullscreen": "Super+Shift+F", "inhibit": "Super+Escape",
}
CHORD_RE = re.compile(r"^(?:(?:Super|Ctrl|Alt|Shift)\+)*(?:[A-Za-z][A-Za-z0-9_-]*|[0-9])$")
NIRI_NAMED_KEYS = {
    "Space", "Left", "Right", "Up", "Down", "Tab", "Escape", "Return", "Enter",
    "Insert", "Delete", "Home", "End", "PageUp", "PageDown", "period", "comma",
    "slash", "backslash", "semicolon", "apostrophe", "grave", "bracketleft",
    "bracketright", "minus", "equal", "Print",
}


def _niri_config_path(env: dict[str, str]) -> Path:
    override = env.get("NIRI_CONFIG", "")
    if override:
        return Path(override).expanduser().absolute()
    config_home = Path(env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")).expanduser()
    return (config_home / "niri" / "config.kdl").absolute()


def _state_root(env: dict[str, str]) -> Path:
    state_home = Path(env.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")).expanduser()
    return state_home / "sparrow-shell"


def _decode_kdl_string(value: str) -> str:
    if value.startswith("r"):
        first_quote = value.find('"')
        hashes = value[1:first_quote]
        suffix = '"' + hashes
        if first_quote < 0 or not value.endswith(suffix):
            raise ValueError("unsupported raw KDL include path")
        return value[first_quote + 1 : -len(suffix)]
    decoded = json.loads(value)
    if not isinstance(decoded, str):
        raise ValueError("include path is not a string")
    return decoded


def _include_paths(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot inspect include file {path}: {exc}") from exc
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/-"):
            continue
        match = INCLUDE_RE.match(line)
        if match:
            result.append(_decode_kdl_string(match.group("path")))
    return result


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _atomic_replace(target: Path, content: bytes, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.sparrow-", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
        dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _backup_fragment(
    backup_root: Path,
    fragment_id: str,
    relative_path: Path,
    old_content: Optional[bytes],
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = backup_root / f"{BACKUP_PREFIX}{stamp}"
    try:
        backup_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        if old_content is not None:
            payload_path = backup_dir / relative_path.name
            with payload_path.open("xb") as stream:
                stream.write(old_content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(payload_path, 0o600)
        manifest = {
            "schemaVersion": 1,
            "fragmentId": fragment_id,
            "relativePath": relative_path.as_posix(),
            "timestampUtc": datetime.now(timezone.utc).isoformat(),
            "previousFileExisted": old_content is not None,
            "previousSha256": hashlib.sha256(old_content).hexdigest() if old_content is not None else None,
        }
        with (backup_dir / "manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        dir_fd = os.open(backup_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return backup_dir
    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def _prune_backups(backup_root: Path) -> None:
    candidates = sorted(
        (p for p in backup_root.iterdir()
         if p.is_dir() and not p.is_symlink() and p.name.startswith(BACKUP_PREFIX)
         and (p / "manifest.json").is_file()),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in candidates[BACKUP_LIMIT:]:
        shutil.rmtree(old)


def _safe_user_input(content: str) -> bool:
    """Accept only Sparrow's deliberately small, complete input-settings KDL."""
    stack: list[str] = []
    seen: set[tuple[str, str]] = set()
    allowed_blocks = {
        "root": {"keyboard", "touchpad", "mouse", "touch", "tablet"},
        "keyboard": {"xkb"}, "xkb": set(), "touchpad": set(), "mouse": set(),
        "touch": set(), "tablet": set(),
    }
    allowed_props = {
        "root": {"focus-follows-mouse"},
        "keyboard": {"numlock", "repeat-rate", "repeat-delay"},
        "xkb": {"layout"},
        "touchpad": {"tap", "natural-scroll", "dwt", "accel-speed", "accel-profile"},
        "mouse": {"natural-scroll", "left-handed", "accel-speed", "accel-profile"},
        "touch": {"map-to-output"},
        "tablet": {"map-to-output", "map-to-focused-output"},
    }
    values: dict[str, str] = {}
    root_count = header_count = 0
    block_re = re.compile(r"^(\s*)(input|keyboard|xkb|touchpad|mouse|touch|tablet) \{$")
    property_re = re.compile(r'^(\s*)([a-z][a-z0-9-]*)(?: ("(?:[^"\\]|\\.)*"|-?[0-9]+(?:\.[0-9]+)?))?$')

    for line in content.splitlines():
        if line == "// Generated by Sparrow Input; do not edit.":
            header_count += 1
            continue
        if not line:
            continue
        closing = re.fullmatch(r"( *)}", line)
        if closing:
            if not stack:
                return False
            if closing.group(1) != "    " * (len(stack) - 1):
                return False
            stack.pop()
            continue
        block = block_re.fullmatch(line)
        if block:
            indent, name = block.groups()
            parent = stack[-1] if stack else "root"
            parent = "root" if parent == "input" else parent
            if name == "input":
                if stack or root_count:
                    return False
                root_count += 1
                stack.append("input")
                continue
            if not stack or name not in allowed_blocks.get(parent, set()):
                return False
            if indent != "    " * len(stack):
                return False
            key = (parent, name)
            if key in seen:
                return False
            seen.add(key)
            stack.append(name)
            continue
        prop = property_re.fullmatch(line)
        if not prop or not stack or stack[0] != "input":
            return False
        indent, name, value = prop.groups()
        context = "root" if stack[-1] == "input" else stack[-1]
        if indent != "    " * len(stack) or name not in allowed_props.get(context, set()):
            return False
        key = (context, name)
        if key in seen:
            return False
        seen.add(key)
        values[f"{context}.{name}"] = value or ""

    if header_count != 1 or root_count != 1 or stack or ("root", "keyboard") not in seen:
        return False
    if ("keyboard", "xkb") in seen:
        layout = values.get("xkb.layout", "")
        if layout and not re.fullmatch(r'"[A-Za-z0-9_,+-]{1,64}"', layout):
            return False
    for prop, low, high in (("keyboard.repeat-rate", 1, 100), ("keyboard.repeat-delay", 1, 5000)):
        value = values.get(prop)
        if value and (not value.isdigit() or not low <= int(value) <= high):
            return False
    for context in ("touchpad", "mouse"):
        speed = values.get(f"{context}.accel-speed")
        if speed:
            try:
                number = float(speed)
            except ValueError:
                return False
            if not -1 <= number <= 1:
                return False
        profile = values.get(f"{context}.accel-profile")
        if profile and profile not in {'"adaptive"', '"flat"'}:
            return False
    for prop in ("touch.map-to-output", "tablet.map-to-output"):
        value = values.get(prop)
        if value and not re.fullmatch(r'"(?:[^"\\]|\\.){1,256}"', value):
            return False
    if ("tablet", "map-to-focused-output") in seen and ("tablet", "map-to-output") in seen:
        return False
    return True


def _parse_user_bind_overrides(content: str) -> Optional[dict[str, str]]:
    """Accept only a JSON mapping of curated action IDs to Niri key chords."""
    try:
        values = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(values, dict) or len(values) > len(KEYBIND_DEFAULTS):
        return None
    result: dict[str, str] = {}
    seen: set[str] = set()
    for bind_id, chord in values.items():
        if bind_id not in KEYBIND_DEFAULTS or not isinstance(chord, str) or not _valid_key_chord(chord):
            return None
        if chord == KEYBIND_DEFAULTS[bind_id] or chord in seen:
            return None
        seen.add(chord)
        result[bind_id] = chord
    return result


def _valid_key_chord(chord: str) -> bool:
    if not CHORD_RE.fullmatch(chord):
        return False
    parts = chord.split("+")
    modifiers, key = parts[:-1], parts[-1]
    order = {"Super": 0, "Ctrl": 1, "Alt": 2, "Shift": 3}
    return (
        bool(modifiers)
        and len(set(modifiers)) == len(modifiers)
        and all(modifier in order for modifier in modifiers)
        and modifiers == sorted(modifiers, key=order.__getitem__)
        and (len(key) == 1 or key in NIRI_NAMED_KEYS or key.startswith("XF86")
             or key.startswith("F") and key[1:].isdigit())
    )


class ConfigTransaction:
    """Filesystem transaction implementation; callers pass IDs, never paths."""

    def __init__(
        self,
        config_path: Path,
        state_root: Path,
        command_runner: Optional[Callable[..., subprocess.CompletedProcess[str]]] = None,
        rollback_scheduler: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config_path = config_path
        self.config_root = config_path.parent
        self.state_root = state_root
        self.command_runner = command_runner or subprocess.run
        self.rollback_scheduler = rollback_scheduler

    def _run(self, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return self.command_runner(args, text=True, capture_output=True, timeout=timeout, check=False)

    def _render_user_binds(self, content: str) -> str:
        overrides = _parse_user_bind_overrides(content)
        if overrides is None:
            raise ValueError("shortcut overrides are malformed or outside Sparrow's curated actions")
        default_file = self.config_root / "sparrow" / "binds.kdl"
        if not default_file.is_file() or default_file.is_symlink():
            raise ValueError("Sparrow default binds.kdl is missing or unsafe")
        source_lines = default_file.read_text(encoding="utf-8").splitlines()
        actions: dict[str, str] = {}
        for bind_id, default_chord in KEYBIND_DEFAULTS.items():
            matches = [line.strip() for line in source_lines
                       if line.strip().startswith(default_chord + " ") and "{" in line and line.rstrip().endswith("}")]
            if len(matches) != 1:
                raise ValueError(f"default shortcut {bind_id} must have exactly one bind in Sparrow binds.kdl")
            actions[bind_id] = matches[0][len(default_chord):].strip()

        occupied = {chord: bind_id for bind_id, chord in KEYBIND_DEFAULTS.items() if bind_id not in overrides}
        display_chords: set[str] = set()
        display_file = self.config_root / "sparrow" / "display-binds.kdl"
        if display_file.is_file() and not display_file.is_symlink():
            for line in display_file.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^\s*(Super(?:\+Shift)?\+F[0-9]+)\s", line)
                if match:
                    display_chords.add(match.group(1))
        for bind_id, chord in overrides.items():
            if chord in occupied:
                raise ValueError(f"{chord} is already assigned to {occupied[chord]}")
            if chord in display_chords:
                raise ValueError(f"{chord} is reserved for a generated display shortcut")
            occupied[chord] = bind_id

        lines = ["// Generated by Sparrow Keybinds; do not edit.", "binds {"]
        for bind_id in KEYBIND_DEFAULTS:
            chord = overrides.get(bind_id)
            if not chord:
                continue
            default_chord = KEYBIND_DEFAULTS[bind_id]
            lines.append(f"    // override: {bind_id} = {chord}")
            lines.append(f"    {chord} {actions[bind_id]}")
            lines.append(f'    {default_chord} {{ spawn "true"; }}')
        lines.append("}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _safe_fragment_payload(fragment_id: str, content: str) -> bool:
        """Constrain generated KDL and the Keybinds UI's ID/chord payload."""
        if fragment_id == "user-appearance":
            return _safe_user_appearance(content)
        if fragment_id == "display-outputs":
            return _safe_display_outputs(content)
        if fragment_id == "display-binds":
            return _safe_display_binds(content)
        if fragment_id == "user-input":
            return _safe_user_input(content)
        if fragment_id == "user-binds":
            return _parse_user_bind_overrides(content) is not None
        if fragment_id != "generated-colors":
            return False
        lines = content.splitlines()
        if len(lines) < 5 or lines[:3] != [
            "// Generated by Sparrow wallpaper palette; do not edit.",
            "layout {", "    border {",
        ]:
            return False
        if not (re.fullmatch(r'        active-color "[^"\\\r\n]*"', lines[3])
                and re.fullmatch(r'        inactive-color "[^"\\\r\n]*"', lines[4])):
            return False
        tail = lines[5:]
        # The old border-only form remains valid. Missing closing braces are
        # passed to Niri validation, which reports the actual syntax error.
        if tail in ([], ["    }"]):
            return True
        if tail[:2] != ["    }", "}"]:
            return False
        if len(tail) == 2:
            return True
        return (len(tail) == 8 and tail[2:4] == ["recent-windows {", "    highlight {"]
                and re.fullmatch(r'        active-color "[^"\\\r\n]*"', tail[4]) is not None
                and re.fullmatch(r'        urgent-color "[^"\\\r\n]*"', tail[5]) is not None
                and tail[6:] == ["    }", "}"])

    def _schedule_rollback(self, token: str) -> None:
        """Start a detached failsafe so a lost Quickshell cannot strand a bad mode."""
        if self.rollback_scheduler is not None:
            self.rollback_scheduler(token)
            return
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--rollback-after", token],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    def _validate_candidate(self, fragment_rel: Path, candidate: bytes) -> tuple[Optional[Path], Optional[str], Optional[str]]:
        stage: Optional[Path] = None
        if not self.config_path.is_file() or self.config_path.is_symlink():
            return None, "staging_failed", f"Niri root config is missing or is a symlink: {self.config_path}"
        try:
            root_real = self.config_root.resolve(strict=True)
            config_real = self.config_path.resolve(strict=True)
            if config_real.parent != root_real:
                return None, "staging_failed", "Niri root config must be directly inside its config directory"
            target = self.config_root / fragment_rel
            if not _is_relative_to(target.absolute(), self.config_root.absolute()):
                return None, "staging_failed", "managed fragment resolves outside the Niri config directory"

            # Fail closed on symlinked config trees: relative includes through a
            # symlink can resolve differently in a staged copy.
            for current, dirs, files in os.walk(self.config_root, followlinks=False):
                base = Path(current)
                for name in dirs + files:
                    item = base / name
                    if item.is_symlink():
                        return None, "staging_failed", f"cannot stage a Niri config tree containing symlinks: {item}"

            included: set[Path] = set()
            visited: set[Path] = set()
            pending = [config_real]
            while pending:
                source = pending.pop()
                if source in visited:
                    continue
                visited.add(source)
                for include in _include_paths(source):
                    include_path = Path(include)
                    if include_path.is_absolute():
                        resolved = include_path.resolve(strict=False)
                        if resolved == target.resolve(strict=False):
                            return None, "staging_failed", "managed fragment is included through an absolute path; staging cannot safely substitute it"
                    else:
                        resolved = (source.parent / include_path).resolve(strict=False)
                        if not _is_relative_to(resolved, root_real):
                            return None, "staging_failed", f"relative include escapes the Niri config directory: {include}"
                    included.add(resolved)
                    if resolved.is_file():
                        pending.append(resolved)

            target_real = target.resolve(strict=False)
            if target_real not in included:
                return None, "staging_failed", f"managed fragment {fragment_rel.as_posix()} is not included by the active config"

            staging_parent = self.state_root / "niri-config-transactions" / "staging"
            staging_parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix="candidate-", dir=staging_parent))
            stage_root = stage / "niri"
            shutil.copytree(self.config_root, stage_root, symlinks=False)
            stage_target = stage_root / fragment_rel
            stage_target.parent.mkdir(parents=True, exist_ok=True)
            stage_target.write_bytes(candidate)
            stage_target.chmod(0o600)
            stage_config = stage_root / self.config_path.name

            result = self._run(["niri", "validate", "-c", str(stage_config)], timeout=20)
            if result.returncode != 0:
                details = (result.stderr or result.stdout or "Niri validation failed").strip()
                shutil.rmtree(stage, ignore_errors=True)
                return None, "validation_failed", details
            return stage, None, None
        except subprocess.TimeoutExpired:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            return None, "validation_failed", "Niri validation timed out"
        except Exception as exc:  # report staging/copy/inspection failures uniformly
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            return None, "staging_failed", str(exc)

    def _restore_from_journal(self, journal_path: Path, backup_root: Path) -> tuple[bool, str]:
        """Recover a transaction interrupted after its durable journal was written."""
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            fragment_id = journal.get("fragmentId")
            backup_name = journal.get("backupDirectory")
            if fragment_id not in MANAGED_FRAGMENTS or not isinstance(backup_name, str):
                return False, "pending transaction journal is malformed"
            if Path(backup_name).name != backup_name or not backup_name.startswith(BACKUP_PREFIX):
                return False, "pending transaction journal contains an unsafe backup reference"
            backup_dir = backup_root / backup_name
            manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("fragmentId") != fragment_id or manifest.get("relativePath") != MANAGED_FRAGMENTS[fragment_id].as_posix():
                return False, "pending transaction backup does not match its managed fragment"
            target = self.config_root / MANAGED_FRAGMENTS[fragment_id]
            if manifest.get("previousFileExisted"):
                old_content = (backup_dir / MANAGED_FRAGMENTS[fragment_id].name).read_bytes()
                if hashlib.sha256(old_content).hexdigest() != manifest.get("previousSha256"):
                    return False, "pending transaction backup checksum does not match"
                mode = stat.S_IMODE(target.stat().st_mode) if target.exists() and not target.is_symlink() else 0o600
                _atomic_replace(target, old_content, mode)
            else:
                target.unlink(missing_ok=True)
                dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            reload_result = self._run(["niri", "msg", "action", "load-config-file"], timeout=15)
            if reload_result.returncode != 0:
                return False, (reload_result.stderr or reload_result.stdout or "Niri reload failed during crash recovery").strip()
            journal_path.unlink()
            return True, "previous fragment restored after interrupted transaction"
        except Exception as exc:
            return False, f"cannot recover interrupted transaction: {exc}"

    def transact(self, fragment_id: str, content: str, confirm: bool = False) -> dict[str, object]:
        if fragment_id not in MANAGED_FRAGMENTS:
            return {"status": "invalid_fragment", "message": "fragment is not Sparrow-managed"}
        if not isinstance(content, str) or "\x00" in content:
            return {"status": "invalid_request", "message": "fragment content must be NUL-free text"}
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_CONTENT_BYTES:
            return {"status": "invalid_request", "message": "fragment exceeds the 1 MiB safety limit"}
        if not self._safe_fragment_payload(fragment_id, content):
            return {"status": "invalid_content", "message": f"{fragment_id} content is outside Sparrow's restricted generated syntax"}
        if fragment_id == "user-binds":
            try:
                content = self._render_user_binds(content)
            except (OSError, UnicodeError, ValueError) as exc:
                return {"status": "invalid_content", "message": str(exc)}
            encoded = content.encode("utf-8")
            if len(encoded) > MAX_CONTENT_BYTES:
                return {"status": "invalid_request", "message": "rendered shortcut fragment exceeds the 1 MiB safety limit"}

        fragment_rel = MANAGED_FRAGMENTS[fragment_id]
        target = self.config_root / fragment_rel
        lock_root = self.state_root / "niri-config-transactions"
        backup_root = self.state_root / "backups"
        stage: Optional[Path] = None
        try:
            lock_root.mkdir(parents=True, mode=0o700, exist_ok=True)
            backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
            lock_fd = os.open(lock_root / "transaction.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except OSError as exc:
            return {"status": "staging_failed", "message": f"cannot initialize transaction state: {exc}"}

        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                journal_path = lock_root / "pending-transaction.json"
                if journal_path.exists():
                    try:
                        pending = json.loads(journal_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        pending = {}
                    if pending.get("phase") == "confirmation_pending":
                        if float(pending.get("expiresAt", 0)) > time.time():
                            return {"status": "confirmation_pending", "message": "another display change is awaiting confirmation", "changed": False}
                    recovered, recovery_message = self._restore_from_journal(journal_path, backup_root)
                    if not recovered:
                        return {"status": "recovery_failed", "message": recovery_message, "changed": False}

                if target.is_symlink():
                    return {"status": "write_failed", "message": "managed fragment must not be a symlink"}
                old_stat = target.stat() if target.exists() else None
                if old_stat is not None and (not stat.S_ISREG(old_stat.st_mode) or old_stat.st_uid != os.getuid()):
                    return {"status": "write_failed", "message": "managed fragment must be a regular file owned by the current user"}
                old_content = target.read_bytes() if old_stat is not None else None
                if old_content == encoded:
                    return {"status": "success", "message": "fragment is unchanged", "changed": False}

                stage, validation_status, validation_error = self._validate_candidate(fragment_rel, encoded)
                if validation_error:
                    return {"status": validation_status or "staging_failed", "message": validation_error, "changed": False}

                try:
                    backup_dir = _backup_fragment(backup_root, fragment_id, fragment_rel, old_content)
                except OSError as exc:
                    return {"status": "backup_failed", "message": str(exc), "changed": False}

                journal = {
                    "schemaVersion": 1,
                    "fragmentId": fragment_id,
                    "backupDirectory": backup_dir.name,
                    "phase": "commit_pending",
                }
                journal_path = lock_root / "pending-transaction.json"
                try:
                    _atomic_replace(journal_path, (json.dumps(journal) + "\n").encode("utf-8"), 0o600)
                except OSError as exc:
                    return {"status": "write_failed", "message": f"cannot persist recovery journal: {exc}", "backupPath": str(backup_dir), "changed": False}

                mode = stat.S_IMODE(old_stat.st_mode) if old_stat is not None else 0o600
                try:
                    _atomic_replace(target, encoded, mode)
                except OSError as exc:
                    recovered, recovery_message = self._restore_from_journal(journal_path, backup_root)
                    return {"status": "write_failed", "message": f"{exc}; recovery: {recovery_message}", "backupPath": str(backup_dir), "changed": False, "rollbackSucceeded": recovered}

                try:
                    reload_result = self._run(["niri", "msg", "action", "load-config-file"], timeout=15)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    reload_result = None
                    reload_error = str(exc)
                else:
                    reload_error = (reload_result.stderr or reload_result.stdout or "Niri rejected the config reload").strip()

                if reload_result is None or reload_result.returncode != 0:
                    try:
                        if old_content is None:
                            target.unlink(missing_ok=True)
                            dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                            try:
                                os.fsync(dir_fd)
                            finally:
                                os.close(dir_fd)
                        else:
                            _atomic_replace(target, old_content, mode)
                        rollback = self._run(["niri", "msg", "action", "load-config-file"], timeout=15)
                        rollback_ok = rollback.returncode == 0
                        if rollback_ok:
                            journal_path.unlink(missing_ok=True)
                    except Exception as exc:
                        rollback_ok = False
                        reload_error += f"; rollback error: {exc}"
                    return {
                        "status": "reload_failed",
                        "message": reload_error,
                        "rollbackSucceeded": rollback_ok,
                        "backupPath": str(backup_dir),
                        "changed": False,
                    }

                if confirm:
                    token = secrets.token_urlsafe(24)
                    journal = {
                        "schemaVersion": 1,
                        "fragmentId": fragment_id,
                        "backupDirectory": backup_dir.name,
                        "phase": "confirmation_pending",
                        "token": token,
                        "expiresAt": time.time() + DISPLAY_CONFIRM_SECONDS,
                    }
                    try:
                        _atomic_replace(journal_path, (json.dumps(journal) + "\n").encode("utf-8"), 0o600)
                        self._schedule_rollback(token)
                    except Exception as exc:
                        try:
                            if old_content is None:
                                target.unlink(missing_ok=True)
                                dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                                try:
                                    os.fsync(dir_fd)
                                finally:
                                    os.close(dir_fd)
                            else:
                                _atomic_replace(target, old_content, mode)
                            rollback = self._run(["niri", "msg", "action", "load-config-file"], timeout=15)
                            rollback_ok = rollback.returncode == 0
                            if rollback_ok:
                                journal_path.unlink(missing_ok=True)
                        except Exception:
                            rollback_ok = False
                        return {
                            "status": "watchdog_failed",
                            "message": f"could not arm display rollback timer: {exc}",
                            "rollbackSucceeded": rollback_ok,
                            "backupPath": str(backup_dir),
                            "changed": False,
                        }
                    return {
                        "status": "confirmation_pending",
                        "message": "validated and reloaded; keep or revert before the display safety timer expires",
                        "confirmationToken": token,
                        "timeoutSeconds": DISPLAY_CONFIRM_SECONDS,
                        "backupPath": str(backup_dir),
                        "changed": True,
                    }

                try:
                    journal_path.unlink(missing_ok=True)
                    _prune_backups(backup_root)
                except OSError:
                    # A retention cleanup problem must not turn a successful,
                    # validated active config into a rollback condition.
                    pass
                return {
                    "status": "success",
                    "message": "validated, committed, and reloaded",
                    "backupPath": str(backup_dir),
                    "changed": True,
                }
            finally:
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)
        finally:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            os.close(lock_fd)

    def resolve_confirmation(self, token: str, rollback: bool) -> dict[str, object]:
        lock_root = self.state_root / "niri-config-transactions"
        backup_root = self.state_root / "backups"
        try:
            lock_root.mkdir(parents=True, mode=0o700, exist_ok=True)
            lock_fd = os.open(lock_root / "transaction.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except OSError as exc:
            return {"status": "staging_failed", "message": str(exc)}
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            journal_path = lock_root / "pending-transaction.json"
            try:
                journal = json.loads(journal_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                if rollback:
                    return {"status": "already_resolved", "message": "display preview was already resolved"}
                return {"status": "no_pending_confirmation", "message": str(exc)}
            if journal.get("phase") != "confirmation_pending" or not secrets.compare_digest(str(journal.get("token", "")), str(token)):
                return {"status": "invalid_confirmation", "message": "confirmation token does not match the pending display change"}
            if not rollback and float(journal.get("expiresAt", 0)) <= time.time():
                restored, message = self._restore_from_journal(journal_path, backup_root)
                return {"status": "rolled_back" if restored else "rollback_failed", "message": message, "rollbackSucceeded": restored}
            if rollback:
                restored, message = self._restore_from_journal(journal_path, backup_root)
                return {"status": "rolled_back" if restored else "rollback_failed", "message": message, "rollbackSucceeded": restored}
            journal_path.unlink(missing_ok=True)
            _prune_backups(backup_root)
            return {"status": "confirmed", "message": "display configuration kept"}
        finally:
            os.close(lock_fd)

    def rollback_after_delay(self, token: str) -> dict[str, object]:
        lock_root = self.state_root / "niri-config-transactions"
        journal_path = lock_root / "pending-transaction.json"
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "already_resolved", "message": "display preview was already resolved"}
        deadline = float(journal.get("expiresAt", 0))
        if deadline > time.time():
            time.sleep(deadline - time.time())
        return self.resolve_confirmation(token, rollback=True)


def _safe_display_outputs(content: str) -> bool:
    lines = content.splitlines()
    if not lines or lines[0] != "// Generated by Sparrow Display settings; do not edit.":
        return False
    string = KDL_STRING_RE
    open_re = re.compile(r"output (" + string + r") \{")
    mode_re = re.compile(r"    mode (" + string + r")")
    transform_re = re.compile(r"    transform (" + string + r")")
    scale_re = re.compile(r"    scale (0\.[1-9][0-9]*|[1-9](?:\.[0-9]+)?|10(?:\.0+)?)")
    position_re = re.compile(r"    position x=-?[0-9]+ y=-?[0-9]+")
    allowed_transforms = {"normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"}
    focus_at_startup_count = 0
    index = 1
    while index < len(lines):
        if lines[index] == "":
            index += 1
            continue
        match = open_re.fullmatch(lines[index])
        if not match:
            return False
        try:
            identity = json.loads(match.group(1))
        except json.JSONDecodeError:
            return False
        if not isinstance(identity, str) or not identity or any(ord(ch) < 32 for ch in identity):
            return False
        index += 1
        body = []
        while index < len(lines) and lines[index] != "}":
            body.append(lines[index])
            index += 1
        if index >= len(lines):
            return False
        index += 1
        if body and body[0] == "    off":
            body = body[1:]
        has_focus_at_startup = len(body) == 5 and body[3] == "    focus-at-startup"
        position_index = 4 if has_focus_at_startup else 3
        if len(body) not in (4, 5) or (len(body) == 5 and not has_focus_at_startup) or not mode_re.fullmatch(body[0]) or not scale_re.fullmatch(body[1]) or not transform_re.fullmatch(body[2]) or not position_re.fullmatch(body[position_index]):
            return False
        if has_focus_at_startup:
            focus_at_startup_count += 1
            if focus_at_startup_count > 1:
                return False
        try:
            mode = json.loads(mode_re.fullmatch(body[0]).group(1))
            transform = json.loads(transform_re.fullmatch(body[2]).group(1))
        except (AttributeError, json.JSONDecodeError):
            return False
        if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*@[0-9]+\.[0-9]{3}", mode) or transform not in allowed_transforms:
            return False
    return True


def _safe_user_appearance(content: str) -> bool:
    """Allow only Look's bounded Niri appearance settings, never arbitrary KDL."""
    pattern = re.compile(
        r"\A// Generated by Sparrow Look; do not edit\.\n"
        r"layout \{\n"
        r"    gaps (?P<gaps>0|[1-9][0-9]*(?:\.[0-9]+)?)\n"
        r"    struts \{\n"
        r"        left (?P<left_strut>0)\n"
        r"        right (?P<right_strut>0)\n"
        r"        top (?P<top_strut>-?(?:0|[1-9][0-9]*(?:\.[0-9]+)?))\n"
        r"        bottom (?P<bottom_strut>0)\n"
        r"    \}\n"
        r"    border \{\n"
        r"        width (?P<border>0|[1-9][0-9]*)\n"
        r"    \}\n"
        r"    shadow \{\n"
        r"        (?P<shadow>on|off)\n"
        r"        softness (?P<softness>0|[1-9][0-9]*)\n"
        r"    \}\n"
        r"\}\n"
        r"window-rule \{\n"
        r"    geometry-corner-radius (?P<radius>0|[1-9][0-9]*)\n"
        r"    clip-to-geometry true\n"
        r"\}\n"
        r"animations \{\n"
        r"    (?:(?P<off>off)|slowdown (?P<slowdown>0\.75|1\.0|1\.5))\n"
        r"\}\n"
        r"\Z"
    )
    match = pattern.fullmatch(content)
    if not match:
        return False
    values = {key: int(match.group(key)) for key in ("border", "softness", "radius")}
    gaps = float(match.group("gaps"))
    return (
        0 <= gaps <= 40
        and int(match.group("left_strut")) == 0
        and int(match.group("right_strut")) == 0
        and abs(float(match.group("top_strut")) + gaps) < 0.000001
        and int(match.group("bottom_strut")) == 0
        and 0 <= values["border"] <= 8
        and 0 <= values["softness"] <= 50
        and 0 <= values["radius"] <= 30
    )


def _safe_display_binds(content: str) -> bool:
    lines = content.splitlines()
    if len(lines) < 3 or lines[0] != "// Generated by Sparrow from the current Niri output arrangement." or lines[1] != "binds {" or lines[-1] != "}":
        return False
    string = KDL_STRING_RE
    metadata_re = re.compile(r"    // sparrow-monitor-number (" + string + r") ([1-9][0-9]*)")
    focus_re = re.compile(r"    Super\+F([1-9][0-9]*) hotkey-overlay-title=(" + string + r") \{ focus-monitor (" + string + r"); \}")
    move_re = re.compile(r"    Super\+Shift\+F([1-9][0-9]*) hotkey-overlay-title=(" + string + r") \{ move-window-to-monitor (" + string + r"); \}")
    identities: set[str] = set()
    assigned_numbers: set[int] = set()
    index = 2
    while index < len(lines) - 1 and lines[index].startswith("    // sparrow-monitor-number "):
        match = metadata_re.fullmatch(lines[index])
        if not match:
            return False
        try:
            identity = json.loads(match.group(1))
        except json.JSONDecodeError:
            return False
        number = int(match.group(2))
        if not isinstance(identity, str) or not identity or any(ord(ch) < 32 for ch in identity):
            return False
        if identity in identities or number in assigned_numbers:
            return False
        identities.add(identity)
        assigned_numbers.add(number)
        index += 1

    bind_lines = lines[index:-1]
    if len(bind_lines) % 2:
        return False
    bound_numbers: set[int] = set()
    for offset in range(0, len(bind_lines), 2):
        focus = focus_re.fullmatch(bind_lines[offset])
        move = move_re.fullmatch(bind_lines[offset + 1])
        if not focus or not move or focus.group(1) != move.group(1) or focus.group(3) != move.group(3):
            return False
        try:
            focus_title, focus_output = json.loads(focus.group(2)), json.loads(focus.group(3))
            move_title, move_output = json.loads(move.group(2)), json.loads(move.group(3))
        except json.JSONDecodeError:
            return False
        number = int(focus.group(1))
        if number in bound_numbers:
            return False
        bound_numbers.add(number)
        if any(not isinstance(value, str) or not value or any(ord(ch) < 32 for ch in value)
               for value in (focus_title, focus_output, move_title, move_output)):
            return False
    return True


def main() -> int:
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--rollback-after":
            token = sys.argv[2]
            env = dict(os.environ)
            transaction = ConfigTransaction(_niri_config_path(env), _state_root(env))
            transaction.rollback_after_delay(token)
            return 0
        line = sys.stdin.readline(MAX_CONTENT_BYTES * 2 + 4096)
        if not line:
            raise ValueError("expected one JSON request on stdin")
        request = json.loads(line)
        env = dict(os.environ)
        transaction = ConfigTransaction(_niri_config_path(env), _state_root(env))
        if isinstance(request, dict) and set(request) in ({"fragment", "content"}, {"fragment", "content", "confirm"}):
            confirm = request.get("confirm", False)
            if not isinstance(confirm, bool):
                raise ValueError("confirm must be a boolean")
            result = transaction.transact(request["fragment"], request["content"], confirm)
        elif isinstance(request, dict) and set(request) == {"operation", "token"} and request["operation"] in {"confirm", "rollback"}:
            result = transaction.resolve_confirmation(request["token"], request["operation"] == "rollback")
        else:
            raise ValueError("invalid transaction request")
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] in {"success", "confirmed", "rolled_back"} else 1
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"status": "invalid_request", "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
