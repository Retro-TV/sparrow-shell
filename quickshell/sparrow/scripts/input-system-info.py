#!/usr/bin/env python3
"""Read-only input-device and installed XKB layout inventory for Sparrow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


INPUT_FLAGS = {
    "keyboard": "ID_INPUT_KEYBOARD",
    "touchpad": "ID_INPUT_TOUCHPAD",
    "mouse": "ID_INPUT_MOUSE",
    "tablet": "ID_INPUT_TABLET",
    "touchscreen": "ID_INPUT_TOUCHSCREEN",
}


def parse_properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key] = value
    return result


def parse_layouts(text: str) -> list[dict[str, str]]:
    layouts: list[dict[str, str]] = []
    in_layouts = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "! layout":
            in_layouts = True
            continue
        if stripped.startswith("!"):
            if in_layouts:
                break
            continue
        if not in_layouts or not stripped or stripped.startswith("#"):
            continue
        code, separator, label = stripped.partition(" ")
        label = label.strip()
        if separator and re.fullmatch(r"[A-Za-z0-9_+-]{1,32}", code) and label:
            layouts.append({"code": code, "label": label})
    return layouts


def load_layouts(paths: list[Path] | None = None) -> list[dict[str, str]]:
    if paths is None:
        roots = [Path(os.environ.get("XKB_CONFIG_ROOT", "/usr/share/X11/xkb")),
                 Path("/usr/local/share/X11/xkb")]
        paths = [root / "rules" / "base.lst" for root in roots]
        paths += [root / "rules" / "evdev.lst" for root in roots]
    for path in paths:
        try:
            layouts = parse_layouts(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
        if layouts:
            return layouts
    return []


def _truthy(properties: dict[str, str], name: str) -> bool:
    return properties.get(name, "").lower() in {"1", "yes", "true"}


def discover_devices(event_paths: list[Path] | None = None, runner=subprocess.run) -> dict[str, bool]:
    if event_paths is None:
        event_paths = sorted(Path("/dev/input").glob("event*"))
    groups: dict[str, set[str]] = {}
    for device in event_paths:
        try:
            result = runner(["udevadm", "info", "--query=property", "--name", str(device)],
                            text=True, capture_output=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        properties = parse_properties(result.stdout)
        fallback_path = re.sub(r"/input/input\d+(?:/event\d+)?$", "", properties.get("DEVPATH", ""))
        identity = (properties.get("ID_PATH_TAG") or properties.get("ID_PATH")
                    or properties.get("ID_SERIAL") or fallback_path or str(device.resolve()))
        kinds = groups.setdefault(identity, set())
        for kind, flag in INPUT_FLAGS.items():
            if _truthy(properties, flag):
                kinds.add(kind)

    found = {kind: False for kind in INPUT_FLAGS}
    for kinds in groups.values():
        for kind in kinds:
            if kind == "mouse" and "touchpad" in kinds:
                continue
            found[kind] = True
    return found


def main() -> int:
    result = {"devices": discover_devices(), "layouts": load_layouts()}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
