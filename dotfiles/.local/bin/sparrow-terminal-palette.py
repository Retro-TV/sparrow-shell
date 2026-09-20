#!/usr/bin/env python3
"""Render terminal colors not covered by Kitty/Ghostty's native formats."""

import json
from pathlib import Path


home = Path.home()
cache = home / ".cache/ricelin"
colors = json.loads((cache / "colors.json").read_text())
palette = {}
for line in (cache / "ghostty-colors").read_text().splitlines():
    if line.startswith("palette = "):
        key, value = line.split("=", 2)[1:]
        palette[int(key)] = value.lstrip("#")

primary = colors["primary"].lstrip("#")
on_primary = colors["on_primary_container"].lstrip("#")
bg = palette.get(0, "14151a")
fg = palette.get(7, "a8aab1")

foot = [
    "[colors-dark]",
    "alpha=0.88",
    f"background={bg}",
    f"foreground={fg}",
    f"cursor={primary} {bg}",
    f"selection-background={palette.get(2, bg)}",
    f"selection-foreground={fg}",
]
foot += [f"regular{i}={palette.get(i, fg)}" for i in range(8)]
bright = [fg, primary, on_primary, on_primary, primary, on_primary, primary, fg]
foot += [f"bright{i}={value}" for i, value in enumerate(bright)]
(cache / "foot-colors").write_text("\n".join(foot) + "\n")

# Starship deliberately stays as a tracked, static layout. It references the
# extended ANSI slots generated for each terminal, so wallpaper changes recolor
# its filled segments without rewriting the prompt structure or spacing.
