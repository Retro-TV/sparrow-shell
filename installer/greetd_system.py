#!/usr/bin/env python3
"""Conservative root-side install/restore of Sparrow's opt-in greetd setup."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def capture(path: Path, backup: Path) -> dict:
    if path.is_symlink():
        return {"exists": True, "type": "symlink", "target": os.readlink(path)}
    if not path.exists():
        return {"exists": False}
    if not path.is_file():
        raise RuntimeError(f"Refusing to replace non-file system config: {path}")
    backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy2(path, backup)
    return {"exists": True, "type": "file", "backup": str(backup), "mode": path.stat().st_mode & 0o777}


def restore(path: Path, saved: dict) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        raise RuntimeError(f"Refusing to remove non-file system path during restore: {path}")
    if not saved.get("exists"):
        return
    if saved["type"] == "symlink":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(saved["target"])
    elif saved["type"] == "file":
        source = Path(saved["backup"])
        if not source.is_file():
            raise RuntimeError(f"Required recovery backup is missing: {source}")
        atomic_write(path, source.read_bytes(), saved.get("mode", 0o644))


class GreetdSystemManager:
    def __init__(
        self,
        repo: Path,
        *,
        etc_root: Path = Path("/etc"),
        state_root: Path = Path("/var/lib/sparrow-shell/installer/greetd"),
        backup_root: Path = Path("/var/backups/sparrow/greetd"),
        run: Callable = subprocess.run,
        require_root: bool = True,
    ) -> None:
        self.repo = repo
        self.etc_root = etc_root
        self.state_root = state_root
        self.backup_root = backup_root
        self.run = run
        self.require_root = require_root
        self.manifest_path = state_root / "manifest.json"
        source_manifest = json.loads((repo / "SOURCE-OF-TRUTH.json").read_text(encoding="utf-8"))
        definition = source_manifest["system_integrations"]["greetd"]
        self.configs = tuple(zip(definition["sources"], definition["destinations"], strict=True))

    def _destination(self, destination: str) -> Path:
        relative = Path(destination).relative_to("/etc")
        return self.etc_root / relative

    def _systemctl(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = self.run(["systemctl", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            raise RuntimeError(f"systemctl {' '.join(args)} failed: {result.stderr or result.stdout}")
        return result

    def _enabled(self, unit: str) -> bool:
        return self._systemctl("is-enabled", unit, check=False).returncode == 0

    def _active(self, unit: str) -> bool:
        return self._systemctl("is-active", unit, check=False).returncode == 0

    def _load(self) -> dict:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if value.get("schema") == 1 else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def display_manager(self) -> str | None:
        alias = self.etc_root / "systemd/system/display-manager.service"
        if not alias.is_symlink():
            return None
        service = alias.resolve(strict=False).name
        return None if service == "greetd.service" else service

    def plan(self) -> dict:
        old = self._load()
        conflicts = []
        for source_rel, dest_rel in self.configs:
            source = self.repo / source_rel
            destination = self._destination(dest_rel)
            expected = source.read_bytes()
            previous = old.get("files", {}).get(str(destination), {})
            managed_as_is = destination.is_file() and digest(destination.read_bytes()) == previous.get("installed_sha256")
            if destination.exists() or destination.is_symlink():
                if not managed_as_is and (not destination.is_file() or digest(destination.read_bytes()) != digest(expected)):
                    conflicts.append(str(destination))
        return {"conflicting_files": conflicts, "display_manager": self.display_manager()}

    def install(self, *, replace_existing: bool = False, replace_display_manager: bool = False) -> dict:
        if self.require_root and os.geteuid() != 0:
            raise RuntimeError("Run this system integration through sudo.")
        plan = self.plan()
        if plan["conflicting_files"] and not replace_existing:
            raise RuntimeError("Existing system config needs explicit replacement consent: " + ", ".join(plan["conflicting_files"]))
        manager = plan["display_manager"]
        if manager and not replace_display_manager:
            raise RuntimeError(f"Existing display manager {manager} needs explicit replacement consent.")

        old = self._load()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.backup_root / stamp
        files = dict(old.get("files", {}))
        for index, (source_rel, dest_rel) in enumerate(self.configs, 1):
            source, destination = self.repo / source_rel, self._destination(dest_rel)
            record = dict(files.get(str(destination), {}))
            if "initial" not in record:
                record["initial"] = capture(destination, backup_dir / f"{index:02d}-{destination.name}")
            record["installed_sha256"] = digest(source.read_bytes())
            record["source"] = source_rel
            files[str(destination)] = record

        state = old or {
            "schema": 1,
            "greetd_enabled_before": self._enabled("greetd.service"),
            "tty2_enabled_before": self._enabled("getty@tty2.service"),
            "tty2_active_before": self._active("getty@tty2.service"),
            "display_manager_before": manager,
            "display_manager_enabled_before": self._enabled(manager) if manager else False,
        }
        state.update({"files": files, "last_backup": str(backup_dir)})
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if backup_dir.exists():
            backup_dir = self.backup_root / f"{stamp}-{os.getpid()}"
            state["last_backup"] = str(backup_dir)
        self.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(self.manifest_path, (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(), 0o600)

        written: list[Path] = []
        try:
            # Establish the recovery console before taking ownership of tty1.
            self._systemctl("enable", "--now", "getty@tty2.service")
            if not self._active("getty@tty2.service"):
                raise RuntimeError("getty@tty2.service did not become active; login-manager settings were left unchanged.")
            if manager and state.get("display_manager_enabled_before"):
                self._systemctl("disable", manager)
            for source_rel, dest_rel in self.configs:
                source, destination = self.repo / source_rel, self._destination(dest_rel)
                atomic_write(destination, source.read_bytes(), 0o644)
                written.append(destination)
            self._systemctl("daemon-reload")
            self._systemctl("enable", "greetd.service")  # Deliberately never start/restart greetd here.
        except Exception:
            for destination in written:
                record = files[str(destination)]
                restore(destination, record["initial"])
            if not state.get("greetd_enabled_before"):
                self._systemctl("disable", "greetd.service", check=False)
            if manager and state.get("display_manager_enabled_before"):
                self._systemctl("enable", manager, check=False)
            if not state.get("tty2_enabled_before"):
                self._systemctl("disable", "getty@tty2.service", check=False)
            self._systemctl("daemon-reload", check=False)
            raise
        return {"status": "installed", "backup": str(backup_dir), "enabled_next_boot": True, "started": False}

    def uninstall(self) -> dict:
        if self.require_root and os.geteuid() != 0:
            raise RuntimeError("Run this system integration through sudo.")
        state = self._load()
        if not state:
            return {"status": "not-installed"}
        clean = True
        restored = []
        preserved = []
        for path_text, record in state.get("files", {}).items():
            path = Path(path_text)
            if path.is_file() and digest(path.read_bytes()) == record.get("installed_sha256"):
                restore(path, record.get("initial", {"exists": False}))
                restored.append(path_text)
            else:
                clean = False
                preserved.append(path_text)
        # If the user edited either system config, retain login-manager enablement too.
        if clean:
            manager = state.get("display_manager_before")
            if not state.get("greetd_enabled_before"):
                self._systemctl("disable", "greetd.service", check=False)
            if manager and state.get("display_manager_enabled_before"):
                current_manager = self.display_manager()
                if current_manager in (None, "greetd.service"):
                    self._systemctl("enable", manager, check=False)
            if not state.get("tty2_enabled_before"):
                self._systemctl("disable", "getty@tty2.service", check=False)
        self._systemctl("daemon-reload", check=False)
        self.manifest_path.unlink(missing_ok=True)
        return {"status": "restored", "restored": restored, "preserved": preserved, "unit_state_restored": clean}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "install", "uninstall"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--etc-root", type=Path, default=Path("/etc"))
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/sparrow-shell/installer/greetd"))
    parser.add_argument("--backup-root", type=Path, default=Path("/var/backups/sparrow/greetd"))
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--replace-display-manager", action="store_true")
    args = parser.parse_args(argv)
    manager = GreetdSystemManager(args.repo, etc_root=args.etc_root, state_root=args.state_root, backup_root=args.backup_root)
    try:
        result = manager.plan() if args.action == "plan" else manager.install(
            replace_existing=args.replace_existing,
            replace_display_manager=args.replace_display_manager,
        ) if args.action == "install" else manager.uninstall()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
