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
    "display-outputs": Path("sparrow/display-outputs.kdl"),
    "display-binds": Path("sparrow/display-binds.kdl"),
}
BACKUP_PREFIX = "niri-transaction-"
BACKUP_LIMIT = 20
MAX_CONTENT_BYTES = 1024 * 1024
DISPLAY_CONFIRM_SECONDS = 15
INCLUDE_RE = re.compile(r'^\s*include\s+(?:optional=true\s+)?(?P<path>r#+".*?"#+|"(?:\\.|[^"\\])*")\s*(?://.*)?$')
COLOR_LINE_RE = re.compile(r'        (?:active|inactive)-color "[^"\\\r\n]*"\Z')
KDL_STRING_RE = r'"(?:\\.|[^"\\])*"'


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

    @staticmethod
    def _safe_fragment_payload(fragment_id: str, content: str) -> bool:
        """Constrain each generated fragment to its documented Niri subset."""
        if fragment_id == "display-outputs":
            return _safe_display_outputs(content)
        if fragment_id == "display-binds":
            return _safe_display_binds(content)
        if fragment_id != "generated-colors":
            return False
        allowed = {
            "// Generated by Sparrow wallpaper palette; do not edit.",
            "layout {",
            "    border {",
            "    }",
            "}",
        }
        counts = {"layout {": 0, "    border {": 0, "active": 0, "inactive": 0,
                  "    }": 0, "}": 0, "// Generated by Sparrow wallpaper palette; do not edit.": 0}
        for line in content.splitlines():
            if line in allowed:
                counts[line] += 1
                continue
            if COLOR_LINE_RE.fullmatch(line):
                kind = "active" if line.startswith("        active-color ") else "inactive"
                counts[kind] += 1
                continue
            if line:
                return False
        # Permit missing closing braces so Niri's real parser can diagnose
        # malformed KDL in the staging test/validation path. All directives
        # and values remain constrained to the two color properties.
        return (
            counts["// Generated by Sparrow wallpaper palette; do not edit."] == 1
            and counts["layout {"] == 1
            and counts["    border {"] == 1
            and counts["active"] == 1
            and counts["inactive"] == 1
            and counts["    }"] <= 1
            and counts["}"] <= 1
        )

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
