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


def monitor_identity(block: str) -> tuple[str, str]:
    """Return the EDID model and DRM connector from one ddcutil detect block."""
    model_match = re.search(r"^[ \t]*Model:[ \t]*(.*?)[ \t]*$", block, re.MULTILINE)
    connector_match = re.search(
        r"^[ \t]*DRM connector:[ \t]+card\d+-(\S+)[ \t]*$", block, re.MULTILINE
    )
    model = " ".join(model_match.group(1).split()) if model_match else ""
    connector = connector_match.group(1) if connector_match else ""
    if model.lower() in {"unknown", "n/a", "none", "unspecified"}:
        model = ""
    return model, connector


def label_monitors(monitors: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    """Assign useful EDID labels, then connector or stable display-number fallbacks."""
    ordered = sorted(
        monitors,
        key=lambda item: (str(item.get("connector", "")), str(item["bus"])),
    )
    labels: list[str] = []
    for index, monitor in enumerate(ordered, start=1):
        model = str(monitor.get("model", "")).strip()
        connector = str(monitor.get("connector", "")).strip()
        labels.append(model or connector or f"Display {index}")

    totals = {label: labels.count(label) for label in labels}
    seen: dict[str, int] = {}
    result = []
    for monitor, label in zip(ordered, labels):
        if totals[label] > 1:
            seen[label] = seen.get(label, 0) + 1
            label = f"{label} · {seen[label]}"
        result.append({
            "bus": monitor["bus"],
            "label": label,
            "brightness": monitor["brightness"],
        })
    return result


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
            ["ddcutil", "detect"],
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
        model, connector = monitor_identity(block)
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
            "model": model,
            "connector": connector,
            "brightness": brightness,
        })
    return label_monitors(monitors)


if __name__ == "__main__":
    print(json.dumps(detect_monitors()))
