#!/usr/bin/env python3
"""Conservative user-level installer for Sparrow Shell (Arch/CachyOS)."""

from __future__ import annotations

import argparse
import configparser
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
MARKER_START = "// >>> BEGIN SPARROW INSTALLER INCLUDES"
MARKER_END = "// <<< END SPARROW INSTALLER INCLUDES"
SCHEMA = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path).as_posix().encode()
        digest.update(rel + b"\0")
        if item.is_symlink():
            digest.update(b"L" + os.readlink(item).encode())
        elif item.is_file():
            digest.update(b"F" + bytes.fromhex(sha256_file(item)))
    return digest.hexdigest()


def atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def is_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def snapshot(path: Path, backup_root: Path, index: int) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"exists": False}
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        return {"exists": True, "type": "symlink", "target": os.readlink(path)}
    target = backup_root / f"{index:04d}-{path.name}"
    if path.is_dir():
        shutil.copytree(path, target, symlinks=True)
        return {"exists": True, "type": "directory", "backup": str(target)}
    shutil.copy2(path, target)
    return {"exists": True, "type": "file", "backup": str(target)}


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def restore_snapshot(path: Path, saved: dict) -> None:
    remove_path(path)
    if not saved.get("exists"):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    kind = saved["type"]
    if kind == "symlink":
        path.symlink_to(saved["target"])
    elif kind == "directory":
        shutil.copytree(saved["backup"], path, symlinks=True)
    elif kind == "file":
        shutil.copy2(saved["backup"], path)


@dataclass
class XdgPaths:
    home: Path
    config: Path
    data: Path
    state: Path
    cache: Path

    @classmethod
    def from_environment(cls) -> "XdgPaths":
        home = Path.home()
        return cls(
            home=home,
            config=Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")),
            data=Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")),
            state=Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")),
            cache=Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")),
        )


