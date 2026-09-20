#!/usr/bin/env python3
"""Small regression test for Sparrow's shared contrast policy."""

import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
source = root / "dotfiles/.config/hypr/scripts/wallcolors.py"
spec = importlib.util.spec_from_file_location("wallcolors", source)
wallcolors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wallcolors)


for surface, foreground in (("#210e0b", "#ffdad4"), ("#e6ebef", "#141a1f")):
    pill = {
        "surface": surface,
        "surface_container_low": surface,
        "surface_container": surface,
        "surface_container_high": surface,
        "surface_container_highest": surface,
        "outline_variant": foreground,
        "primary": foreground,
        "secondary": foreground,
        "tertiary": foreground,
        "primary_container": surface,
        "on_primary_container": foreground,
        "outline": foreground,
        "bright": foreground,
        "subtle": foreground,
        "dim": foreground,
        "cream": foreground,
        "faint": foreground,
        "icon_dim": foreground,
        "tick_rest": foreground,
    }
    pill = wallcolors.normalize_palette(pill)
    base16 = {f"base{i:02x}": "#6b2520" for i in range(16)}
    _, ansi = wallcolors.normalize_terminal_palette(base16, pill)
    assert all(wallcolors.contrast_ratio(color, surface) >= 4.5 for color in ansi[1:])
    assert wallcolors.contrast_ratio(pill["bright"], surface) >= 7.0

print("palette contrast: ok")
