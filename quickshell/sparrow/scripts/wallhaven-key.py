#!/usr/bin/env python3
"""Store the optional Wallhaven API key in private per-user state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat
import sys


def key_path() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "sparrow-shell" / "secrets" / "wallhaven-api-key"


def read_key() -> str:
    path = key_path()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ""
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise PermissionError("Wallhaven API key file must be a private user-owned file")
    return path.read_text(encoding="utf-8").strip()


def save_key(value: str) -> None:
    key = value.strip()
    if not key or len(key) > 512 or any(ord(char) < 0x21 or ord(char) == 0x7f for char in key):
        raise ValueError("Invalid Wallhaven API key")
    directory = key_path().parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    destination = key_path()
    if destination.is_symlink():
        raise PermissionError("Refusing to replace a symlink at the Wallhaven API key path")
    temporary = directory / (".wallhaven-api-key-" + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(key + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if command == "status":
            configured = bool(read_key())
            print(json.dumps({"configured": configured}))
        elif command == "set":
            save_key(sys.stdin.readline(514))
            print(json.dumps({"configured": True}))
        elif command == "remove":
            path = key_path()
            if path.is_symlink():
                path.unlink()
            else:
                path.unlink(missing_ok=True)
            print(json.dumps({"configured": False}))
        else:
            return 2
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({"ok": False, "error": "Could not update Wallhaven API key"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
