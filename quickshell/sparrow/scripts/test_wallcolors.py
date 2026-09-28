#!/usr/bin/env python3
"""Behavior tests for Sparrow's Matugen-backed palette path."""

from __future__ import annotations

import colorsys
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import wallcolors

MIGRATION_PATH = Path(__file__).with_name("migrate-state.py")
MIGRATION_SPEC = importlib.util.spec_from_file_location("sparrow_migrate_state", MIGRATION_PATH)
migrate_state = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(migrate_state)


class PaletteModelTests(unittest.TestCase):
    def test_niri_generated_colors_include_recent_windows_matugen_roles(self):
        rendered = wallcolors.render_niri_colors({
            "primary": "#aabbcc",
            "outline_variant": "#334455",
            "error": "#dd2233",
        })
        self.assertIn('active-color "#aabbcc"', rendered)
        self.assertIn('inactive-color "#334455"', rendered)
        self.assertIn('urgent-color "#dd2233"', rendered)
        self.assertIn("recent-windows {", rendered)

    def test_legacy_palette_style_migration_is_deterministic(self):
        expected = {
            "tonal": "tonal", "scheme-tonal-spot": "tonal", "fidelity": "tonal",
            "vibrant": "content", "scheme-content": "content",
            "alternate": "auto", "fruit": "auto", "expressive": "auto",
        }
        for old, new in expected.items():
            self.assertEqual(wallcolors.canonical_style(old), new)

    def test_mode_auto_is_separate_from_palette_style(self):
        self.assertEqual(wallcolors.canonical_style("tonal"), "tonal")
        self.assertEqual(wallcolors.canonical_mode("auto"), "auto")
        self.assertEqual(wallcolors.canonical_mode("light"), "light")

    def test_fresh_flags_use_requested_palette_defaults(self):
        flags_source = Path(__file__).parents[1] / "Singletons/Flags.qml"
        source = flags_source.read_text()
        for default in (
            'property string paletteMode: "dynamic"',
            'property string paletteVariant: "auto"',
            'property string appearanceMode: "auto"',
            "property int paletteSettingsVersion: 1",
        ):
            self.assertIn(default, source)

    def test_adw_gtk3_system_package_is_preferred_to_user_data_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "system/adw-gtk3"
            data = root / "data"
            system_css = system / "gtk-3.0/gtk-dark.css"
            user_css = data / "themes/adw-gtk3/gtk-3.0/gtk-dark.css"
            system_css.parent.mkdir(parents=True)
            user_css.parent.mkdir(parents=True)
            system_css.touch()
            user_css.touch()
            self.assertEqual(
                wallcolors.find_adw_gtk3_stylesheet("dark", data, system), system_css,
            )
            system_css.unlink()
            self.assertEqual(
                wallcolors.find_adw_gtk3_stylesheet("dark", data, system), user_css,
            )

    def test_palette_state_migration_is_safe_and_idempotent(self):
        cases = (
            (
                {"paletteMode": "manual", "paletteVariant": "vibrant",
                 "manualHue": 26, "manualDark": False, "manualSat": 0.7,
                 "dnd": True},
                {"paletteMode": "dynamic", "paletteVariant": "content",
                 "appearanceMode": "light", "dnd": True},
            ),
            (
                {"paletteMode": "static", "paletteVariant": "monochrome"},
                {"paletteMode": "static", "paletteVariant": "monochrome",
                 "appearanceMode": "dark"},
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flags.json"
            for old, expected in cases:
                path.write_text(json.dumps(old))
                self.assertTrue(migrate_state.migrate_palette_preferences(path))
                migrated = json.loads(path.read_text())
                for key, value in expected.items():
                    self.assertEqual(migrated[key], value)
                self.assertEqual(migrated["paletteSettingsVersion"], 1)
                for obsolete in ("manualHue", "manualDark", "manualSat"):
                    self.assertNotIn(obsolete, migrated)
                stable = path.read_text()
                self.assertFalse(migrate_state.migrate_palette_preferences(path))
                self.assertEqual(path.read_text(), stable)

    def test_wallpaper_luminance_and_lock_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dark = root / "dark.png"
            bright = root / "bright.png"
            Image.new("RGB", (16, 16), "#08090b").save(dark)
            Image.new("RGB", (16, 16), "#f5f4ef").save(bright)
            dark_luminance = wallcolors.sample_wallpaper_luminance(dark)
            bright_luminance = wallcolors.sample_wallpaper_luminance(bright)
        self.assertLess(dark_luminance, bright_luminance)
        self.assertEqual(wallcolors.recommended_lock_foreground(dark_luminance), "light")
        self.assertEqual(wallcolors.recommended_lock_foreground(bright_luminance), "dark")

    @unittest.skipUnless(shutil.which("matugen"), "Matugen is not installed")
    def test_full_wallpaper_mode_and_style_matrix(self):
        fixtures = {
            "black-red": [("#050505", .60), ("#d52331", .40)],
            "blue-green-white": [("#1757d5", .34), ("#14a46f", .33), ("#f2f5f2", .33)],
            "orange-yellow": [("#dc5c12", .54), ("#ffd54a", .46)],
            "purple-pink": [("#6422a8", .52), ("#ec4b9b", .48)],
            "neutral-grey": [("#282a2d", .25), ("#8b8d90", .50), ("#e5e5e3", .25)],
            "bright": [("#faf8ee", .75), ("#dfd6c2", .25)],
            "dark": [("#060913", .65), ("#161d36", .35)],
            "multicolor": [("#e42b38", .25), ("#1689ec", .25), ("#21a75a", .25), ("#f0cb23", .25)],
        }
        styles = ("auto", "tonal", "content", "monochrome")
        modes = ("auto", "dark", "light")
        with tempfile.TemporaryDirectory(prefix="sparrow-matugen-matrix-") as directory:
            root = Path(directory)
            images = {}
            for name, blocks in fixtures.items():
                image = Image.new("RGB", (256, 160))
                draw, x = ImageDraw.Draw(image), 0
                for color, share in blocks:
                    width = round(256 * share)
                    draw.rectangle((x, 0, min(255, x + width), 159), fill=color)
                    x += width
                images[name] = root / f"{name}.png"
                image.save(images[name])

            outcomes = {}
            for name, image_path in images.items():
                for style in styles:
                    for mode in modes:
                        roles, resolved, effective_style, requested_mode, source = wallcolors.run_matugen(
                            image_path, "dynamic", style, mode,
                        )
                        self.assertIn(resolved, ("dark", "light"))
                        self.assertEqual(effective_style, style)
                        self.assertEqual(requested_mode, mode)
                        self.assertEqual(source, "dynamic")
                        self.assertTrue(set(wallcolors.SEMANTIC_ROLES).issubset(roles))
                        self.assertGreaterEqual(contrast_ratio(roles["on_surface"], roles["surface"]), 4.5)
                        self.assertGreaterEqual(contrast_ratio(roles["on_background"], roles["background"]), 4.5)
                        for family in ("primary", "secondary", "tertiary", "error"):
                            self.assertGreaterEqual(
                                contrast_ratio(roles[f"on_{family}"], roles[family]), 4.5,
                                (name, style, mode, family),
                            )
                            self.assertGreaterEqual(
                                contrast_ratio(roles[f"on_{family}_container"], roles[f"{family}_container"]),
                                4.5, (name, style, mode, family, "container"),
                            )
                        outcomes[(name, style, mode)] = roles

            # Matugen's native smart appearance-mode choice must follow the
            # clear luminance extremes, not the manual style selection.
            self.assertEqual(outcomes[("bright", "auto", "auto")]["background"],
                             outcomes[("bright", "auto", "light")]["background"])
            self.assertEqual(outcomes[("dark", "auto", "auto")]["background"],
                             outcomes[("dark", "auto", "dark")]["background"])

            # Curated chromatic choices stay related to the black/red source.
            for style in ("auto", "tonal", "content"):
                primary = outcomes[("black-red", style, "dark")]["primary"]
                self.assertLess(hue_distance(hue(primary), 0), 35, (style, primary))
            # A deliberately monochrome choice is neutral, not an invented hue.
            mono = outcomes[("black-red", "monochrome", "dark")]["primary"]
            self.assertLess(chroma(mono), 0.04, mono)
            neutral_auto = outcomes[("neutral-grey", "auto", "dark")]
            self.assertLess(chroma(neutral_auto["primary"]), 0.05, neutral_auto["primary"])

            for name in fixtures:
                for style in styles:
                    dark = outcomes[(name, style, "dark")]
                    light = outcomes[(name, style, "light")]
                    self.assertGreater(
                        abs(srgb_luminance(dark["background"]) - srgb_luminance(light["background"])),
                        0.5, (name, style, dark["background"], light["background"]),
                    )
                    self.assertNotEqual(dark["primary"], light["primary"], (name, style))

    @unittest.skipUnless(shutil.which("matugen"), "Matugen is not installed")
    def test_static_palette_is_independent_of_wallpaper(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first.png", Path(directory) / "second.png"
            Image.new("RGB", (20, 20), "#e02030").save(first)
            Image.new("RGB", (20, 20), "#185ee0").save(second)
            first_roles = wallcolors.run_matugen(first, "static", "auto", "auto")[0]
            second_roles = wallcolors.run_matugen(second, "static", "auto", "auto")[0]
        self.assertEqual(first_roles, second_roles)
        self.assertEqual(first_roles["source_color"].lower(), wallcolors.STATIC_SEED)

    @unittest.skipUnless(shutil.which("matugen"), "Matugen is not installed")
    def test_isolated_generation_keeps_consumers_on_one_palette(self):
        gtk_sources = (
            Path("/usr/share/themes/adw-gtk3/gtk-3.0/gtk-dark.css"),
            Path.home() / ".local/share/themes/adw-gtk3/gtk-3.0/gtk-dark.css",
        )
        source_theme = next((path for path in gtk_sources if path.is_file()), None)
        if source_theme is None:
            self.skipTest("adw-gtk3 source theme is not installed")

        with tempfile.TemporaryDirectory(prefix="sparrow-wallcolors-output-") as directory:
            root = Path(directory)
            cache_home, config_home, data_home = (root / name for name in ("cache", "config", "data"))
            (data_home / "themes").mkdir(parents=True)
            (data_home / "themes/adw-gtk3").symlink_to(source_theme.parent.parent)
            image_path = root / "test-wallpaper.png"
            Image.new("RGB", (120, 80), "#cf2935").save(image_path)
            captured_kdl = []
            real_run = subprocess.run

            def isolated_run(command, *args, **kwargs):
                if any(Path(str(part)).name == "niri-config-transaction.py" for part in command):
                    captured_kdl.append(json.loads(kwargs["input"])["content"])
                    return subprocess.CompletedProcess(command, 0, '{"status":"success"}\n', "")
                if command[0] in ("pkill", "gtk-update-icon-cache"):
                    return subprocess.CompletedProcess(command, 0, "", "")
                return real_run(command, *args, **kwargs)

            with mock.patch.dict(os.environ, {
                "XDG_CACHE_HOME": str(cache_home), "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }), mock.patch.object(sys, "argv", [
                "wallcolors.py", str(image_path), "--style", "content", "--mode", "dark",
            ]), mock.patch.object(subprocess, "run", side_effect=isolated_run):
                with mock.patch.object(wallcolors, "CACHE", cache_home / "sparrow-shell"):
                    wallcolors.main()

            palette = json.loads((cache_home / "sparrow-shell/palette.json").read_text())
            kitty = (config_home / "kitty/sparrow-colors.conf").read_text()
            gtk = (data_home / "themes/Sparrow/gtk-3.0/gtk.css").read_text()
            gtk_dark = (data_home / "themes/Sparrow/gtk-3.0/gtk-dark.css").read_text()
            icon = (data_home / "icons/Sparrow/scalable/places/folder.svg").read_text()
            self.assertEqual(palette["theme_source"], "dynamic")
            self.assertEqual(palette["palette_style"], "content")
            self.assertEqual(palette["resolved_mode"], "dark")
            self.assertIn(f"background {palette['terminal']['background']}", kitty)
            self.assertIn(f"color4 {palette['terminal']['ansi'][4]}", kitty)
            self.assertIn(f"@define-color window_bg_color {palette['background']};", gtk)
            self.assertEqual(gtk, gtk_dark)
            self.assertIn(palette["primary_container"], icon)
            self.assertEqual(len(captured_kdl), 1)
            self.assertIn(f'active-color "{palette["primary"]}"', captured_kdl[0])
            self.assertIn(f'inactive-color "{palette["outline_variant"]}"', captured_kdl[0])


def srgb_luminance(color: str) -> float:
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    return wallcolors.relative_luminance(rgb)


def contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((srgb_luminance(first), srgb_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def hue(color: str) -> float:
    rgb = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(*rgb)[0] * 360


def hue_distance(first: float, second: float) -> float:
    delta = abs(first - second) % 360
    return min(delta, 360 - delta)


def chroma(color: str) -> float:
    rgb = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return max(rgb) - min(rgb)


if __name__ == "__main__":
    unittest.main()
