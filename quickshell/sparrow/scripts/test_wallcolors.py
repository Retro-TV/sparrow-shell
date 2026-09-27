import sys
import tempfile
import unittest
import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import wallcolors


class WallpaperPaletteSelectionTests(unittest.TestCase):
    def make_image(self, blocks, size=(240, 120)):
        image = Image.new("RGB", size, blocks[0][0])
        draw = ImageDraw.Draw(image)
        x = 0
        for color, fraction in blocks:
            next_x = min(size[0], round(x + size[0] * fraction))
            draw.rectangle((x, 0, max(x, next_x - 1), size[1] - 1), fill=color)
            x = next_x
        with tempfile.NamedTemporaryFile(suffix=".png") as stream:
            image.save(stream.name)
            return wallcolors.candidates_from_colors(
                stream.name, [color for color, _ in blocks]
            )

    def hue_gap(self, first, second):
        return min(abs(first - second) % 360, 360 - abs(first - second) % 360)

    def test_black_red_stays_red_for_every_style(self):
        extraction = self.make_image([("#050505", 0.72), ("#d52331", 0.28)])
        self.assertGreater(extraction["chromatic_coverage"], 0.20)
        for style in wallcolors.PALETTE_STYLES:
            result = wallcolors.choose_seed(extraction, style)
            seed_hue = wallcolors._lab_hue(wallcolors.rgb_to_oklab(
                tuple(int(result["seed"][i:i + 2], 16) for i in (1, 3, 5))))
            self.assertLess(self.hue_gap(seed_hue, 0), 30, (style, result))

    def test_blue_green_wallpaper_exposes_real_alternate(self):
        extraction = self.make_image([
            ("#126be0", 0.40), ("#218446", 0.40), ("#f6f6f2", 0.20),
        ])
        tonal = wallcolors.choose_seed(extraction, "tonal")
        alternate = wallcolors.choose_seed(extraction, "alternate")
        self.assertTrue(alternate["used_alternate"])
        self.assertGreater(self.hue_gap(
            wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
                int(tonal["seed"][i:i + 2], 16) for i in (1, 3, 5)))),
            wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
                int(alternate["seed"][i:i + 2], 16) for i in (1, 3, 5)))),
        ), 28)

    def test_neutral_wallpaper_does_not_invent_a_hue(self):
        extraction = self.make_image([
            ("#111111", 0.25), ("#777777", 0.45), ("#eeeeee", 0.30),
        ])
        self.assertEqual(extraction["candidates"], [])
        self.assertEqual(wallcolors.available_styles(extraction), ["tonal"])
        for style in wallcolors.PALETTE_STYLES:
            self.assertEqual(wallcolors.choose_seed(extraction, style)["seed"], "#787878")

    def test_lock_foreground_recommendation_tracks_sampled_wallpaper_luminance(self):
        dark = self.make_image([("#101114", 1.0)])
        bright = self.make_image([("#f4f3ef", 1.0)])
        vivid_yellow = self.make_image([("#e8bd16", 1.0)])

        self.assertLess(dark["mean_luminance"], wallcolors.LOCK_DARK_FOREGROUND_THRESHOLD)
        self.assertEqual(wallcolors.recommended_lock_foreground(dark["mean_luminance"]), "light")
        self.assertGreater(bright["mean_luminance"], wallcolors.LOCK_DARK_FOREGROUND_THRESHOLD)
        self.assertEqual(wallcolors.recommended_lock_foreground(bright["mean_luminance"]), "dark")
        self.assertEqual(wallcolors.recommended_lock_foreground(vivid_yellow["mean_luminance"]), "dark")

    def test_tiny_colored_object_does_not_recolor_black_wallpaper(self):
        extraction = self.make_image([("#080808", 0.985), ("#00e5ff", 0.015)])
        self.assertLess(extraction["chromatic_coverage"], 0.05)
        self.assertEqual(wallcolors.choose_seed(extraction, "vibrant")["seed"], "#787878")
        self.assertEqual(wallcolors.available_styles(extraction), ["tonal"])

    def test_black_red_has_no_fabricated_alternate_and_stays_red(self):
        extraction = self.make_image([("#050505", 0.72), ("#d52331", 0.28)])
        self.assertEqual(wallcolors.available_styles(extraction), ["tonal", "vibrant"])
        for style in ("tonal", "vibrant", "alternate"):
            result = wallcolors.choose_seed(extraction, style)
            lab = wallcolors.rgb_to_oklab(tuple(
                int(result["seed"][i:i + 2], 16) for i in (1, 3, 5)))
            self.assertLess(self.hue_gap(wallcolors._lab_hue(lab), 0), 30)
        self.assertEqual(wallcolors.choose_seed(extraction, "alternate")["style"], "vibrant")

    def test_palette_treatments_are_distinct_without_hue_rotation(self):
        extraction = self.make_image([("#d52331", 0.55), ("#050505", 0.45)])
        tonal = wallcolors.choose_seed(extraction, "tonal")
        vibrant = wallcolors.choose_seed(extraction, "vibrant")
        self.assertEqual(wallcolors.material_scheme("tonal", True), "scheme-tonal-spot")
        self.assertEqual(wallcolors.material_scheme("vibrant", True), "scheme-content")
        self.assertNotEqual(wallcolors.surface_tones("tonal"), wallcolors.surface_tones("vibrant"))
        tonal_hue = wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
            int(tonal["seed"][i:i + 2], 16) for i in (1, 3, 5))))
        vibrant_hue = wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
            int(vibrant["seed"][i:i + 2], 16) for i in (1, 3, 5))))
        self.assertLess(self.hue_gap(tonal_hue, vibrant_hue), 30)

    def test_limited_color_on_white_remains_available(self):
        extraction = self.make_image([("#ffffff", 0.82), ("#c21873", 0.18)])
        result = wallcolors.choose_seed(extraction, "tonal")
        self.assertTrue(result["chromatic"])
        self.assertLess(self.hue_gap(
            wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
                int(result["seed"][i:i + 2], 16) for i in (1, 3, 5)))),
            330,
        ), 32)

    def test_warm_and_purple_wallpapers_keep_their_families(self):
        cases = (
            ([ ("#1a1008", 0.30), ("#ed8a16", 0.38), ("#f2d54d", 0.32) ], 35, 110),
            ([ ("#160c20", 0.28), ("#7730a0", 0.38), ("#df579b", 0.34) ], 280, 355),
        )
        for blocks, hue_min, hue_max in cases:
            extraction = self.make_image(blocks)
            for style in wallcolors.PALETTE_STYLES:
                result = wallcolors.choose_seed(extraction, style)
                if not result["chromatic"]:
                    continue
                seed_hue = wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
                    int(result["seed"][i:i + 2], 16) for i in (1, 3, 5))))
                self.assertTrue(hue_min <= seed_hue <= hue_max, (style, seed_hue, result))

    def test_colorful_image_styles_are_all_image_derived(self):
        extraction = self.make_image([
            ("#d72a30", 0.25), ("#2374db", 0.25),
            ("#1d9a57", 0.25), ("#e8bb2d", 0.25),
        ])
        self.assertGreaterEqual(len(extraction["candidates"]), 3)
        source_hues = [candidate["hue"] for candidate in extraction["candidates"]]
        for style in wallcolors.PALETTE_STYLES:
            result = wallcolors.choose_seed(extraction, style)
            seed_hue = wallcolors._lab_hue(wallcolors.rgb_to_oklab(tuple(
                int(result["seed"][i:i + 2], 16) for i in (1, 3, 5))))
            self.assertLess(min(self.hue_gap(seed_hue, hue) for hue in source_hues), 12)

    def test_legacy_style_names_normalize(self):
        self.assertEqual(wallcolors.canonical_style("scheme-tonal-spot"), "tonal")
        self.assertEqual(wallcolors.canonical_style("scheme-expressive"), "vibrant")
        self.assertEqual(wallcolors.canonical_style("scheme-fruit-salad"), "alternate")
        self.assertEqual(wallcolors.canonical_style("expressive"), "vibrant")
        self.assertEqual(wallcolors.canonical_style("fruit"), "alternate")
        self.assertEqual(wallcolors.canonical_style("fidelity"), "tonal")
        with self.assertRaises(ValueError):
            wallcolors.canonical_style("scheme-rainbow")

    @unittest.skipUnless(shutil.which("matugen"), "Matugen is not installed")
    def test_isolated_generation_keeps_all_consumer_outputs_in_sync(self):
        theme_candidates = (
            Path.home() / ".local/share/themes/adw-gtk3/gtk-3.0/gtk-dark.css",
            Path("/usr/share/themes/adw-gtk3/gtk-3.0/gtk-dark.css"),
        )
        source_theme = next((path for path in theme_candidates if path.is_file()), None)
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
                "XDG_CACHE_HOME": str(cache_home),
                "XDG_CONFIG_HOME": str(config_home),
                "XDG_DATA_HOME": str(data_home),
            }), mock.patch.object(wallcolors.sys, "argv", [
                "wallcolors.py", str(image_path), "--style", "vibrant",
            ]), mock.patch.object(wallcolors.subprocess, "run", side_effect=isolated_run):
                with mock.patch.object(wallcolors, "CACHE", cache_home / "sparrow-shell"):
                    wallcolors.main()

            palette = json.loads((cache_home / "sparrow-shell/palette.json").read_text())
            kitty = (config_home / "kitty/sparrow-colors.conf").read_text()
            gtk = (data_home / "themes/Sparrow/gtk-3.0/gtk-dark.css").read_text()
            icon = (data_home / "icons/Sparrow/scalable/places/folder.svg").read_text()
            self.assertIn("terminal", palette)
            self.assertIn("wallpaper_luminance", palette)
            self.assertEqual(palette["recommended_lock_foreground"], "light")
            self.assertIn(f"background {palette['terminal']['background']}", kitty)
            self.assertIn(f"color4 {palette['terminal']['ansi'][4]}", kitty)
            self.assertIn(f"@define-color window_bg_color {palette['background']};", gtk)
            self.assertIn(palette["primary_container"], icon)
            self.assertEqual(len(captured_kdl), 1)
            self.assertIn(f'active-color "{palette["primary"]}"', captured_kdl[0])
            self.assertIn(f'inactive-color "{palette["outline_variant"]}"', captured_kdl[0])


if __name__ == "__main__":
    unittest.main()
