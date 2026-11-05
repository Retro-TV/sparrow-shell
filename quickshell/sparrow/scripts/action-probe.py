#!/usr/bin/env python3
"""Passive action prerequisites and consistent state reads. Never creates files."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

MAX_STATE_BYTES = 1024 * 1024


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def media_fingerprint(path):
    if not path:
        return None
    try:
        info = Path(path).stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    return hashlib.sha256(repr(stamp(info)).encode()).hexdigest()


@contextmanager
def wallpaper_read_lock(state):
    """Share the existing writer lock without creating it or changing its bytes."""
    path = state / "wallpaper.lock"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        fd = None
    try:
        if fd is not None:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("Wallpaper lock is not a regular file")
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Wallpaper writer is active; retry after it completes") from exc
        yield
        if fd is None:
            if path.exists():
                raise ValueError("Wallpaper writer appeared during inspection")
        elif stamp(os.fstat(fd)) != stamp(path.stat(follow_symlinks=False)):
            raise ValueError("Wallpaper lock changed during inspection")
    finally:
        if fd is not None:
            os.close(fd)


def read_state(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        return b"", None
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Action state must be a regular file")
        data = stream.read(MAX_STATE_BYTES + 1)
        if len(data) > MAX_STATE_BYTES:
            raise ValueError("Action state exceeds size limit")
        if stamp(before) != stamp(os.fstat(stream.fileno())):
            raise ValueError("Action state changed during inspection")
        return data, stamp(before)


def probe(request, environ=os.environ, which=shutil.which):
    if not isinstance(request, dict):
        return {"supported": False, "message": "Invalid probe request"}
    home = Path(environ.get("HOME") or str(Path.home()))
    state = Path(environ.get("XDG_STATE_HOME") or str(home / ".local/state")) / "sparrow-shell"
    kind = request.get("type")
    if kind not in ("wallpaper.output", "appearance.mode", "recovery"):
        return {"supported": False, "message": "Unsupported probe"}
    with wallpaper_read_lock(state):
        if kind == "recovery":
            result = {"supported": True, "safe": True, "message": "Wallpaper writer lock is idle"}
        else:
            result = inspect_settings(request, state, which)
    return result


def inspect_settings(request, state, which):
    kind = request["type"]
    params = request.get("params", {})
    snapshots = {name: read_state(state / name) for name in ("wallpaper", "wallpaper-map", "flags.json")}
    global_path = snapshots["wallpaper"][0].decode().strip()
    mapping = {}
    for line in snapshots["wallpaper-map"][0].decode().splitlines():
        if "\t" not in line:
            raise ValueError("Malformed wallpaper map")
        output, path = line.split("\t", 1)
        if output in mapping:
            raise ValueError("Ambiguous duplicate output in wallpaper map")
        mapping[output] = path
    path = params.get("value") if kind == "wallpaper.output" else global_path
    if not isinstance(path, str) or not Path(path).is_file() or not os.access(path, os.R_OK):
        return {"supported": False, "message": "Wallpaper file missing or unreadable"}
    if Path(path).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mkv", ".mov"):
        return {"supported": False, "message": "Unsupported wallpaper format"}
    required = ["bash", "python3", "jq", "matugen", "niri"]
    if kind == "wallpaper.output":
        required += ["awww"]
    # Recoloring a video also extracts a still frame.
    if Path(path).suffix.lower() in (".gif", ".mp4", ".webm", ".mkv", ".mov"):
        required += ["ffmpeg"]
        if kind == "wallpaper.output":
            required += ["mpvpaper"]
    missing = [name for name in required if not which(name)]
    if missing:
        return {"supported": False, "message": "Missing prerequisites: " + ", ".join(missing)}
    value = mapping.get(request.get("output"), global_path)
    current_fingerprint = media_fingerprint(value)
    target_fingerprint = media_fingerprint(path) if kind == "wallpaper.output" else None
    digest = hashlib.sha256()
    for name, (data, signature) in snapshots.items():
        # Flags have a QML generation of their own; unrelated flag edits must not
        # invalidate a wallpaper lease. Still require a consistent read below.
        if name != "flags.json":
            digest.update(repr(signature).encode())
            digest.update(data)
        try:
            after = stamp((state / name).stat(follow_symlinks=False))
        except FileNotFoundError:
            after = None
        if signature != after:
            raise ValueError("Action state changed during inspection")
    digest.update(str(current_fingerprint).encode())
    result = {"supported": True, "value": value, "revision": digest.hexdigest()}
    if kind == "wallpaper.output":
        result.update(valueFingerprint=current_fingerprint, targetFingerprint=target_fingerprint)
    if kind == "appearance.mode":
        saved_flags = json.loads(snapshots["flags.json"][0] or "{}")
        if not isinstance(saved_flags, dict):
            raise ValueError("Flags state must be an object")
        result["persistedMode"] = saved_flags.get("appearanceMode", "auto")
        result["persistedPaletteMode"] = saved_flags.get("paletteMode", "dynamic")
    return result


def main():
    try:
        print(json.dumps(probe(json.load(sys.stdin))))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(json.dumps({"supported": False, "safe": False, "message": str(exc)}))


if __name__ == "__main__":
    main()
