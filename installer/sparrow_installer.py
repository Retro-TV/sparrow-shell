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


class PackageTransactionError(RuntimeError):
    """A requested package transaction did not complete successfully."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        code = int(exit_code)
        # subprocess uses negative codes for signal termination; expose the
        # conventional shell status (128 + signal) instead of losing it as 1.
        self.exit_code = min(128 + abs(code), 255) if code < 0 else max(1, min(code, 255))


class SparrowInstaller:
    def __init__(
        self,
        paths: XdgPaths | None = None,
        repo: Path = ROOT,
        *,
        dry_run: bool = False,
        testing: bool = False,
        confirm: Callable[[str, bool], bool] | None = None,
        run: Callable[..., subprocess.CompletedProcess] | None = None,
        test_machine: dict | None = None,
        output: Callable[[str], None] = print,
    ) -> None:
        self.paths = paths or XdgPaths.from_environment()
        self.repo = repo
        self.dry_run = dry_run
        self.testing = testing
        self.confirm = confirm or self._confirm
        if testing and run is not None:
            raise ValueError("test mode forbids external command runners; use its built-in closed simulator")
        self.test_machine = test_machine if test_machine is not None else {
            "os": "id=cachyos",
            "packages": set(),
            "commands": {"sudo", "pacman", "bash", "systemd-analyze", "systemctl", "env", "gio", "udevadm"},
            "modules": set(),
            "missing_after_install": set(),
            "existing_polkit_agent": False,
            "pacman_failure": False,
            "pacman_query_failure": False,
            "pacman_transaction_count": 0,
            "interrupt_at_transaction": None,
            "interrupt_at_prompt": False,
            "invocations": [],
            "events": [],
        }
        self.test_machine.setdefault("gsettings", {})
        self.test_machine.setdefault("cachyos_hello_autostart", True)
        self.run = run or (self._test_run if testing else subprocess.run)
        self.output = output
        self.state_root = self.paths.state / "sparrow-shell" / "installer"
        self.manifest_path = self.state_root / "manifest.json"
        self.old = self._read_manifest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.backup_root = self.state_root / "backups" / f"{stamp}-{os.getpid()}"
        self.snapshots: dict[str, dict] = {}
        self.managed: dict[str, dict] = dict(self.old.get("managed", {}))
        self.managed_settings: dict[str, dict] = dict(self.old.get("managed_settings", {}))
        self.changed: list[str] = []
        self.conflicts: list[str] = []
        self.replace_approved: dict[str, bool] = {}
        self.enabled_before: dict[str, bool] = {}
        self.enabled_by_sparrow: set[str] = set(self.old.get("enabled_by_sparrow", []))
        self._installed_package_cache: set[str] | None = None
        self.install_polkit_agent = False
        self.bibata_available = False
        self.skipped_optional_groups: list[str] = []
        self.default_profile_skipped = False
        self.missing_manual: list[str] = []
        self.settings_before: dict[str, str | None] = {}

    def _which(self, executable: str) -> str | None:
        if self.testing:
            return f"/simulated/bin/{executable}" if executable in self.test_machine["commands"] else None
        return shutil.which(executable)

    def _test_run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        """A closed command simulator: installer tests never dispatch to the host."""
        self.test_machine["events"].append(tuple(args))
        self.test_machine["invocations"].append((tuple(args), dict(kwargs)))
        text_result = kwargs.get("text", True)
        stdout = ""
        stderr = ""
        code = 0
        package_binaries = {
            "niri": {"niri"}, "quickshell": {"qs"}, "python": {"python3"},
            "awww": {"awww", "awww-daemon"}, "matugen": {"matugen"},
            "bash": {"bash"}, "jq": {"jq"}, "wireplumber": {"wpctl"},
            "gtk3": {"gtk-launch"}, "lxqt-policykit": {"lxqt-policykit-agent"},
            "ffmpeg": {"ffmpeg", "ffprobe"}, "networkmanager": {"nmcli"},
            "bluez-utils": {"bluetoothctl"}, "upower": {"upower"},
            "wlsunset": {"wlsunset"}, "cava": {"cava"},
            "brightnessctl": {"brightnessctl"}, "ddcutil": {"ddcutil"},
            "curl": {"curl"}, "imagemagick": {"magick"}, "wl-clipboard": {"wl-copy", "wl-paste"},
            "gpu-screen-recorder": {"gpu-screen-recorder"}, "slurp": {"slurp"},
            "hyprlock": {"hyprlock"}, "kitty": {"kitty"}, "fish": {"fish"},
            "starship": {"starship"}, "thunar": {"thunar"},
            "firefox": {"firefox"}, "pavucontrol": {"pavucontrol"},
            "xdg-utils": {"xdg-open"}, "libnotify": {"notify-send"},
        }
        if args[:2] == ["pacman", "-Qq"]:
            if self.test_machine["pacman_query_failure"]:
                code, stderr = 1, "simulated pacman query failure"
            else:
                stdout = "\n".join(sorted(self.test_machine["packages"]))
        elif args[:3] == ["sudo", "pacman", "-S"]:
            self.test_machine["pacman_transaction_count"] += 1
            transaction = self.test_machine["pacman_transaction_count"]
            packages = args[4:]
            if self.test_machine["interrupt_at_transaction"] == transaction:
                # Model pacman having committed a subset before Ctrl+C. A
                # rerun must query and skip these installed packages.
                partial_count = max(1, len(packages) // 3)
                self._simulate_package_install(packages[:partial_count], package_binaries)
                raise KeyboardInterrupt
            if self.test_machine["pacman_failure"] or self.test_machine.get("pacman_failure_at_transaction") == transaction:
                code = int(self.test_machine.get("pacman_failure_exit_code", 1))
                stderr = "simulated pacman transaction failure"
            else:
                self._simulate_package_install(packages, package_binaries)
        elif args and args[0] == "niri" and "validate" in args:
            if "niri" not in self.test_machine["commands"]:
                code, stderr = 127, "simulated niri executable is missing"
        elif args and args[0] == "python3" and "-c" in args:
            module = args[-1].split("import", 1)[-1].strip().split()[0]
            if module not in self.test_machine["modules"]:
                code, stderr = 1, f"simulated Python module is missing: {module}"
        elif args and args[0] == "systemd-analyze":
            for filename in args[args.index("verify") + 1:]:
                content = Path(filename).read_text(encoding="utf-8")
                for executable in re.findall(r"(?m)^Exec(?:Start|StartPre|StartPost|Stop|Condition)=(/[^\s]+)", content):
                    name = Path(executable).name
                    if name not in {"env", "bash"} and name not in self.test_machine["commands"]:
                        code, stderr = 1, f"{filename}: {executable} is not executable (simulated)"
                        break
                for executable in re.findall(r"(?m)^ConditionFileIsExecutable=(/[^\s]+)", content):
                    name = Path(executable).name
                    if name not in self.test_machine["commands"]:
                        code, stderr = 1, f"{filename}: {executable} is not executable (simulated)"
                        break
                if code:
                    break
        elif args and args[0] == "bash" and "-n" in args:
            pass
        else:
            raise AssertionError(f"Test runner refused to execute unmodelled host command: {args!r}")
        return subprocess.CompletedProcess(args, code, stdout if text_result else stdout.encode(), stderr if text_result else stderr.encode())

    def _simulate_package_install(self, packages: list[str], package_binaries: dict[str, set[str]]) -> None:
        self.test_machine["packages"].update(packages)
        for package in packages:
            self.test_machine["commands"].update(package_binaries.get(package, set()))
            if package == "python-pillow":
                self.test_machine["modules"].add("PIL.Image")
        self.test_machine["commands"].difference_update(self.test_machine["missing_after_install"])

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

    def _command(
        self,
        args: list[str],
        *,
        check: bool = False,
        inherit_stdio: bool = False,
    ) -> subprocess.CompletedProcess:
        if not inherit_stdio:
            self.output("+ " + " ".join(args))
        if self.dry_run and self._is_mutating_command(args):
            self.output("  (dry-run: command not executed)")
            return subprocess.CompletedProcess(args, 0, "", "")
        if inherit_stdio:
            # Keep pacman's normal terminal UI and sudo's controlling TTY.
            # subprocess.run waits for the child and inherits stdin/stdout/stderr.
            sys.stdout.flush()
            sys.stderr.flush()
            return self.run(args, check=check)
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
        try:
            sets = json.loads((self.repo / "installer/package-sets.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read valid installer/package-sets.json: {error}") from error
        if not isinstance(sets, dict):
            raise ValueError("Installer package set must be a JSON object.")
        package_pattern = re.compile(r"^[A-Za-z0-9@._+:-]+$")
        for key in ("required", "defaults"):
            values = sets.get(key)
            if not isinstance(values, list) or any(not isinstance(item, str) or not package_pattern.fullmatch(item) for item in values):
                raise ValueError(f"Installer package set '{key}' must be a list of valid package names.")
        optional = sets.get("optional")
        if not isinstance(optional, dict) or any(
            not isinstance(group, str)
            or not isinstance(values, list)
            or any(not isinstance(item, str) or not package_pattern.fullmatch(item) for item in values)
            for group, values in optional.items()
        ):
            raise ValueError("Installer package set 'optional' must map group names to lists of valid package names.")
        for key in ("required_executables", "platform_executables"):
            values = sets.get(key, [])
            if not isinstance(values, list) or any(not isinstance(item, str) or not package_pattern.fullmatch(item) for item in values):
                raise ValueError(f"Installer package set '{key}' must be a list of executable names.")
        modules = sets.get("required_python_modules", [])
        if not isinstance(modules, list) or any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.]+", item) for item in modules):
            raise ValueError("Installer package set 'required_python_modules' must contain valid module names.")
        polkit = sets.get("polkit_agent")
        if not isinstance(polkit, dict) or any(not isinstance(polkit.get(key), str) for key in ("package", "executable")):
            raise ValueError("Installer package set 'polkit_agent' must specify a package and executable.")
        return sets

    def installed_packages(self) -> set[str]:
        if self._installed_package_cache is not None:
            return self._installed_package_cache
        result = self._command(["pacman", "-Qq"])
        if result.returncode:
            raise PackageTransactionError(
                "Could not query installed packages with pacman -Qq: " + (result.stderr or "unknown pacman error"),
                result.returncode,
            )
        self._installed_package_cache = set(result.stdout.splitlines())
        return self._installed_package_cache

    def _install_package_list(self, packages: list[str], *, label: str, required: bool = False) -> bool:
        missing = sorted(set(packages) - self.installed_packages())
        if not missing:
            self.output(f"{label}: already installed")
            return True
        self.output(f"{label} packages to install ({len(missing)}): " + " ".join(missing))
        if not self.confirm(f"Install these official repository packages with pacman?", required):
            self.output(f"Skipped {label}; dependent apps/features remain unavailable until installed.")
            return False
        if self._which("sudo") is None:
            raise PackageTransactionError("sudo is unavailable; install manually with: sudo pacman -S --needed " + " ".join(missing))
        if self._which("pacman") is None:
            raise PackageTransactionError("pacman is unavailable; cannot install package group " + label)
        self.output(f"Starting pacman transaction for {label}.")
        try:
            result = self._command(["sudo", "pacman", "-S", "--needed", *missing], inherit_stdio=True)
        except KeyboardInterrupt:
            self._installed_package_cache = None
            self.output(f"Pacman transaction for {label} was interrupted.")
            raise
        if result.returncode:
            self._installed_package_cache = None
            raise PackageTransactionError(
                f"Pacman transaction for {label} failed with exit status {result.returncode}. "
                "No Sparrow files were deployed; resolve the package issue and rerun the installer.",
                result.returncode,
            )
        self._installed_package_cache = None
        still_missing = sorted(set(missing) - self.installed_packages())
        if still_missing:
            raise PackageTransactionError(
                f"Pacman returned success for {label}, but package verification still finds these missing: "
                + ", ".join(still_missing)
                + ". No Sparrow files were deployed; rerun after resolving the package state."
            )
        self._installed_package_cache = None
        self.output(f"Pacman transaction for {label} completed successfully.")
        self.output(f"Verified all {len(missing)} requested {label} package(s) are installed.")
        return True

    def resolve_packages(self) -> bool:
        if self.testing:
            os_release = self.test_machine["os"].lower()
        elif not Path("/etc/os-release").is_file():
            self.output("Cannot identify the operating system; refusing an unverified Sparrow deployment.")
            return False
        else:
            os_release = Path("/etc/os-release").read_text(errors="replace").lower()
        if not any(name in os_release for name in ("id=arch", "id=cachyos", "id_like=arch")):
            self.output("Sparrow targets Arch/CachyOS; refusing to install on an unverified distribution.")
            return False
        if self._which("pacman") is None:
            self.output("pacman is unavailable; install/repair pacman before running Sparrow Installer.")
            return False
        sets = self.package_sets()
        installed = self.installed_packages()
        for group, names in (("Required", sets["required"]), ("Defaults", sets["defaults"]), *sets["optional"].items()):
            present = sorted(set(names) & installed)
            missing = sorted(set(names) - installed)
            self.output(f"Detected {group} packages present: " + (", ".join(present) if present else "none"))
            if missing:
                self.output(f"  not installed: {', '.join(missing)}")
        bibata_available = self._detect_bibata()
        self.bibata_available = bibata_available
        for label, available in (
            ("mpvpaper", self._which("mpvpaper") is not None),
            ("Rishot", self._which("rishot") is not None),
            ("Bibata cursor theme", bibata_available),
        ):
            self.output(f"Detected {label}: {'available' if available else 'not found'}")
        if self.dry_run:
            self.output("AUR/upstream (manual only): " + "; ".join(f"{k}: {v}" for k, v in sets["aur_manual"].items()))
            return True
        if not self._install_package_list(sets["required"], label="Required Sparrow runtime", required=True):
            return False
        if not self._verify_required_runtime(sets):
            return False
        if self.confirm("Install Sparrow's recommended desktop apps, fonts, GTK theme and portal integrations?", True):
            defaults = list(sets["defaults"])
            existing_screencast = self._portal_route(
                self.paths.config / "xdg-desktop-portal/niri-portals.conf",
                "org.freedesktop.impl.portal.ScreenCast",
            )
            if existing_screencast and existing_screencast != "gnome;":
                defaults.remove("xdg-desktop-portal-gnome")
                self.output(f"Preserving the existing ScreenCast portal route ({existing_screencast}); skipping the GNOME portal package.")
            agent_exists = self.has_existing_polkit_agent()
            if not agent_exists:
                defaults.append(sets["polkit_agent"]["package"])
            if not self._install_package_list(defaults, label="Default desktop profile"):
                self.default_profile_skipped = True
                self.output("Recommended desktop bundle declined. App shortcuts/integrations for uninstalled apps will be unavailable.")
            if not agent_exists:
                self.install_polkit_agent = self._which(sets["polkit_agent"]["executable"]) is not None
                if not self.install_polkit_agent:
                    self.output("No graphical Polkit agent was detected or installed; privileged prompts will not have a Sparrow agent.")
        else:
            self.default_profile_skipped = True
            if not self.has_existing_polkit_agent():
                self.output("Default apps/Polkit were declined and no existing Polkit agent was detected; privileged prompts will not be shown graphically.")
        optional = sets["optional"]
        if self.confirm("Choose optional feature packages (recording, Night Light, visualizer, hardware integrations)?", False):
            for group, packages in optional.items():
                if self.confirm(f"  Include optional group '{group}' ({', '.join(packages)})?", False):
                    if not self._install_package_list(packages, label=f"Optional {group}"):
                        self.skipped_optional_groups.append(group)
                else:
                    self.skipped_optional_groups.append(group)
        else:
            self.skipped_optional_groups.extend(optional)
        self.output("No AUR packages are installed by Sparrow. Manual AUR notes: " + "; ".join(f"{k}: {v}" for k, v in sets["aur_manual"].items()))
        for executable, label in (("rishot", "Rishot screenshots"), ("mpvpaper", "video wallpaper playback")):
            if self._which(executable) is None:
                self.missing_manual.append(label)
        if not bibata_available:
            self.missing_manual.append("Bibata Modern Ice cursor (manual AUR)")
        if self._which("rishot") is None:
            self.output("Screenshot shortcut Super+Shift+S requires the separate Rishot application; install it manually from its upstream-supported source.")
        if not bibata_available:
            self.output("Bibata Modern Ice is not installed. The cursor default needs the manual AUR package listed above or a user-selected cursor theme.")
        return True

    def _verify_required_runtime(self, sets: dict) -> bool:
        missing = [name for name in sets.get("required_executables", []) if self._which(name) is None]
        missing_platform = [name for name in sets.get("platform_executables", []) if self._which(name) is None]
        if missing_platform:
            self.output("Required Arch/CachyOS base-session commands are missing: " + ", ".join(missing_platform))
            return False
        if missing:
            self.output("Required Sparrow executables are still missing after package resolution: " + ", ".join(missing))
            self.output("Install the corresponding official packages, then rerun Sparrow Installer.")
            return False
        for module in sets.get("required_python_modules", []):
            result = self._command(["python3", "-c", f"import {module}"])
            if result.returncode:
                self.output(f"Required Python module is missing after package resolution: {module}")
                return False
        return True

    def has_existing_polkit_agent(self) -> bool:
        if self.testing:
            return bool(self.test_machine["existing_polkit_agent"])
        known = re.compile(r"(lxqt-policykit-agent|polkit-gnome-authentication-agent-1|polkit-mate-authentication-agent-1|polkit-kde-authentication-agent-1|hyprpolkitagent)")
        try:
            result = self._command(["ps", "-u", str(os.getuid()), "-o", "args="])
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

    def _detect_bibata(self) -> bool:
        if self.testing:
            return "Bibata-Modern-Ice" in self.test_machine.get("themes", set())
        return any(
            (root / "Bibata-Modern-Ice/index.theme").is_file()
            for root in (self.paths.data / "icons", Path("/usr/share/icons"), Path("/usr/local/share/icons"))
        )

    def _has_cachyos_hello_skeleton_entry(self) -> bool:
        if self.testing:
            return bool(self.test_machine.get("cachyos_hello_autostart", True))
        source = Path("/etc/skel/.config/autostart/cachyos-hello.desktop")
        try:
            return self._is_cachyos_hello_desktop(source.read_text(encoding="utf-8"))
        except OSError:
            return False

    @staticmethod
    def _is_cachyos_hello_desktop(content: str) -> bool:
        section = re.search(r"(?ms)^\[Desktop Entry\]\s*\n(.*?)(?=^\[|\Z)", content)
        if not section:
            return False
        values = dict(re.findall(r"(?m)^([A-Za-z][A-Za-z0-9]*)\s*=\s*(.*?)\s*$", section.group(1)))
        exec_command = values.get("Exec", "").split("%", 1)[0].strip()
        return values.get("Name") == "CachyOS Hello" and exec_command == "/usr/bin/cachyos-hello"

    @staticmethod
    def _desktop_hidden_value(content: str) -> str | None:
        section = re.search(r"(?ms)^\[Desktop Entry\]\s*\n(.*?)(?=^\[|\Z)", content)
        if not section:
            return None
        match = re.search(r"(?m)^Hidden\s*=\s*(.*?)\s*$", section.group(1))
        return match.group(1).lower() if match else None

    @staticmethod
    def _merge_desktop_hidden(content: str) -> str:
        if not content:
            return "[Desktop Entry]\nHidden=true\n"
        section = re.search(r"(?ms)^\[Desktop Entry\]\s*\n(.*?)(?=^\[|\Z)", content)
        if not section:
            return content.rstrip() + "\n\n[Desktop Entry]\nHidden=true\n"
        match = re.search(r"(?m)^Hidden\s*=.*$", section.group(1))
        if match:
            updated = section.group(1)[:match.start()] + "Hidden=true" + section.group(1)[match.end():]
        else:
            updated = section.group(1).rstrip("\n") + "\nHidden=true\n"
        return content[:section.start(1)] + updated + content[section.end(1):]

    def _icon_theme_user_value(self) -> tuple[bool, str | None]:
        if self.testing:
            return True, self.test_machine.setdefault("gsettings", {}).get("icon-theme")
        if self.paths.home != Path.home():
            return False, None
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            variant = settings.get_user_value("icon-theme")
            return True, variant.unpack() if variant is not None else None
        except Exception as error:
            self.output(f"Could not inspect the GTK icon-theme user preference; leaving it unchanged: {error}")
            return False, None

    def _set_icon_theme_user_value(self, value: str | None) -> bool:
        if self.testing:
            values = self.test_machine.setdefault("gsettings", {})
            if value is None:
                values.pop("icon-theme", None)
            else:
                values["icon-theme"] = value
            return True
        if self.paths.home != Path.home():
            return False
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            if value is None:
                settings.reset("icon-theme")
                return True
            return bool(settings.set_string("icon-theme", value))
        except Exception as error:
            self.output(f"Could not update GTK icon-theme preference: {error}")
            return False

    def _apply_sparrow_icon_default(self) -> None:
        key = "org.gnome.desktop.interface/icon-theme"
        if not (self.paths.data / "icons/Sparrow/index.theme").is_file():
            self.output("Sparrow icon theme files are unavailable; preserving the current GTK icon-theme preference.")
            return
        available, current = self._icon_theme_user_value()
        if not available:
            return
        previous = self.managed_settings.get(key)
        if previous:
            if current == previous.get("installed"):
                return
            # A later user choice relinquishes Sparrow ownership permanently.
            self.managed_settings.pop(key, None)
            self.output(f"Preserved the user's GTK icon-theme choice: {current}")
            return
        if current is not None:
            self.output(f"Preserved explicit GTK icon-theme choice: {current}")
            return
        if self.dry_run:
            self.output("Would set the unset GTK icon-theme preference to Sparrow (colors remain globally Adwaita).")
            return
        if self._set_icon_theme_user_value("Sparrow"):
            self.settings_before[key] = current
            self.managed_settings[key] = {"previous": current, "installed": "Sparrow"}
            self.output("Selected Sparrow icons for this fresh user; global GTK colors remain unchanged.")

    def _restore_icon_default(self, key: str, record: dict) -> None:
        available, current = self._icon_theme_user_value()
        if not available:
            return
        if current != record.get("installed"):
            self.output(f"Preserved changed GTK icon-theme preference during restore: {current}")
            return
        self._set_icon_theme_user_value(record.get("previous"))

    @classmethod
    def _restore_desktop_hidden(cls, current: str, original: str) -> str:
        if cls._desktop_hidden_value(current) != "true":
            return current
        original_section = re.search(r"(?ms)^\[Desktop Entry\]\s*\n(.*?)(?=^\[|\Z)", original)
        original_hidden = None
        if original_section:
            match = re.search(r"(?m)^Hidden\s*=.*$", original_section.group(1))
            if match:
                original_hidden = match.group(0)
        section = re.search(r"(?ms)^\[Desktop Entry\]\s*\n(.*?)(?=^\[|\Z)", current)
        if not section:
            return current
        match = re.search(r"(?m)^Hidden\s*=.*(?:\n|$)", section.group(1))
        if not match:
            return current
        replacement = (original_hidden + "\n") if original_hidden else ""
        body = section.group(1)[:match.start()] + replacement + section.group(1)[match.end():]
        result = current[:section.start(1)] + body + current[section.end(1):]
        if not original:
            remaining = re.sub(r"(?m)^\[Desktop Entry\]\s*$", "", result)
            if not remaining.strip():
                return ""
        return result

    def _apply_cachyos_hello_override(self, path: Path) -> None:
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        old_record = self.managed.get(str(path))
        if old_record and old_record.get("mergeRole") == "desktop-hidden":
            if not path.exists():
                self.managed.pop(str(path), None)
                self.output(f"Preserved the user's removal of the CachyOS Hello override: {path}")
                return
            if current and self._desktop_hidden_value(current) != "true":
                self.managed.pop(str(path), None)
                self.output(f"Preserved user-edited CachyOS Hello autostart: {path}")
                return
        elif current:
            if not self._is_cachyos_hello_desktop(current):
                self.output(f"Preserved unrelated user autostart with the CachyOS Hello desktop ID: {path}")
                return
            # Explicit Hidden=false is treated as a user choice to keep it.
            if self._desktop_hidden_value(current) == "false":
                self.output(f"Preserved explicit CachyOS Hello autostart choice: {path}")
                return
            if self._desktop_hidden_value(current) == "true":
                return
        wanted = self._merge_desktop_hidden(current)
        if wanted == current:
            return
        self._snapshot_once(path)
        initial = self._initial_snapshot(path) if old_record is None else old_record.get("initial", {"exists": False})
        if not self.dry_run:
            atomic_write(path, wanted.encode())
        self.managed[str(path)] = {
            "kind": "merge", "role": "CachyOS Hello autostart suppression",
            "initial": initial, "mergeRole": "desktop-hidden", "mergeExpected": "Hidden=true",
        }
        self.changed.append(str(path))
        self.output("Suppressed only CachyOS Hello through the Sparrow user's XDG autostart override.")

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

    def merge_portal(self, existing: str, *, include_screencast: bool) -> str:
        routes = {
            "org.freedesktop.impl.portal.FileChooser": "gtk;",
        }
        if include_screencast:
            routes["org.freedesktop.impl.portal.ScreenCast"] = "gnome;"
        section_pattern = re.compile(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)")
        match = section_pattern.search(existing)
        if match:
            section = match.group(1)
            for key, value in routes.items():
                key_pattern = re.compile(rf"(?m)^{re.escape(key)}\s*=.*$")
                found = key_pattern.search(section)
                if found:
                    if key.endswith("FileChooser") and found.group(0).split("=", 1)[1].strip() != value:
                        section = key_pattern.sub(f"{key}={value}", section, count=1)
                else:
                    section += f"{key}={value}\n"
            return existing[:match.start(1)] + section + existing[match.end(1):]
        tail = "" if not existing or existing.endswith("\n") else "\n"
        route_lines = "".join(f"{key}={value}\n" for key, value in routes.items())
        return existing + tail + f"\n[preferred]\n{route_lines}"

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
                    if source.name == "cursor.kdl" and not self.bibata_available:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text("// Bibata Modern Ice is not installed; preserve Niri's existing cursor default.\n", encoding="utf-8")
                        continue
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
                    self.output("Staged Niri validation is deferred until after the approved package step and before deployment.")
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
                if not self.bibata_available:
                    (stage_home / "sparrow/cursor.kdl").write_text(
                        "// Bibata Modern Ice is not installed; preserve Niri's existing cursor default.\n",
                        encoding="utf-8",
                    )
                if validate:
                    result = self._command(["niri", "validate", "-c", str(root)])
                    if result.returncode:
                        raise RuntimeError("Repository Niri config validation failed: " + (result.stderr or result.stdout))
                else:
                    self.output("Staged Niri validation is deferred until after the approved package step and before deployment.")
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
            if source.name == "cursor.kdl" and not self.bibata_available:
                data = b"// Bibata Modern Ice is not installed; preserve Niri's existing cursor default.\n"
            else:
                data = source.read_bytes()
            plan.append((self.paths.config / "niri/sparrow" / source.name, data, "Niri Sparrow fragment", 0o644))
        for source in sorted((self.repo / "quickshell/sparrow/systemd").glob("*.service")):
            if source.name == "sparrow-polkit-agent.service" and not self.install_polkit_agent:
                continue
            plan.append((self.paths.config / "systemd/user" / source.name, self._unit_payload(source), "Sparrow user service", 0o644))
        dropin = self.repo / "quickshell/sparrow/systemd/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf"
        plan.append((self.paths.config / "systemd/user/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf", dropin.read_bytes(), "GTK portal-only theme override", 0o644))
        user_files = [
            (self.repo / "kitty/kitty.conf", self.paths.config / "kitty/kitty.conf", "Kitty defaults"),
            (self.repo / "fish/config.fish", self.paths.config / "fish/config.fish", "Fish defaults"),
            (self.repo / "starship/starship.toml", self.paths.config / "starship.toml", "Starship defaults"),
            (self.repo / "applications/sparrow-files.desktop", self.paths.data / "applications/sparrow-files.desktop", "Sparrow Files desktop entry"),
            (self.repo / "hyprlock/hyprlock.conf", self.paths.config / "sparrow/hyprlock.conf", "optional Hyprlock fallback config"),
        ]
        if self._has_cachyos_hello_skeleton_entry():
            hello_path = self.paths.config / "autostart/cachyos-hello.desktop"
            plan.append((hello_path, b"[Desktop Entry]\nHidden=true\n", "CachyOS Hello autostart suppression", 0o644))
        if self.bibata_available:
            user_files.append((self.repo / "environment.d/90-cursor.conf", self.paths.config / "environment.d/90-cursor.conf", "recommended cursor defaults"))
        for source, destination, label in user_files:
            plan.append((destination, source.read_bytes(), label, source.stat().st_mode & 0o777))
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        original_portal = portal.read_text(encoding="utf-8") if portal.is_file() else ""
        gnome_portal_installed = "xdg-desktop-portal-gnome" in self.installed_packages()
        merged_portal = self.merge_portal(original_portal, include_screencast=gnome_portal_installed)
        plan.append((portal, merged_portal.encode(), "Sparrow portal route merge", 0o644))
        return plan

    def _validate_units(self, plan: list[tuple[Path, bytes, str, int]]) -> None:
        if self._which("systemd-analyze") is None:
            raise RuntimeError("systemd-analyze is required to validate Sparrow's user services; install/repair the systemd base package.")
        unit_payloads = [(path.name, content) for path, content, role, _ in plan if role == "Sparrow user service"]
        if not unit_payloads:
            raise RuntimeError("No Sparrow user service units were staged for validation.")
        with tempfile.TemporaryDirectory(prefix="sparrow-unit-stage-") as temp_name:
            staged = []
            for name, content in unit_payloads:
                path = Path(temp_name) / name
                path.write_bytes(content)
                staged.append(str(path))
            result = self._command(["systemd-analyze", "--user", "verify", *staged])
            if result.returncode:
                raise RuntimeError("Staged Sparrow systemd unit validation failed: " + (result.stderr or result.stdout))

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
        if self._which("qmllint"):
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
            elif role == "Sparrow portal route merge":
                self.write_merged_file(path, content, role=role, merge_role="portal")
            elif role == "CachyOS Hello autostart suppression":
                self._apply_cachyos_hello_override(path)
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
            "managed_settings": self.managed_settings,
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
        for key, previous in self.settings_before.items():
            available, current = self._icon_theme_user_value()
            if available and current == "Sparrow":
                self._set_icon_theme_user_value(previous)
        if newly_enabled and not self.testing and not self.dry_run:
            self._command(["systemctl", "--user", "daemon-reload"])

    def install(self) -> int:
        try:
            self.output("[1/6] Checking installer inputs and source syntax")
            self._validate_sources()
            self.bibata_available = self._detect_bibata()
            # Planning may stage config text, but package-dependent validation
            # is intentionally deferred until after the approved transaction.
            _, niri_plan, _ = self._planned_niri(validate=False)
            plan = self._build_file_plan(niri_plan)
            self.output("Planned: portable runtime, Niri defaults, user services, scoped portal/GTK integration, and selected desktop defaults.")
            self.output("User state, wallpapers, generated palettes, caches, and monitor layout will be preserved.")
            if self.dry_run:
                for path, _, role, _ in plan:
                    self.output(f"  {role}: {path}")
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
                self.output("[2/6] Checking package availability (dry-run; no transactions)")
                if not self.resolve_packages():
                    return 2
                self.output("Dry run complete; no files, packages, services, or user settings changed.")
                return 0
            # Package installation precedes file deployment. If Niri was absent,
            # install it before validating the staged Niri graph, but validate
            # before modifying any user configuration. Shared packages are
            # intentionally never removed on a later deployment failure.
            self.output("[2/6] Resolving required, recommended, and optional packages")
            if not self.resolve_packages():
                self.output("Required packages were declined or unavailable; no Sparrow files were deployed.")
                return 2
            _, niri_plan, _ = self._planned_niri(validate=True)
            plan = self._build_file_plan(niri_plan)
            self.output("[3/6] Validating staged Niri configuration and Sparrow services")
            self._validate_units(plan)
            self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Runtime copy and entrypoint are staged before all integrations.
            self.output("[4/6] Deploying Sparrow runtime and selected configuration")
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
            self._apply_sparrow_icon_default()
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
            self.output("[5/6] Verifying the installed Niri configuration")
            self._validate_installed_niri()
            self.output("[6/6] Enabling session integration and saving installer state")
            self._activate_units()
            self._save_manifest()
        except KeyboardInterrupt:
            self._installed_package_cache = None
            if not self.dry_run:
                self._rollback()
            self.output("Installation cancelled by user. No further Sparrow changes were made.")
            self.output("Any packages completed by pacman remain installed; rerun the installer to resume. Do not remove pacman lock files manually.")
            return 130
        except PackageTransactionError as error:
            self.output(f"Install stopped: {error}")
            if not self.dry_run:
                self._rollback()
            return error.exit_code
        except Exception as error:
            self.output(f"Install failed; rolling back changed files: {error}")
            if not self.dry_run:
                self._rollback()
            return 1
        self.output(f"Sparrow installation succeeded. Backups and restore manifest: {self.backup_root}")
        self.output("Units were enabled but not started or restarted. Log out and back into Niri to test startup.")
        self.output("Portal routing/theme changes are not applied to already-running portal processes; they take effect after the next session start.")
        if self.default_profile_skipped:
            self.output("Recommended desktop apps/integrations were skipped; some default shortcuts and app theming will be unavailable.")
        if self.skipped_optional_groups:
            self.output("Optional groups skipped: " + ", ".join(self.skipped_optional_groups))
        if self.missing_manual:
            self.output("Manual/external items still missing: " + ", ".join(self.missing_manual) + ".")
        self.output("Next: log out, choose Niri in your session menu, and log in. If no session menu exists, start `niri-session` from a TTY.")
        self.output("Uninstall later with `./uninstall.sh`; recovery state is kept under " + str(self.state_root) + ".")
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
                elif role == "desktop-hidden":
                    initial = record.get("initial", {})
                    original = ""
                    backup = initial.get("backup")
                    if initial.get("type") == "file" and backup:
                        original = Path(backup).read_text(encoding="utf-8")
                    current = self._restore_desktop_hidden(current, original)
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
            for key, record in self.old.get("managed_settings", {}).items():
                self._restore_icon_default(key, record)
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
        managed = {
            "org.freedesktop.impl.portal.FileChooser": "gtk;",
            "org.freedesktop.impl.portal.ScreenCast": "gnome;",
        }
        result = current
        for key, expected in managed.items():
            section_match = re.search(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)", result)
            if not section_match:
                break
            section = section_match.group(1)
            key_match = re.search(rf"(?m)^{re.escape(key)}\s*=.*(?:\n|$)", section)
            if not key_match or key_match.group(0).split("=", 1)[1].strip() != expected:
                continue
            original_match = re.search(rf"(?m)^{re.escape(key)}\s*=.*$", original)
            replacement = (original_match.group(0) + "\n") if original_match else ""
            section = section[:key_match.start()] + replacement + section[key_match.end():]
            result = result[:section_match.start(1)] + section + result[section_match.end(1):]
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

    @staticmethod
    def _portal_route(path: Path, interface: str) -> str | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        preferred = re.search(r"(?ms)^\[preferred\]\s*\n(.*?)(?=^\[|\Z)", content)
        if not preferred:
            return None
        match = re.search(rf"(?m)^{re.escape(interface)}\s*=\s*(.*)$", preferred.group(1))
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
        try:
            return installer.uninstall(stop_now=args.stop_now, restore=not args.remove_instead_of_restore)
        except KeyboardInterrupt:
            print("Uninstall cancelled by user; no further files or services will be changed.", file=sys.stderr)
            return 130
    return installer.install()


if __name__ == "__main__":
    raise SystemExit(main())
