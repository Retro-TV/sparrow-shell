#!/usr/bin/env python3
"""Safely copy legacy Ricelin state into Sparrow's canonical XDG locations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


def xdg_dir(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable)
    return Path(value).expanduser() if value else Path.home() / fallback


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_copy(source: Path, destination: Path, expected_hash: str) -> None:
    """Create destination atomically without replacing an existing file."""
    source_stat = source.stat()
    if not stat.S_ISREG(source_stat.st_mode):
        raise RuntimeError(f"not a regular file: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as incoming, os.fdopen(descriptor, "wb") as outgoing:
            while True:
                chunk = incoming.read(1024 * 1024)
                if not chunk:
                    break
                outgoing.write(chunk)
            outgoing.flush()
            os.fchmod(outgoing.fileno(), stat.S_IMODE(source_stat.st_mode))
            os.fsync(outgoing.fileno())

        os.utime(temporary, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        if digest(temporary) != expected_hash or digest(source) != expected_hash:
            raise RuntimeError(f"source changed or copy verification failed: {source}")

        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise
        temporary.unlink()
        fsync_directory(destination.parent)

        if digest(destination) != expected_hash:
            raise RuntimeError(f"destination verification failed: {destination}")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def migrate(source: Path, destination: Path, backup: Path) -> bool:
    if not source.exists():
        return False

    source_hash = digest(source)
    if backup.exists():
        if digest(backup) != source_hash:
            raise RuntimeError(f"preserved backup differs from current source: {backup}")
    else:
        atomic_copy(source, backup, source_hash)
        print(f"backup created: {backup} sha256={source_hash}")

    if destination.exists():
        print(
            f"destination preserved (not overwritten): {destination} "
            f"sha256={digest(destination)}; legacy copy remains at {source} "
            f"sha256={source_hash}"
        )
        return False

    try:
        atomic_copy(source, destination, source_hash)
    except FileExistsError:
        print(f"destination appeared concurrently; preserved without overwrite: {destination}")
        return False

    print(f"migrated: {source} -> {destination} sha256={source_hash}")
    return True


def initialize_onboarding_state(state_root: Path) -> bool:
    """Create the one-time onboarding marker without touching flags.json."""
    destination = state_root / "onboarding.json"
    existing_state_files = (
        "flags.json",
        "events.json",
        "launcher-usage.json",
        "nvibrant-value",
        "wallpaper",
        "wallpaper-map",
        "wallpaper-dir",
        "wallpaper-bag",
        "wallpaper-still.png",
    )
    established = any((state_root / name).exists() for name in existing_state_files)
    established = established or any(state_root.glob("mpvpaper-*.log"))
    transaction_root = state_root / "niri-config-transactions"
    if transaction_root.exists():
        established = established or any(path.is_file() for path in transaction_root.iterdir())

    payload = json.dumps(
        {"completed": established, "autoShown": established},
        indent=2,
        sort_keys=True,
    ) + "\n"
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False

    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_directory(state_root)
    print(f"initialized Getting Started state: {destination} (existing={established})")
    return True


def migrate_palette_preferences(flags_path: Path) -> bool:
    """Translate the experimental palette controls without touching other flags."""
    if not flags_path.is_file():
        return False
    try:
        flags = json.loads(flags_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"could not read Sparrow flags for palette migration: {error}") from error
    if not isinstance(flags, dict) or int(flags.get("paletteSettingsVersion", 0) or 0) >= 1:
        return False

    old_source = str(flags.get("paletteMode", "dynamic")).lower()
    old_style = str(flags.get("paletteVariant", "tonal")).strip().lower()
    styles = {
        "auto": "auto", "monochrome": "monochrome",
        "tonal": "tonal", "scheme-tonal-spot": "tonal", "neutral": "tonal",
        "scheme-neutral": "tonal", "fidelity": "tonal", "scheme-fidelity": "tonal",
        "vibrant": "content", "scheme-vibrant": "content", "content": "content",
        "scheme-content": "content", "alternate": "auto", "fruit": "auto",
        "scheme-fruit-salad": "auto", "expressive": "auto", "scheme-expressive": "auto",
    }
    flags["paletteVariant"] = styles.get(old_style, "auto")
    if old_source not in ("static", "dynamic"):
        flags["paletteMode"] = "dynamic"
    old_mode = str(flags.get("appearanceMode", "")).lower()
    if old_mode not in ("auto", "dark", "light"):
        # Legacy wallpaper-driven palettes were always Matugen dark. Manual
        # hue users retain their explicit tone choice when possible.
        old_mode = "light" if old_source == "manual" and flags.get("manualDark") is False else "dark"
    flags["appearanceMode"] = old_mode
    for obsolete in ("manualHue", "manualDark", "manualSat"):
        flags.pop(obsolete, None)
    flags["paletteSettingsVersion"] = 1

    source_stat = flags_path.stat()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{flags_path.name}.", suffix=".tmp", dir=flags_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(flags, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fchmod(stream.fileno(), stat.S_IMODE(source_stat.st_mode))
            os.fsync(stream.fileno())
        os.replace(temporary, flags_path)
        fsync_directory(flags_path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"migrated palette preferences: source={flags['paletteMode']} "
        f"style={flags['paletteVariant']} mode={flags['appearanceMode']}"
    )
    return True


def main() -> int:
    state_home = xdg_dir("XDG_STATE_HOME", ".local/state")
    cache_home = xdg_dir("XDG_CACHE_HOME", ".cache")
    state_root = state_home / "sparrow-shell"
    state_root.mkdir(parents=True, exist_ok=True, mode=0o755)
    (cache_home / "sparrow-shell").mkdir(parents=True, exist_ok=True, mode=0o755)
    backup_root = state_root / "migration-backups" / "ricelin-before-migration-1"
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_root.parent, 0o700)
    os.chmod(backup_root, 0o700)
    lock_path = state_root / ".state-migration.lock"

    migrations = [
        (state_home / "ricelin/flags.json", state_root / "flags.json", backup_root / "state/flags.json"),
        (state_home / "ricelin/events.json", state_root / "events.json", backup_root / "state/events.json"),
        (
            state_home / "ricelin/launcher-usage.json",
            state_root / "launcher-usage.json",
            backup_root / "state/launcher-usage.json",
        ),
        (
            state_home / "ricelin/nvibrant-value",
            state_root / "nvibrant-value",
            backup_root / "state/nvibrant-value",
        ),
        (
            cache_home / "ricelin/weather-loc.json",
            cache_home / "sparrow-shell/weather-loc.json",
            backup_root / "cache/weather-loc.json",
        ),
    ]
    for _, _, backup in migrations:
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(backup.parent, 0o700)

    try:
        with lock_path.open("a+b") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            for source, destination, backup in migrations:
                migrate(source, destination, backup)
            migrate_palette_preferences(state_root / "flags.json")
            initialize_onboarding_state(state_root)
    except (OSError, RuntimeError) as error:
        print(f"state migration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