class SparrowInstaller:
    def __init__(
        self,
        paths: XdgPaths | None = None,
        repo: Path = ROOT,
        *,
        dry_run: bool = False,
        testing: bool = False,
        confirm: Callable[[str, bool], bool] | None = None,
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        output: Callable[[str], None] = print,
    ) -> None:
        self.paths = paths or XdgPaths.from_environment()
        self.repo = repo
        self.dry_run = dry_run
        self.testing = testing
        self.confirm = confirm or self._confirm
        self.run = run
        self.output = output
        self.state_root = self.paths.state / "sparrow-shell" / "installer"
        self.manifest_path = self.state_root / "manifest.json"
        self.old = self._read_manifest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.backup_root = self.state_root / "backups" / f"{stamp}-{os.getpid()}"
        self.snapshots: dict[str, dict] = {}
        self.managed: dict[str, dict] = dict(self.old.get("managed", {}))
        self.changed: list[str] = []
        self.conflicts: list[str] = []
        self.replace_approved: dict[str, bool] = {}
        self.enabled_before: dict[str, bool] = {}
        self.enabled_by_sparrow: set[str] = set(self.old.get("enabled_by_sparrow", []))
        self._installed_package_cache: set[str] | None = None

    def _confirm(self, prompt: str, default: bool = False) -> bool:
        if not sys.stdin.isatty():
            self.output("Cannot ask for consent without an interactive terminal; treating this prompt as declined.")
            return False
        suffix = "Y/n" if default else "y/N"
        answer = input(f"{prompt} [{suffix}] ").strip().lower()
        if not answer:
            return default
        return answer in {"y", "yes"}

    def _read_manifest(self) -> dict:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if data.get("schema") == SCHEMA else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def _command(self, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
        self.output("+ " + " ".join(args))
        if self.dry_run and self._is_mutating_command(args):
            self.output("  (dry-run: command not executed)")
            return subprocess.CompletedProcess(args, 0, "", "")
        return self.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)

    @staticmethod
    def _is_mutating_command(args: list[str]) -> bool:
        if args[:3] == ["sudo", "pacman", "-S"]:
            return True
        return len(args) >= 3 and args[:2] == ["systemctl", "--user"] and args[2] in {
            "enable", "disable", "stop", "daemon-reload"
        }

    def _snapshot_once(self, path: Path) -> dict:
        key = str(path)
        if key not in self.snapshots:
            local = self.backup_root / "transaction"
            current = snapshot(path, local, len(self.snapshots) + 1)
            self.snapshots[key] = current
        return self.snapshots[key]

    def _initial_snapshot(self, path: Path) -> dict:
        previous = self.managed.get(str(path))
        if previous and "initial" in previous:
            return previous["initial"]
        return snapshot(path, self.backup_root / "original", len(self.managed) + 1)

    def _ask_replace(self, path: Path) -> bool:
        if str(path) in self.replace_approved:
            return self.replace_approved[str(path)]
        self.conflicts.append(str(path))
        answer = self.confirm(
            f"Apply Sparrow's change to the existing user path {path}? A copy will be kept in {self.backup_root}.",
            False,
        )
        self.replace_approved[str(path)] = answer
        return answer

    def write_file(self, path: Path, content: bytes, *, mode: int = 0o644, role: str = "file") -> bool:
        desired_hash = hashlib.sha256(content).hexdigest()
        exists = path.exists() or path.is_symlink()
        current_hash = None
        if exists and path.is_file():
            try:
                current_hash = sha256_file(path)
            except OSError:
                pass
        old_record = self.managed.get(str(path))
        managed_unchanged = bool(old_record and current_hash == old_record.get("sha256"))
        if exists and current_hash == desired_hash and not path.is_symlink():
            record = old_record or {"initial": self._initial_snapshot(path)}
            record.update({"kind": "file", "sha256": desired_hash, "role": role, "mode": mode})
            self.managed[str(path)] = record
            return True
        if exists and not (current_hash == desired_hash and not path.is_symlink()) and not managed_unchanged and not self._ask_replace(path):
            self.output(f"Preserved existing file: {path}")
            return False
        self._snapshot_once(path)
        initial = self._initial_snapshot(path) if old_record is None else old_record.get("initial", {"exists": False})
        self.output(f"Install {role}: {path}")
        if not self.dry_run:
            atomic_write(path, content, mode)
        self.managed[str(path)] = {"kind": "file", "sha256": desired_hash, "role": role, "mode": mode, "initial": initial}
        self.changed.append(str(path))
        return True

    def write_tree(self, destination: Path, source: Path, *, role: str) -> bool:
        wanted_hash = tree_digest(source)
        old_record = self.managed.get(str(destination))
        exists = destination.exists() or destination.is_symlink()
        current_hash = None
        if destination.is_dir() and not destination.is_symlink():
            current_hash = tree_digest(destination)
        elif destination.is_symlink() and destination.resolve(strict=False).is_dir():
            current_hash = tree_digest(destination.resolve())
        managed_unchanged = bool(old_record and old_record.get("sha256") == current_hash)
        if exists and current_hash == wanted_hash and destination.is_dir() and not destination.is_symlink():
            self.managed[str(destination)] = old_record or {
                "kind": "directory", "sha256": wanted_hash, "role": role,
                "initial": self._initial_snapshot(destination),
            }
            self.managed[str(destination)].update({"kind": "directory", "sha256": wanted_hash, "role": role})
            return True
        if exists and not managed_unchanged and not self._ask_replace(destination):
            self.output(f"Preserved existing directory/link: {destination}")
            return False
        self._snapshot_once(destination)
        initial = self._initial_snapshot(destination) if old_record is None else old_record.get("initial", {"exists": False})
        self.output(f"Install {role}: {destination}")
        if not self.dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage = destination.with_name(f".{destination.name}.sparrow-stage-{os.getpid()}")
            remove_path(stage)
            shutil.copytree(source, stage, symlinks=True)
            remove_path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage, destination)
        self.managed[str(destination)] = {"kind": "directory", "sha256": wanted_hash, "role": role, "initial": initial}
        self.changed.append(str(destination))
        return True

    def write_symlink(self, path: Path, target: Path, *, role: str) -> bool:
        target_text = os.path.relpath(target, path.parent)
        old_record = self.managed.get(str(path))
        exists = path.exists() or path.is_symlink()
        if path.is_symlink() and os.readlink(path) == target_text:
            self.managed[str(path)] = old_record or {
                "kind": "symlink", "target": target_text, "role": role,
                "initial": self._initial_snapshot(path),
            }
            return True
        current_managed = bool(old_record and path.is_symlink() and os.readlink(path) == old_record.get("target"))
        if exists and not current_managed and not self._ask_replace(path):
            self.output(f"Preserved existing runtime entry: {path}")
            return False
        self._snapshot_once(path)
        initial = self._initial_snapshot(path) if old_record is None else old_record.get("initial", {"exists": False})
        self.output(f"Install {role}: {path} -> {target_text}")
        if not self.dry_run:
            remove_path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target_text)
        self.managed[str(path)] = {"kind": "symlink", "target": target_text, "role": role, "initial": initial}
        self.changed.append(str(path))
        return True

    def write_merged_file(self, path: Path, content: bytes, *, role: str, merge_role: str) -> bool:
        old_record = self.managed.get(str(path))
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        wanted = content.decode()
        if current == wanted:
            return True
        if merge_role == "portal" and path.is_file():
            route = self._portal_filechooser_route(current)
            previously_managed = bool(old_record and old_record.get("mergeRole") == "portal")
            if (route is not None and route != "gtk;") or (previously_managed and route != "gtk;"):
                if not self._ask_replace(path):
                    self.output(f"Preserved existing FileChooser portal choice: {path}")
                    return False
        if old_record and old_record.get("kind") == "merge":
            # The merge builder only changes Sparrow's marker/key; an edited or
            # malformed marker is never silently overwritten.
            if merge_role == "niri" and MARKER_START in current and MARKER_END not in current:
                raise RuntimeError(f"incomplete Sparrow merge marker in {path}")
        elif path.exists() and not self._ask_replace(path):
            self.output(f"Preserved existing file; skipped {role}: {path}")
            return False
        self._snapshot_once(path)
        initial = self._initial_snapshot(path) if old_record is None else old_record.get("initial", {"exists": False})
        digest = hashlib.sha256(content).hexdigest()
        if not self.dry_run:
            atomic_write(path, content)
        expected_merge = None
        if merge_role == "niri":
            match = re.search(
                r"(?m)^" + re.escape(MARKER_START) + r"\n.*?^" + re.escape(MARKER_END) + r"\n?",
                content.decode(), re.S,
            )
            expected_merge = match.group(0) if match else None
        self.managed[str(path)] = {
            "kind": "merge", "sha256": digest, "role": role, "initial": initial,
            "mergeRole": merge_role,
            "mergeExpected": expected_merge,
        }
        self.changed.append(str(path))
        return True

    def package_sets(self) -> dict:
        return json.loads((self.repo / "installer/package-sets.json").read_text(encoding="utf-8"))

    def installed_packages(self) -> set[str]:
        if self.testing:
            return set()
        if self._installed_package_cache is not None:
            return self._installed_package_cache
        result = self._command(["pacman", "-Qq"])
        if result.returncode:
            self._installed_package_cache = set()
        else:
            self._installed_package_cache = set(result.stdout.splitlines())
        return self._installed_package_cache

    def _install_package_list(self, packages: list[str], *, label: str, required: bool = False) -> bool:
        missing = sorted(set(packages) - self.installed_packages())
        if not missing:
            self.output(f"{label}: already present")
            return True
        self.output(f"{label} missing: " + " ".join(missing))
        if not self.confirm(f"Install these official repository packages with pacman?", required):
            return not required
        if self.testing:
            self.output("TEST: pacman install suppressed")
            return True
        if shutil.which("sudo") is None:
            self.output("sudo is unavailable. Install manually: sudo pacman -S --needed " + " ".join(missing))
            return not required
        result = self._command(["sudo", "pacman", "-S", "--needed", *missing])
        if result.returncode:
            self.output(result.stderr or f"Package installation failed ({result.returncode}).")
            return not required
        self._installed_package_cache = None
        return True

    def resolve_packages(self) -> bool:
        if self.testing:
            return True
        if not Path("/etc/os-release").is_file():
            self.output("Cannot identify the operating system; refusing an unverified Sparrow deployment.")
            return False
        os_release = Path("/etc/os-release").read_text(errors="replace").lower()
        if not any(name in os_release for name in ("id=arch", "id=cachyos", "id_like=arch")):
            self.output("Sparrow targets Arch/CachyOS; refusing to install on an unverified distribution.")
            return False
        sets = self.package_sets()
        installed = self.installed_packages()
        for group, names in (("Required", sets["required"]), ("Defaults", sets["defaults"]), *sets["optional"].items()):
            present = sorted(set(names) & installed)
            missing = sorted(set(names) - installed)
            self.output(f"Detected {group} packages present: " + (", ".join(present) if present else "none"))
            if missing:
                self.output(f"  not installed: {', '.join(missing)}")
        bibata_available = any(
            (root / "Bibata-Modern-Ice/index.theme").is_file()
            for root in (self.paths.data / "icons", Path("/usr/share/icons"))
        )
        for label, available in (
            ("mpvpaper", shutil.which("mpvpaper") is not None),
            ("Rishot", shutil.which("rishot") is not None),
            ("Bibata cursor theme", bibata_available),
        ):
            self.output(f"Detected {label}: {'available' if available else 'not found'}")
        if self.dry_run:
            self.output("AUR/upstream (manual only): " + "; ".join(f"{k}: {v}" for k, v in sets["aur_manual"].items()))
            return True
        if not self._install_package_list(sets["required"], label="Required Sparrow runtime", required=True):
            return False
        if self.confirm("Offer Sparrow's replaceable default apps and GTK/portal integration?", True):
            defaults = list(sets["defaults"])
            agent_exists = self.has_existing_polkit_agent()
            if not agent_exists:
                defaults.append(sets["polkit_agent"])
            if not self._install_package_list(defaults, label="Default desktop profile"):
                self.output("Continuing without some default apps; their bindings may need replacement.")
        optional = sets["optional"]
        if self.confirm("Choose optional feature packages (recording, video helpers, hardware integrations)?", False):
            for group, packages in optional.items():
                if self.confirm(f"  Include optional group '{group}' ({', '.join(packages)})?", False):
                    self._install_package_list(packages, label=f"Optional {group}")
        self.output("No AUR packages are installed by Sparrow. Manual AUR notes: " + "; ".join(f"{k}: {v}" for k, v in sets["aur_manual"].items()))
        return True

    def has_existing_polkit_agent(self) -> bool:
        known = re.compile(r"(lxqt-policykit-agent|polkit-gnome-authentication-agent-1|polkit-mate-authentication-agent-1|polkit-kde-authentication-agent-1|hyprpolkitagent)")
        try:
            result = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "args="], text=True, capture_output=True, check=False)
            if any(known.search(line) for line in result.stdout.splitlines()):
                return True
        except OSError:
            pass
        autostart = self.paths.config / "autostart"
        if autostart.is_dir():
            for item in autostart.glob("*.desktop"):
                try:
                    if known.search(item.read_text(encoding="utf-8", errors="replace")):
                        return True
                except OSError:
                    continue
        unit_roots = (
            self.paths.config / "systemd/user",
            Path("/etc/systemd/user"),
            Path("/usr/lib/systemd/user"),
        )
        for unit_root in unit_roots:
            if not unit_root.is_dir():
                continue
            for unit_file in unit_root.rglob("*.service"):
                if unit_file.name == "sparrow-polkit-agent.service":
                    continue
                try:
                    content = unit_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if re.search(r"(?im)^\s*ExecStart\s*=.*(?:polkit.*agent|agent.*polkit)", content):
                    return True
        return False

    def _runtime_source(self) -> Path:
        return self.repo / "quickshell/sparrow"

    def _runtime_stage_source(self) -> Path:
        stage = Path(tempfile.mkdtemp(prefix="sparrow-runtime-source-"))
        shutil.copytree(self._runtime_source(), stage / "sparrow", dirs_exist_ok=True)
        # Keep the installed runtime focused on run-time material, not local test entry points.
        for relative in ("minimal-test.qml", "lib/monitors.test.mjs", "scripts/test_wallcolors.py", "scripts/test_niri_config_transaction.py"):
            (stage / "sparrow" / relative).unlink(missing_ok=True)
        return stage / "sparrow"

    def _niri_expected_directives(self) -> list[str]:
        entry = (self.repo / "niri/sparrow/entry.kdl").read_text(encoding="utf-8")
        return [line.strip() for line in entry.splitlines() if line.strip().startswith("include ")]

    def _niri_directives_to_add(self, existing: str) -> list[str]:
        expected = self._niri_expected_directives()
        noncomment = [line.strip() for line in existing.splitlines() if line.strip() and not line.lstrip().startswith("//")]
        present = {line for line in noncomment if line.startswith("include ") and '"sparrow/' in line}
        entry_line = 'include "sparrow/entry.kdl"'
        if entry_line in present:
            return []
        if present:
            return [line for line in expected if line not in present]
        return ['include "sparrow/entry.kdl"']

    def merge_niri_root(self, existing: str) -> str:
        if MARKER_START in existing:
            start = existing.index(MARKER_START)
            end = existing.find(MARKER_END, start)
            if end < 0:
                raise RuntimeError("Niri installer marker is incomplete; refusing to edit the user's root config.")
            additions = self._niri_directives_to_add(existing)
            if not additions:
                return existing
            before_end = existing[:end]
            if before_end and not before_end.endswith("\n"):
                before_end += "\n"
            result = before_end + "\n".join(additions) + "\n" + existing[end:]
            return result
        directives = self._niri_directives_to_add(existing)
        if not directives:
            return existing
        block = f"{MARKER_START}\n" + "\n".join(directives) + f"\n{MARKER_END}\n"
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        return prefix + block

    def merge_portal(self, existing: str) -> str:
        key = "org.freedesktop.impl.portal.FileChooser"
        section_pattern = re.compile(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)")
        match = section_pattern.search(existing)
        if match:
            section = match.group(1)
            key_pattern = re.compile(rf"(?m)^{re.escape(key)}\s*=.*$")
            found = key_pattern.search(section)
            if found:
                if found.group(0).split("=", 1)[1].strip() == "gtk;":
                    return existing
                new_section = key_pattern.sub(f"{key}=gtk;", section, count=1)
                return existing[:match.start(1)] + new_section + existing[match.end(1):]
            line = f"{key}=gtk;\n"
            return existing[:match.end(1)] + line + existing[match.end(1):]
        tail = "" if not existing or existing.endswith("\n") else "\n"
        return existing + tail + f"\n[preferred]\n{key}=gtk;\n"

    def _planned_niri(self, *, validate: bool = True) -> tuple[Path, dict[Path, bytes], bytes]:
        niri_home = self.paths.config / "niri"
        planned: dict[Path, bytes] = {}
        if niri_home.exists():
            # Niri configs are small; preserve symlinks and host/user fragments for staged validation.
            with tempfile.TemporaryDirectory(prefix="sparrow-niri-stage-") as temp_name:
                stage_home = Path(temp_name) / "niri"
                shutil.copytree(niri_home, stage_home, symlinks=True)
                root = stage_home / "config.kdl"
                if not root.exists():
                    root.write_bytes((self.repo / "niri/config.kdl").read_bytes())
                else:
                    root.write_text(self.merge_niri_root(root.read_text(encoding="utf-8")), encoding="utf-8")
                for source in sorted((self.repo / "niri/sparrow").glob("*.kdl")):
                    dest = stage_home / "sparrow" / source.name
                    current = dest.read_bytes() if dest.exists() else None
                    managed = self.managed.get(str(niri_home / "sparrow" / source.name))
                    if current is not None and current != source.read_bytes() and not (managed and sha256_file(dest) == managed.get("sha256")):
                        # Ask before staging. The same decision is reused during deployment.
                        if self._ask_replace(niri_home / "sparrow" / source.name):
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(source.read_bytes())
                        else:
                            self.output(f"Staged validation keeps existing fragment: {dest}")
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(source.read_bytes())
                if validate:
                    result = self._command(["niri", "validate", "-c", str(root)])
                    if result.returncode:
                        raise RuntimeError("Staged Niri config validation failed: " + (result.stderr or result.stdout))
                else:
                    self.output("Niri is not installed yet; staged validation will run after the required package step.")
            root_path = niri_home / "config.kdl"
            if root_path.exists():
                root_text = self.merge_niri_root(root_path.read_text(encoding="utf-8"))
            else:
                root_text = (self.repo / "niri/config.kdl").read_text(encoding="utf-8")
        else:
            with tempfile.TemporaryDirectory(prefix="sparrow-niri-stage-") as temp_name:
                stage_home = Path(temp_name) / "niri"
                shutil.copytree(self.repo / "niri", stage_home)
                root = stage_home / "config.kdl"
                if validate:
                    result = self._command(["niri", "validate", "-c", str(root)])
                    if result.returncode:
                        raise RuntimeError("Repository Niri config validation failed: " + (result.stderr or result.stdout))
                else:
                    self.output("Niri is not installed yet; staged validation will run after the required package step.")
            root_path = niri_home / "config.kdl"
            root_text = (self.repo / "niri/config.kdl").read_text(encoding="utf-8")
        planned[root_path] = root_text.encode()
        return root_path, planned, root_text.encode()

    def _copy_tree_files(self, source: Path, destination: Path, role: str, *, preserve_generated: bool = False) -> None:
        for src in sorted(source.rglob("*")):
            if not src.is_file() or src.is_symlink():
                continue
            relative = src.relative_to(source)
            target = destination / relative
            if preserve_generated and target.exists() and str(target) not in self.managed:
                self.output(f"Preserved existing generated/user theme file: {target}")
                continue
            self.write_file(target, src.read_bytes(), mode=src.stat().st_mode & 0o777, role=role)

    def _unit_payload(self, source: Path) -> bytes:
        payload = source.read_bytes()
        conventional_config = self.paths.home / ".config"
        if self.paths.config == conventional_config:
            return payload
        try:
            relative = self.paths.config.relative_to(self.paths.home)
            unit_root = "%h/" + relative.as_posix()
        except ValueError:
            unit_root = str(self.paths.config)
        return payload.replace(b"%h/.config/", unit_root.encode() + b"/")

    def _build_file_plan(self, niri_plan: dict[Path, bytes]) -> list[tuple[Path, bytes, str, int]]:
        plan: list[tuple[Path, bytes, str, int]] = []
        for dest, data in niri_plan.items():
            plan.append((dest, data, "Niri root config", 0o644))
        for source in sorted((self.repo / "niri/sparrow").glob("*.kdl")):
            plan.append((self.paths.config / "niri/sparrow" / source.name, source.read_bytes(), "Niri Sparrow fragment", 0o644))
        for source in sorted((self.repo / "quickshell/sparrow/systemd").glob("*.service")):
            plan.append((self.paths.config / "systemd/user" / source.name, self._unit_payload(source), "Sparrow user service", 0o644))
        dropin = self.repo / "quickshell/sparrow/systemd/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf"
        plan.append((self.paths.config / "systemd/user/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf", dropin.read_bytes(), "GTK portal-only theme override", 0o644))
        user_files = [
            (self.repo / "kitty/kitty.conf", self.paths.config / "kitty/kitty.conf", "Kitty defaults"),
            (self.repo / "fish/config.fish", self.paths.config / "fish/config.fish", "Fish defaults"),
            (self.repo / "starship/starship.toml", self.paths.config / "starship.toml", "Starship defaults"),
            (self.repo / "environment.d/90-cursor.conf", self.paths.config / "environment.d/90-cursor.conf", "recommended cursor defaults"),
            (self.repo / "applications/sparrow-files.desktop", self.paths.data / "applications/sparrow-files.desktop", "Sparrow Files desktop entry"),
            (self.repo / "hyprlock/hyprlock.conf", self.paths.config / "sparrow/hyprlock.conf", "optional Hyprlock fallback config"),
        ]
        for source, destination, label in user_files:
            plan.append((destination, source.read_bytes(), label, source.stat().st_mode & 0o777))
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        original_portal = portal.read_text(encoding="utf-8") if portal.is_file() else ""
        merged_portal = self.merge_portal(original_portal)
        plan.append((portal, merged_portal.encode(), "FileChooser-only portal route merge", 0o644))
        return plan

    def _validate_units(self) -> None:
        unit_files = sorted((self.repo / "quickshell/sparrow/systemd").glob("*.service"))
        if shutil.which("systemd-analyze"):
            result = self._command(["systemd-analyze", "--user", "verify", *map(str, unit_files)])
            if result.returncode:
                raise RuntimeError("Sparrow systemd unit validation failed: " + (result.stderr or result.stdout))

    def _validate_sources(self) -> None:
        py_files = list((self.repo / "quickshell/sparrow/scripts").glob("*.py"))
        for path in py_files:
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            except SyntaxError as error:
                raise RuntimeError(f"Python syntax check failed: {path}: {error}") from error
        for path in (self.repo / "quickshell/sparrow/scripts").glob("*.sh"):
            result = self._command(["bash", "-n", str(path)])
            if result.returncode:
                raise RuntimeError(f"Shell syntax check failed: {path}")
        if shutil.which("qmllint"):
            qmls = [str(p) for p in (self.repo / "quickshell/sparrow").rglob("*.qml")]
            result = self._command(["qmllint", *qmls])
            if result.returncode:
                raise RuntimeError("QML lint failed: " + (result.stderr or result.stdout))
        else:
            self.output("qmllint not found; source QML lint will need the documented developer tool.")

    def _apply_plan(self, plan: list[tuple[Path, bytes, str, int]]) -> None:
        for path, content, role, mode in plan:
            if role == "Niri root config" and path.exists():
                old_text = path.read_text(encoding="utf-8")
                new_text = content.decode()
                if old_text != new_text and MARKER_START in new_text:
                    self.write_merged_file(path, content, role=role, merge_role="niri")
                else:
                    self.write_file(path, content, mode=mode, role=role)
            elif role == "FileChooser-only portal route merge":
                self.write_merged_file(path, content, role=role, merge_role="portal")
            else:
                self.write_file(path, content, mode=mode, role=role)

    def _save_manifest(self) -> None:
        if self.dry_run:
            return
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "schema": SCHEMA,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "managed": self.managed,
            "last_backup": str(self.backup_root),
            "changed": self.changed,
            "enabled_by_sparrow": sorted(self.enabled_by_sparrow),
        }
        atomic_write(self.manifest_path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(), 0o600)

    def _rollback(self) -> None:
        newly_enabled = sorted(self.enabled_by_sparrow - set(self.old.get("enabled_by_sparrow", [])))
        if newly_enabled and not self.testing and not self.dry_run:
            try:
                self._command(["systemctl", "--user", "disable", *newly_enabled])
            except OSError as error:
                self.output(f"Rollback warning: could not undo user-unit enablement: {error}")
        for key, saved in reversed(list(self.snapshots.items())):
            restore_snapshot(Path(key), saved)
        if newly_enabled and not self.testing and not self.dry_run:
            self._command(["systemctl", "--user", "daemon-reload"])

    def install(self) -> int:
        try:
            self._validate_sources()
            self._validate_units()
            niri_was_installed = shutil.which("niri") is not None
            _, niri_plan, _ = self._planned_niri(validate=niri_was_installed)
            plan = self._build_file_plan(niri_plan)
            self.output("\nSparrow install plan:")
            self.output(f"  Runtime copy: {self.paths.data / 'sparrow-shell/runtime'}")
            self.output(f"  Stable Quickshell entry: {self.paths.config / 'quickshell/sparrow'}")
            for path, _, role, _ in plan:
                self.output(f"  {role}: {path}")
            self.output("  Existing user state, wallpapers, generated palettes, caches, and monitor layout: preserve")
            existing_niri = self.paths.config / "niri/config.kdl"
            if existing_niri.exists():
                candidate = next(data for path, data in niri_plan.items() if path == existing_niri)
                root_changes = candidate.decode() != existing_niri.read_text(encoding="utf-8")
                if root_changes and self.dry_run:
                    self.output("  Niri root: would append/update only Sparrow's marked include block.")
                elif root_changes and not self._ask_replace(existing_niri):
                    self.output("Stopped without changing any Sparrow or Niri files.")
                    return 2
                if root_changes and not self.dry_run and os.environ.get("XDG_CURRENT_DESKTOP", "").lower() == "niri":
                    if not self.confirm("Niri watches its config: applying the validated include merge will update the current session. Continue?", False):
                        self.output("Stopped before changing Niri or Sparrow files.")
                        return 2
            if self.dry_run:
                if not self.resolve_packages():
                    return 2
                self.output("Dry run complete; no files, packages, services, or user settings changed.")
                return 0
            # Package installation precedes file deployment. If Niri was absent,
            # install it before validating the staged Niri graph, but validate
            # before modifying any user configuration. Shared packages are
            # intentionally never removed on a later deployment failure.
            if not self.resolve_packages():
                self.output("Required packages were declined or unavailable; no Sparrow files were deployed.")
                return 2
            if not niri_was_installed:
                # The required package set includes Niri. Install it before
                # validating its own config syntax, but still validate the
                # staged graph before deploying user configuration.
                _, niri_plan, _ = self._planned_niri()
                plan = self._build_file_plan(niri_plan)
            self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Runtime copy and entrypoint are staged before all integrations.
            runtime_src = self._runtime_stage_source()
            runtime_dest = self.paths.data / "sparrow-shell/runtime"
            try:
                if not self.write_tree(runtime_dest, runtime_src, role="portable Sparrow runtime copy"):
                    raise RuntimeError("The existing Sparrow runtime was preserved; refusing to link Quickshell to it.")
                runtime_link = self.paths.config / "quickshell/sparrow"
                if not self.write_symlink(runtime_link, runtime_dest, role="canonical Quickshell runtime entry"):
                    raise RuntimeError("The existing canonical Quickshell entry was preserved; no deployment was made.")
            finally:
                shutil.rmtree(runtime_src.parent, ignore_errors=True)
            # A live compositor reloads Niri config on file change. Stage validation happened above.
            self._apply_plan(plan)
            self._copy_tree_files(self.repo / "gtk/Sparrow", self.paths.data / "themes/Sparrow", "Sparrow GTK scaffold", preserve_generated=True)
            self._copy_tree_files(self.repo / "icons/Sparrow", self.paths.data / "icons/Sparrow", "Sparrow icon theme", preserve_generated=True)
            notices = self.paths.data / "sparrow-shell/licenses"
            legal_sources = [
                ("LICENSE", self.repo / "LICENSE"),
                ("THIRD_PARTY.md", self.repo / "THIRD_PARTY.md"),
                ("LICENSES/Ricelin-MIT.txt", self.repo / "LICENSES/Ricelin-MIT.txt"),
                ("icons/NOTICE.md", self.repo / "icons/NOTICE.md"),
                ("icons/PAPIRUS-LICENSE.txt", self.repo / "icons/PAPIRUS-LICENSE.txt"),
                ("Lockscreen/THIRD_PARTY.md", self.repo / "quickshell/sparrow/Lockscreen/THIRD_PARTY.md"),
                ("Lockscreen/COPYING.GPL-3.0", self.repo / "quickshell/sparrow/Lockscreen/COPYING.GPL-3.0"),
                ("Lockscreen/font/OFL.txt", self.repo / "quickshell/sparrow/Lockscreen/font/OFL.txt"),
                ("wallpapers/README.md", self.repo / "quickshell/sparrow/wallpapers/README.md"),
            ]
            for relative, source in legal_sources:
                if source.is_file():
                    self.write_file(notices / relative, source.read_bytes(), role="license/attribution notice")
            self._validate_installed_niri()
            self._activate_units()
            self._save_manifest()
        except Exception as error:
            self.output(f"Install failed; rolling back changed files: {error}")
            if not self.dry_run:
                self._rollback()
            return 1
        self.output(f"Install complete. Backups and restore manifest: {self.backup_root}")
        self.output("Units were enabled but not started or restarted. Log out and back into Niri to test startup.")
        self.output("Portal routing/theme changes are not applied to already-running portal processes; they take effect after the next session start.")
        self.output("Do not select the Sparrow desktop session from a display manager unless Niri is installed and available there.")
        return 0

    def _validate_installed_niri(self) -> None:
        path = self.paths.config / "niri/config.kdl"
        result = self._command(["niri", "validate", "-c", str(path)])
        if result.returncode:
            raise RuntimeError("Deployed Niri config validation failed: " + (result.stderr or result.stdout))

    def _activate_units(self) -> None:
        if self.dry_run or self.testing:
            self.output("TEST/dry-run: user units are not enabled or started.")
            return
        self._command(["systemctl", "--user", "daemon-reload"], check=True)
        managed_units = {
            Path(path).name
            for path, record in self.managed.items()
            if record.get("role") == "Sparrow user service"
            and Path(path).is_file()
            and sha256_file(Path(path)) == record.get("sha256")
        }
        units = [unit for unit in ("sparrow-wallpaper.service", "sparrow-shell.service", "sparrow-idle.service") if unit in managed_units]
        if "sparrow-polkit-agent.service" in managed_units and not self.has_existing_polkit_agent():
            units.append("sparrow-polkit-agent.service")
        to_enable = []
        for unit in units:
            before = self._command(["systemctl", "--user", "is-enabled", unit])
            self.enabled_before[unit] = before.returncode == 0
            if before.returncode == 0:
                continue
            to_enable.append(unit)
        if to_enable:
            try:
                self._command(["systemctl", "--user", "enable", *to_enable], check=True)
            except subprocess.CalledProcessError:
                # `systemctl enable` can partially succeed. Undo only units
                # that were disabled before this invocation.
                enabled_now = [
                    unit for unit in to_enable
                    if self._command(["systemctl", "--user", "is-enabled", unit]).returncode == 0
                ]
                if enabled_now:
                    self._command(["systemctl", "--user", "disable", *enabled_now])
                raise
            self.enabled_by_sparrow.update(to_enable)

    def uninstall(self, *, stop_now: bool = False, restore: bool = True) -> int:
        if not self.old:
            self.output("No Sparrow installer manifest exists; nothing is removed.")
            return 0
        active = []
        if not self.testing:
            for unit in ("sparrow-shell.service", "sparrow-idle.service", "sparrow-wallpaper.service", "sparrow-polkit-agent.service"):
                result = self._command(["systemctl", "--user", "is-active", unit])
                if result.returncode == 0:
                    active.append(unit)
        if active and stop_now and not self.confirm("Stopping Sparrow now will close the shell and wallpaper. Continue?", False):
            self.output("Uninstall cancelled.")
            return 2
        if not self.dry_run and not self.testing:
            owned_enabled = []
            for unit in self.old.get("enabled_by_sparrow", []):
                unit_path = self.paths.config / "systemd/user" / unit
                record = self.old.get("managed", {}).get(str(unit_path), {})
                if unit_path.is_file() and record and sha256_file(unit_path) != record.get("sha256"):
                    self.output(f"Preserving user-edited unit and enablement: {unit_path}")
                    continue
                owned_enabled.append(unit)
            if owned_enabled:
                self._command(["systemctl", "--user", "disable", *owned_enabled])
            if stop_now:
                self._command(["systemctl", "--user", "stop", "sparrow-shell.service", "sparrow-idle.service", "sparrow-wallpaper.service", "sparrow-polkit-agent.service"])
            self._command(["systemctl", "--user", "daemon-reload"])
        defer_runtime_cleanup = bool(active and not stop_now)
        preserved = []
        for key, record in reversed(list(self.old.get("managed", {}).items())):
            path = Path(key)
            if record.get("kind") == "merge":
                current = path.read_text(encoding="utf-8") if path.is_file() else ""
                role = record.get("mergeRole")
                if role == "niri":
                    current_block = self._niri_marker_block(current)
                    if not current_block or current_block != record.get("mergeExpected"):
                        preserved.append(str(path))
                        continue
                    current = self._remove_niri_marker(current)
                elif role == "portal":
                    initial = record.get("initial", {})
                    old_text = ""
                    backup = initial.get("backup")
                    if initial.get("type") == "file" and backup:
                        old_text = Path(backup).read_text(encoding="utf-8")
                    current = self._restore_portal_key(current, old_text)
                    if not initial.get("exists") and not current.strip():
                        if not self.dry_run:
                            remove_path(path)
                        continue
                else:
                    preserved.append(str(path))
                    continue
                if current != (path.read_text(encoding="utf-8") if path.is_file() else "") and not self.dry_run:
                    atomic_write(path, current.encode())
                continue
            if record.get("kind") == "symlink":
                unchanged = path.is_symlink() and os.readlink(path) == record.get("target")
            elif record.get("kind") == "directory":
                unchanged = path.is_dir() and not path.is_symlink() and tree_digest(path) == record.get("sha256")
            else:
                unchanged = path.is_file() and sha256_file(path) == record.get("sha256")
            if not unchanged:
                preserved.append(str(path))
                continue
            if defer_runtime_cleanup and record.get("role") in {
                "portable Sparrow runtime copy", "canonical Quickshell runtime entry"
            }:
                preserved.append(str(path))
                continue
            if restore:
                if not self.dry_run:
                    restore_snapshot(path, record.get("initial", {"exists": False}))
            elif not self.dry_run:
                remove_path(path)
        if defer_runtime_cleanup:
            self.output("Sparrow is still active. Its runtime and entry point were preserved; run ./uninstall.sh again after logging out to finish cleanup.")
        if not self.dry_run:
            if preserved:
                self.output("Preserved user-modified/in-use paths: " + ", ".join(dict.fromkeys(preserved)))
            # Backups remain available for manual recovery; only the active ownership manifest is removed.
            if not defer_runtime_cleanup:
                self.manifest_path.unlink(missing_ok=True)
        self.output(f"Uninstall processed. Recovery backups remain under {self.state_root / 'backups'}.")
        return 0

    @staticmethod
    def _remove_niri_marker(content: str) -> str:
        pattern = re.compile(r"(?m)^" + re.escape(MARKER_START) + r"\n.*?^" + re.escape(MARKER_END) + r"\n?", re.S)
        return pattern.sub("", content, count=1)

    @staticmethod
    def _niri_marker_block(content: str) -> str | None:
        match = re.search(r"(?m)^" + re.escape(MARKER_START) + r"\n.*?^" + re.escape(MARKER_END) + r"\n?", content, re.S)
        return match.group(0) if match else None

    @staticmethod
    def _restore_portal_key(current: str, original: str) -> str:
        key = "org.freedesktop.impl.portal.FileChooser"
        old_match = re.search(rf"(?m)^{re.escape(key)}\s*=.*$", original)
        old_line = old_match.group(0) if old_match else None
        section_match = re.search(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)", current)
        if not section_match:
            return current
        section = section_match.group(1)
        key_match = re.search(rf"(?m)^{re.escape(key)}\s*=.*(?:\n|$)", section)
        if not key_match or key_match.group(0).split("=", 1)[1].strip() != "gtk;":
            return current
        replacement = (old_line + "\n") if old_line else ""
        section = section[:key_match.start()] + replacement + section[key_match.end():]
        result = current[:section_match.start(1)] + section + current[section_match.end(1):]
        if not original or "[preferred]" not in original:
            # Remove only an otherwise empty section created by Sparrow.
            result = re.sub(r"(?m)^\[preferred\]\s*\n(?=\[|\Z)", "", result)
        return result

    @staticmethod
    def _portal_filechooser_route(content: str) -> str | None:
        preferred = re.search(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)", content)
        if not preferred:
            return None
        match = re.search(r"(?m)^org\.freedesktop\.impl\.portal\.FileChooser\s*=\s*(.*)$", preferred.group(1))
        return match.group(1).strip() if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install or restore Sparrow Shell user configuration.")
    parser.add_argument("--dry-run", action="store_true", help="show actions without changing files or packages")
    parser.add_argument("--uninstall", action="store_true", help="remove Sparrow-owned integration and restore backups")
    parser.add_argument("--remove-instead-of-restore", action="store_true", help="remove unchanged Sparrow-owned files instead of restoring prior versions")
    parser.add_argument("--stop-now", action="store_true", help="during uninstall, stop active Sparrow units now")
    parser.add_argument("--testing-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.testing_root:
        if os.environ.get("SPARROW_INSTALLER_TESTING") != "1":
            parser.error("--testing-root is test-only")
        root = args.testing_root.resolve()
        paths = XdgPaths(root, root / ".config", root / ".local/share", root / ".local/state", root / ".cache")
        installer = SparrowInstaller(paths, dry_run=args.dry_run, testing=True)
    else:
        if os.geteuid() == 0:
            parser.error("run as your normal user; Sparrow uses sudo only for approved package installation")
        installer = SparrowInstaller(dry_run=args.dry_run)
    if args.uninstall:
        return installer.uninstall(stop_now=args.stop_now, restore=not args.remove_instead_of_restore)
    return installer.install()


if __name__ == "__main__":
    raise SystemExit(main())
