#!/usr/bin/env python3
"""Feed visible Niri floating-window rectangles to slurp; retain freeform pick."""

from __future__ import annotations

import json
import subprocess
import sys


def niri_json(command: str):
    result = subprocess.run(
        ["niri", "msg", "--json", command],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def rectangles() -> list[str]:
    windows = niri_json("windows")
    workspaces = niri_json("workspaces")
    outputs = niri_json("outputs")

    active_output_by_workspace = {
        ws["id"]: ws["output"]
        for ws in workspaces
        if ws.get("is_active") and ws.get("output")
    }
    rects: list[str] = []
    for window in windows:
        layout = window.get("layout") or {}
        tile_pos = layout.get("tile_pos_in_workspace_view")
        size = layout.get("window_size")
        output_name = active_output_by_workspace.get(window.get("workspace_id"))
        output = outputs.get(output_name, {}) if output_name else {}
        logical = output.get("logical") or {}
        if (
            tile_pos is None
            or not size
            or len(size) != 2
            or not logical
            or size[0] <= 0
            or size[1] <= 0
        ):
            # Niri 26.04 reports viewport coordinates only for floating windows.
            continue

        offset = layout.get("window_offset_in_tile") or [0, 0]
        x = logical["x"] + tile_pos[0] + offset[0]
        y = logical["y"] + tile_pos[1] + offset[1]
        rects.append(f"{float(x):g},{float(y):g} {float(size[0]):g}x{float(size[1]):g}")
    return rects


def main() -> int:
    try:
        rects = rectangles()
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as exc:
        print(f"Sparrow recorder: Niri window geometry unavailable ({exc}); region picking remains available.", file=sys.stderr)
        rects = []

    if sys.argv[1:] == ["--print-rectangles"]:
        print("\n".join(rects))
        return 0

    try:
        result = subprocess.run(
            ["slurp", "-f", "%wx%h+%x+%y"],
            input="\n".join(rects) + ("\n" if rects else ""),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"Sparrow recorder: could not start slurp: {exc}", file=sys.stderr)
        return 127

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
