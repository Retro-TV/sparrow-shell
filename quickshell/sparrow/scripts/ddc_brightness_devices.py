#!/usr/bin/env python3
"""List only DDC displays with a readable brightness control."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable


def parse_brightness(text: str) -> int:
    match = re.search(r"\bC\s+(\d+)\s+", text)
    return int(match.group(1)) if match else -1


def backlight_connectors(root: Path = Path("/sys/class/backlight")) -> set[str]:
    """Resolve internal backlights to DRM connector names when sysfs exposes them."""
    connectors: set[str] = set()
    try:
        entries = list(root.iterdir())
    except OSError:
        return connectors
    for entry in entries:
        try:
            parts = entry.resolve().parts
        except OSError:
            continue
        for part in parts:
            match = re.fullmatch(r"card\d+-(.+)", part)
            if match:
                connectors.add(match.group(1))
    return connectors


def detect_monitors(
    *,
    backlight_root: Path = Path("/sys/class/backlight"),
    run: Callable = subprocess.run,
) -> list[dict[str, str | int]]:
    """Filter detect candidates through the same VCP-10 read used by the fader.

    If a detected connector has a sysfs backlight, brightnessctl owns that
    display instead; exposing a second DDC fader for it creates a duplicate.
    """
    try:
        detected = run(
            ["ddcutil", "detect", "--brief"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if detected.returncode:
        return []

    internal_connectors = backlight_connectors(backlight_root)
    monitors: list[dict[str, str | int]] = []
    seen_buses: set[str] = set()
    for block in re.split(r"\bDisplay\s+\d+", detected.stdout):
        bus_match = re.search(r"I2C bus:\s+/dev/i2c-(\d+)", block)
        if not bus_match:
            continue
        bus = bus_match.group(1)
        if bus in seen_buses:
            continue
        seen_buses.add(bus)
        connector_match = re.search(r"DRM connector:\s+card\d+-(\S+)", block)
        connector = connector_match.group(1) if connector_match else ""
        if connector and connector in internal_connectors:
            continue
        try:
            result = run(
                ["ddcutil", "getvcp", "10", "--brief", "--bus", bus],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        brightness = parse_brightness(result.stdout) if result.returncode == 0 else -1
        if brightness < 0:
            continue
        monitors.append({
            "bus": bus,
            "label": connector or f"BUS {bus}",
            "brightness": brightness,
        })
    return monitors


if __name__ == "__main__":
    print(json.dumps(detect_monitors()))
