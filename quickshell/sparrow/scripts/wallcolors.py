#!/usr/bin/env python3
"""Generate Sparrow's image-derived Material palette and Niri border colors."""
import colorsys
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "sparrow-shell"

PALETTE_STYLES = ("tonal", "vibrant", "alternate")
LEGACY_PALETTE_STYLES = {
    "scheme-tonal-spot": "tonal",
    "scheme-neutral": "tonal",
    "scheme-fidelity": "tonal",
    "neutral": "tonal",
    "fidelity": "tonal",
    "scheme-expressive": "vibrant",
    "scheme-vibrant": "vibrant",
    "expressive": "vibrant",
    "vibrant": "vibrant",
    "scheme-fruit-salad": "alternate",
    "fruit": "alternate",
}


def canonical_style(value):
    value = str(value or "tonal").strip().lower()
    value = LEGACY_PALETTE_STYLES.get(value, value)
    if value not in PALETTE_STYLES:
        raise ValueError(f"unsupported Sparrow palette style: {value}")
    return value


def _linear_channel(value):
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def rgb_to_oklab(rgb):
    """Convert 8-bit sRGB to OKLab for perceptual palette grouping."""
    r, g, b = (_linear_channel(value) for value in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (value ** (1 / 3) for value in (l, m, s))
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def oklab_to_rgb(lab):
    l, a, b = lab
    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = (value ** 3 for value in (l_, m_, s_))
    channels = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    result = []
    for channel in channels:
        channel = max(0.0, min(1.0, channel))
        srgb = 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055
        result.append(round(srgb * 255))
    return tuple(result)


def _lab_hex(lab):
    return "#%02x%02x%02x" % oklab_to_rgb(lab)


def _lab_chroma(lab):
    return math.hypot(lab[1], lab[2])


def _lab_hue(lab):
    return math.degrees(math.atan2(lab[2], lab[1])) % 360


def _hue_distance(first, second):
    distance = abs(first - second) % 360
    return min(distance, 360 - distance)


def _matugen_image_colors(path):
    """Ask Matugen's Material Color Utilities image pipeline for ranked seeds."""
    result = subprocess.run(
        ["matugen", "image", str(path), "--show-source-colors", "--dry-run"],
        check=True, capture_output=True, text=True,
    )
    return list(dict.fromkeys(re.findall(r"#[0-9a-fA-F]{6}", result.stdout)))


def candidates_from_colors(path, source_colors, max_dimension=160):
    """Measure Matugen-ranked seeds against the wallpaper in perceptual space.

    Matugen uses Material Color Utilities' Celebi quantizer and Score ranking.
    Coverage here keeps a tiny accent from becoming a whole-desktop theme and
    lets Sparrow require a genuinely present alternate hue.
    """
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.BOX)
        image = image.quantize(colors=96, method=Image.Quantize.MEDIANCUT).convert("RGB")
        histogram = image.getcolors(max_dimension * max_dimension) or []

    total = sum(count for count, _ in histogram)
    source_labs = []
    for color in source_colors:
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        source_labs.append((color.upper(), rgb_to_oklab(rgb)))

    chromatic_count = 0
    coverage = [0] * len(source_labs)
    for count, rgb in histogram:
        lab = rgb_to_oklab(rgb)
        chroma = _lab_chroma(lab)
        if lab[0] < 0.08 or lab[0] > 0.96 or chroma < 0.045:
            continue
        chromatic_count += count
        if not source_labs:
            continue
        nearest_index, nearest_source = min(
            enumerate(source_labs),
            key=lambda entry: math.dist(lab, entry[1][1]),
        )
        nearest_distance = math.dist(lab, nearest_source[1])
        if nearest_distance <= 0.14:
            coverage[nearest_index] += count

    chromatic_coverage = chromatic_count / max(total, 1)
    candidates = []
    if chromatic_coverage >= 0.05:
        for index, ((color, lab), count) in enumerate(zip(source_labs, coverage)):
            candidate_coverage = count / max(total, 1)
            if candidate_coverage < 0.018:
                continue
            chroma = _lab_chroma(lab)
            chroma_weight = 0.65 + 0.35 * min(chroma / 0.22, 1.0)
            light_weight = 0.7 + 0.3 * max(0.0, 1.0 - abs(lab[0] - 0.58) / 0.58)
            candidates.append({
                "color": color,
                "coverage": candidate_coverage,
                "chroma": chroma,
                "hue": _lab_hue(lab),
                "lab": lab,
                # Keep Material's ranking as a tie-breaker, but let actual
                # image coverage prevent a high-score speck from taking over.
                "score": candidate_coverage * chroma_weight * light_weight
                         + (len(source_labs) - index) * 1e-6,
            })
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {"candidates": candidates, "chromatic_coverage": chromatic_coverage}


def extract_candidates(path, max_dimension=160):
    return candidates_from_colors(path, _matugen_image_colors(path), max_dimension)


def _scale_lab_chroma(lab, factor):
    return (lab[0], lab[1] * factor, lab[2] * factor)


def choose_seed(extraction, style):
    """Select only image-derived seeds; fall back to neutral for near-gray art."""
    style = canonical_style(style)
    candidates = extraction["candidates"]
    if not candidates:
        return {"seed": "#787878", "chromatic": False, "candidate": None,
                "used_alternate": False, "style": "tonal"}

    dominant = candidates[0]
    alternate = next((candidate for candidate in candidates[1:]
                      if candidate["coverage"] >= 0.05
                      and _hue_distance(candidate["hue"], dominant["hue"]) >= 28
                      and math.dist(candidate["lab"], dominant["lab"]) >= 0.10), None)
    vibrant = max(
        (candidate for candidate in candidates
         if candidate["coverage"] >= max(0.03, extraction["chromatic_coverage"] * 0.10)),
        key=lambda candidate: candidate["chroma"] * math.sqrt(candidate["coverage"]),
        default=dominant,
    )

    if style == "tonal":
        selected, chroma_factor, used_alternate = dominant, 0.86, False
    elif style == "vibrant":
        selected, chroma_factor, used_alternate = vibrant, 1.0, False
    elif alternate is not None:
        selected, chroma_factor, used_alternate = alternate, 1.0, True
    else:
        # No distinct secondary hue: use the image's vivid treatment rather
        # than pretending that a slightly desaturated copy is an alternate.
        selected, chroma_factor, used_alternate = vibrant, 1.0, False

    seed = _lab_hex(_scale_lab_chroma(selected["lab"], chroma_factor))
    effective_style = style if (style != "alternate" or used_alternate) else "vibrant"
    return {"seed": seed, "chromatic": True, "candidate": selected,
            "used_alternate": used_alternate, "style": effective_style}


def available_styles(extraction):
    styles = ["tonal"]
    if extraction["candidates"]:
        styles.append("vibrant")
        dominant = extraction["candidates"][0]
        if any(candidate["coverage"] >= 0.05
               and _hue_distance(candidate["hue"], dominant["hue"]) >= 28
               and math.dist(candidate["lab"], dominant["lab"]) >= 0.10
               for candidate in extraction["candidates"][1:]):
            styles.append("alternate")
    return styles


def surface_tones(style):
    """Sparrow dark-surface ramps, expressed as Material tone levels."""
    if style == "tonal":
        return (5, 10, 15, 20, 25, 30)
    return (10, 15, 20, 30, 35, 40)


def material_scheme(style, chromatic):
    if not chromatic:
        return "scheme-monochrome"
    return "scheme-tonal-spot" if style == "tonal" else "scheme-content"
def tint(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h % 1, max(0, min(1, l)), max(0, min(1, s)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def analyze(path):
    with Image.open(path) as source:
        im = source.convert("RGB")
        im.thumbnail((200, 200))
        colors = im.quantize(colors=48, method=Image.Quantize.FASTOCTREE).convert("RGB")
        hist = colors.getcolors(40000) or []
        total = sum(n for n, _ in hist)
        mean_l = sum(n * colorsys.rgb_to_hls(*(c / 255 for c in rgb))[1]
                     for n, rgb in hist) / max(total, 1)
        buckets = {}
        chroma = 0
        for count, rgb in hist:
            h, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
            if sat < .15 or light < .05 or light > .92:
                continue
            chroma += count
            bucket = int(h * 360) // 30 % 12
            slot = buckets.setdefault(bucket, [0.0, None])
            slot[0] += count * sat
            score = count * sat * (1 if .12 < light < .55 else .4)
            if slot[1] is None or score > slot[1][0]:
                slot[1] = (score, h, sat)
    if not buckets or chroma < .08 * total:
        return .09, 0.0, mean_l, False
    winner = max(buckets.values(), key=lambda v: v[0])[1]
    return winner[1], winner[2], mean_l, True


def atomic_write(path, data):
    if path.is_file() and path.read_text() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def terminal_colors(surfaces):
    """Derive Kitty colors from this same Matugen palette; never sample again."""
    background = surfaces["surface_container_lowest"]
    foreground = surfaces["on_surface"]
    # Use Matugen's contrast-aware semantic roles directly. In particular,
    # Fish's default command color is ANSI blue (color4); a fixed hue here
    # made command text stay blue regardless of the wallpaper.
    semantic = {
        "red": surfaces["error"],
        "green": surfaces["tertiary"],
        "yellow": surfaces["secondary"],
        "blue": surfaces["primary"],
        "magenta": surfaces["tertiary"],
        "cyan": surfaces["secondary"],
    }
    normal = semantic
    bright = semantic
    return {
        "background": background,
        "foreground": foreground,
        "cursor": surfaces["primary"],
        "cursor_text": surfaces["on_primary"],
        "selection_background": surfaces["primary_container"],
        "selection_foreground": surfaces["on_primary_container"],
        "url_color": surfaces["primary"],
        "tab_bar_background": background,
        "active_tab_background": surfaces["primary_container"],
        "active_tab_foreground": surfaces["on_primary_container"],
        "inactive_tab_background": surfaces["surface_container"],
        "inactive_tab_foreground": surfaces["on_surface_variant"],
        "ansi": [
            background, normal["red"], normal["green"], normal["yellow"],
            normal["blue"], normal["magenta"], normal["cyan"], foreground,
            surfaces["outline_variant"], bright["red"], bright["green"],
            bright["yellow"], bright["blue"], bright["magenta"],
            bright["cyan"], surfaces["bright"],
        ],
        # The desktop Starship prompt intentionally uses these extended
        # xterm indices for its pill segments. Override their default greys
        # with equivalent Matugen roles so the copied prompt stays wallpaper-
        # themed on Sparrow as well.
        "extended": {
            235: foreground,
            240: foreground,
            243: surfaces["primary"],
            244: normal["red"],
            245: surfaces["outline_variant"],
            248: surfaces["surface_container"],
            249: normal["red"],
            250: surfaces["surface_container_high"],
            251: normal["magenta"],
            252: surfaces["surface_container_highest"],
            253: normal["blue"],
            254: surfaces["primary_container"],
            255: surfaces["surface_container_highest"],
        },
    }


def render_kitty(palette):
    lines = [
        "# Generated by Sparrow wallpaper palette; do not edit.",
        f"background {palette['background']}",
        f"foreground {palette['foreground']}",
        f"cursor {palette['cursor']}",
        f"cursor_text_color {palette['cursor_text']}",
        f"selection_background {palette['selection_background']}",
        f"selection_foreground {palette['selection_foreground']}",
        f"url_color {palette['url_color']}",
        f"tab_bar_background {palette['tab_bar_background']}",
        f"active_tab_background {palette['active_tab_background']}",
        f"active_tab_foreground {palette['active_tab_foreground']}",
        f"inactive_tab_background {palette['inactive_tab_background']}",
        f"inactive_tab_foreground {palette['inactive_tab_foreground']}",
    ]
    lines.extend(f"color{index} {color}" for index, color in enumerate(palette["ansi"]))
    lines.extend(f"color{index} {color}" for index, color in palette["extended"].items())
    return "\n".join(lines) + "\n"


def render_sparrow_gtk(palette):
    """Apply Matugen roles to adw-gtk3's named palette, preserving its states."""
    data_home = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    candidates = (
        data_home / "themes/adw-gtk3/gtk-3.0/gtk-dark.css",
        Path("/usr/share/themes/adw-gtk3/gtk-3.0/gtk-dark.css"),
    )
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise FileNotFoundError(
            "adw-gtk3 is missing; install Arch package adw-gtk-theme or the upstream user theme"
        )

    stylesheet = source.read_text()
    colors = {
        "blue_1": palette["primary"],
        "blue_2": palette["primary"],
        "blue_3": palette["primary"],
        "blue_4": palette["primary_container"],
        "blue_5": palette["primary_container"],
        "green_1": palette["tertiary"],
        "green_2": palette["tertiary"],
        "green_3": palette["tertiary"],
        "green_4": palette["tertiary_container"],
        "green_5": palette["tertiary_container"],
        "yellow_1": palette["secondary"],
        "yellow_2": palette["secondary"],
        "yellow_3": palette["secondary"],
        "yellow_4": palette["secondary_container"],
        "yellow_5": palette["secondary_container"],
        "orange_1": palette["secondary"],
        "orange_2": palette["secondary"],
        "orange_3": palette["secondary"],
        "orange_4": palette["secondary_container"],
        "orange_5": palette["secondary_container"],
        "red_1": palette["error"],
        "red_2": palette["error"],
        "red_3": palette["error"],
        "red_4": palette["error"],
        "red_5": palette["on_error"],
        "purple_1": palette["primary"],
        "purple_2": palette["primary"],
        "purple_3": palette["primary"],
        "purple_4": palette["primary_container"],
        "purple_5": palette["primary_container"],
        "brown_1": palette["tertiary"],
        "brown_2": palette["tertiary"],
        "brown_3": palette["tertiary"],
        "brown_4": palette["tertiary_container"],
        "brown_5": palette["tertiary_container"],
        "light_1": palette["on_surface"],
        "light_2": palette["on_surface"],
        "light_3": palette["on_surface_variant"],
        "light_4": palette["on_surface_variant"],
        "light_5": palette["outline"],
        "dark_1": palette["surface_container_highest"],
        "dark_2": palette["surface_container_high"],
        "dark_3": palette["surface_container"],
        "dark_4": palette["surface_container_low"],
        "dark_5": palette["background"],
        "accent_bg_color": palette["primary"],
        "accent_fg_color": palette["on_primary"],
        "destructive_bg_color": palette["error"],
        "destructive_fg_color": palette["on_error"],
        "success_bg_color": palette["tertiary_container"],
        "success_fg_color": palette["on_tertiary_container"],
        "warning_bg_color": palette["secondary_container"],
        "warning_fg_color": palette["on_secondary_container"],
        "error_bg_color": palette["error"],
        "error_fg_color": palette["on_error"],
        "window_bg_color": palette["background"],
        "window_fg_color": palette["on_background"],
        "view_bg_color": palette["surface_container_lowest"],
        "view_fg_color": palette["on_surface"],
        "headerbar_bg_color": palette["surface_container_low"],
        "headerbar_fg_color": palette["on_surface"],
        "headerbar_border_color": palette["outline_variant"],
        "headerbar_backdrop_color": palette["surface_container"],
        "sidebar_bg_color": palette["surface_container_low"],
        "sidebar_fg_color": palette["on_surface"],
        "sidebar_backdrop_color": palette["surface_container"],
        "sidebar_border_color": palette["outline_variant"],
        "card_bg_color": palette["surface_container"],
        "card_fg_color": palette["on_surface"],
        "dialog_bg_color": palette["surface_container_high"],
        "dialog_fg_color": palette["on_surface"],
        "popover_bg_color": palette["surface_container_high"],
        "popover_fg_color": palette["on_surface"],
        "thumbnail_bg_color": palette["surface_container"],
        "thumbnail_fg_color": palette["on_surface"],
        "panel_bg_color": palette["surface_container"],
        "panel_fg_color": palette["on_surface"],
    }
    for name, color in colors.items():
        pattern = re.compile(rf"(@define-color\s+{re.escape(name)}\s+)[^;]+;")
        stylesheet, count = pattern.subn(rf"\g<1>{color};", stylesheet, count=1)
        if count != 1:
            raise ValueError(f"adw-gtk3 stylesheet lacks expected color token: {name}")

    header = (
        "/* Generated by Sparrow from upstream adw-gtk3 GTK3 CSS (LGPL-2.1).\n"
        f" * Source: {source}\n"
        " * Matugen roles replace its named palette; upstream widget/state rules remain intact. */\n"
    )
    return header + stylesheet


def render_folder_icon(palette):
    """Create Sparrow's simple wallpaper-accented folder icon."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <path fill="{palette["primary_container"]}" d="M4 12a4 4 0 0 1 4-4h12l5 5h15a4 4 0 0 1 4 4v20a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"/>
  <path fill="{palette["primary"]}" d="M4.5 18h39l-3.2 17.7a4 4 0 0 1-3.9 3.3H8.6a4 4 0 0 1-3.9-4.7z"/>
  <path fill="{palette["on_primary"]}" opacity=".12" d="M6.2 20h35.6l-.5 2.8H5.7z"/>
</svg>
'''


def render_text_icon(palette):
    """Recolor Papirus's text-file glyph with the current Matugen accent."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <path fill="{palette["primary"]}" d="M2.75 1C2.33 1 2 1.333 2 1.75v12.5c0 .417.333.75.75.75h10.5c.418 0 .75-.333.75-.75V5.667L9.875 4.792 9 1z"/>
  <path fill="{palette["primary_container"]}" d="M9 1v4.167c0 .458.375.833.833.833H14z"/>
  <path fill="{palette["on_primary"]}" opacity=".68" d="M5 7h6v1H5zm0 2h6v1H5zm0 2h6v1H5zm0 2h3v1H5z"/>
</svg>
'''


def main():
    args = sys.argv[1:]
    palette_style = "tonal"
    style_flag = "--style" if "--style" in args else "--scheme" if "--scheme" in args else None
    if style_flag:
        index = args.index(style_flag)
        if index + 1 >= len(args):
            raise SystemExit(f"wallcolors: {style_flag} needs a Sparrow palette style")
        palette_style = canonical_style(args[index + 1])
        del args[index:index + 2]
    if not args:
        raise SystemExit("usage: wallcolors.py IMAGE [--style tonal|vibrant|alternate] | --hue DEGREES dark|light SATURATION [--style STYLE]")
    mode = "dark"
    if args[0] == "--hue":
        if len(args) < 2:
            raise SystemExit("wallcolors: --hue needs a hue value")
        hue = float(args[1]) % 360 / 360
        mode = "light" if len(args) >= 3 and args[2] == "light" else "dark"
        sat = max(0, min(1, float(args[3]) if len(args) > 3 else .5))
        chromatic = sat > .02
        manual_seed = tint(hue, sat, .45)
        manual_lab = rgb_to_oklab(tuple(int(manual_seed[i:i + 2], 16) for i in (1, 3, 5)))
        factor = {"tonal": 0.86, "vibrant": 1.0, "alternate": 1.0}[palette_style]
        seed = _lab_hex(_scale_lab_chroma(manual_lab, factor)) if chromatic else "#787878"
        if palette_style == "alternate":
            palette_style = "vibrant"
        style_options = ["tonal", "vibrant"] if chromatic else ["tonal"]
    else:
        wallpaper = Path(args[0])
        if not wallpaper.is_file():
            raise SystemExit(f"wallcolors: image not found: {wallpaper}")
        extraction = extract_candidates(wallpaper)
        selection = choose_seed(extraction, palette_style)
        seed, chromatic = selection["seed"], selection["chromatic"]
        palette_style = selection["style"]
        style_options = available_styles(extraction)
    # Wallpaper brightness never selects a light scheme automatically; dynamic
    # wallpaper palettes always use Matugen's dark Material roles.
    # Tonal uses Material's restrained Tonal Spot scheme; stronger choices use
    # Content, which preserves the selected image color instead of rotating to
    # a hue-harmony color.
    effective_scheme = material_scheme(palette_style, chromatic)
    command = ["matugen", "color", "hex", seed, "-m", mode if args[0] == "--hue" else "dark", "-t", effective_scheme, "-j", "hex"]
    matugen = subprocess.run(command,
                             check=True, capture_output=True, text=True)
    generated = json.loads(matugen.stdout)
    material = generated["colors"]
    scheme = mode if args[0] == "--hue" else "dark"
    role = lambda name: material[name][scheme]["color"]
    surfaces = {"source_color": seed}
    if scheme == "dark":
        if not chromatic and effective_scheme == "scheme-monochrome":
            # Preserve a truly neutral palette for grayscale wallpapers.
            tones = generated["palettes"]["neutral"]
        else:
            # Material's stock dark surface roles are intentionally almost
            # neutral black. Derive Sparrow's surface ramp directly from the
            # chosen image seed, not the standardized surface roles.
            surface_seed = seed
            ramp_result = subprocess.run(
                ["matugen", "color", "hex", surface_seed, "-m", "dark",
                 "-t", effective_scheme, "--dry-run", "-j", "hex"],
                check=True, capture_output=True, text=True,
            )
            tones = json.loads(ramp_result.stdout)["palettes"]["primary"]
        tone = lambda value: tones[str(value)]["color"]
        t_background, t_low, t_container, t_high, t_highest, t_bright = surface_tones(palette_style)
        surfaces.update(background=tone(t_background), surface=tone(t_low),
                        surface_container_lowest=tone(t_background), surface_container_low=tone(t_low),
                        surface_container=tone(t_container), surface_container_high=tone(t_high),
                        surface_container_highest=tone(t_highest), surface_bright=tone(t_bright),
                        outline_variant=tone(t_highest), outline=tone(60))
    else:
        # Manual light mode remains opt-in; only wallpaper-driven dynamic mode
        # is subject to Sparrow's forced-dark policy.
        for name in ("background", "surface", "surface_container_lowest", "surface_container_low",
                     "surface_container", "surface_container_high", "surface_container_highest",
                     "surface_bright", "outline", "outline_variant"):
            surfaces[name] = role(name)
    for name in ("primary", "on_primary", "primary_container", "on_primary_container",
                 "secondary", "on_secondary", "secondary_container", "on_secondary_container",
                 "tertiary", "on_tertiary", "tertiary_container", "on_tertiary_container",
                 "error", "on_error", "on_surface", "on_background", "on_surface_variant"):
        surfaces[name] = role(name)
    if scheme == "dark" and chromatic and palette_style != "tonal":
        # Keep Tonal's soft accent, but make the stronger styles use an
        # image-derived Material tone with its matching foreground tone.
        surfaces["primary"] = tone(70)
        surfaces["on_primary"] = tone(10)
    if scheme == "dark" and chromatic and palette_style != "tonal":
        # Tonal keeps Material's soft, high-contrast accent. Vibrant/Alternate
        # use a stronger source-derived accent tone rather than rotating hue.
        surfaces["primary"] = tone(70)
        surfaces["on_primary"] = tone(10)
    if scheme == "dark" and not chromatic and effective_scheme == "scheme-monochrome":
        # Monochrome can inherit a default chromatic hue for undefined gray
        # seeds. Keep Sparrow's established neutral fallback for this case.
        tones = generated["palettes"]["neutral"]
        tone = lambda value: tones[str(value)]["color"]
        surfaces.update(primary=tone(80), on_primary=tone(20), primary_container=tone(30),
                        on_primary_container=tone(90), secondary=tone(70), on_secondary=tone(20),
                        secondary_container=tone(30), on_secondary_container=tone(90),
                        tertiary=tone(70), on_tertiary=tone(20), tertiary_container=tone(30),
                        on_tertiary_container=tone(90), outline=tone(60), outline_variant=tone(35))
    surfaces.update(cream=surfaces["on_surface"], bright=surfaces["on_surface"],
                    subtle=surfaces["on_surface_variant"],
                    dim=surfaces["outline"],
                    faint=surfaces["outline_variant"],
                    icon_dim=surfaces["on_surface_variant"],
                    tick_rest=surfaces["outline"])
    kitty = terminal_colors(surfaces)
    surfaces["terminal"] = kitty
    surfaces["available_styles"] = style_options
    surfaces["palette_style"] = palette_style
    palette = json.dumps(surfaces, indent=2) + "\n"
    kdl = ("// Generated by Sparrow wallpaper palette; do not edit.\n"
           "layout {\n    border {\n"
           f'        active-color "{surfaces["primary"]}"\n'
           f'        inactive-color "{surfaces["outline_variant"]}"\n'
           "    }\n}\n")
    # The helper stages the whole Niri include tree and validates it before it
    # can replace the active generated fragment. Keep the JSON and Niri outputs
    # in step: on a failed Niri transaction, preserve the previous palette too.
    helper = Path(__file__).with_name("niri-config-transaction.py")
    request = json.dumps({"fragment": "generated-colors", "content": kdl}, ensure_ascii=False) + "\n"
    result = subprocess.run(
        [sys.executable, str(helper)], input=request, text=True,
        capture_output=True, check=False,
    )
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        response = {}
    if result.returncode != 0 or response.get("status") != "success":
        detail = response.get("message") or result.stderr.strip() or "Niri config transaction failed"
        raise RuntimeError(f"Niri colors were not applied: {detail}")

    atomic_write(CACHE / "palette.json", palette)
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
    kitty_colors = config_home / "kitty" / "sparrow-colors.conf"
    try:
        colors_changed = atomic_write(kitty_colors, render_kitty(kitty))
    except OSError as exc:
        # Kitty is an optional consumer: it must never make wallpaper/palette
        # changes fail on systems without Kitty or a writable Kitty config dir.
        print(f"wallcolors: optional Kitty palette was not written: {exc}", file=sys.stderr)
    else:
        if colors_changed:
            # Kitty watches the top-level config paths, not files resolved by
            # globinclude. Its documented SIGUSR1 reload picks up this newly
            # written generated include in all currently running instances.
            try:
                subprocess.run(
                    ["pkill", "-USR1", "-x", "kitty"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
            except OSError as exc:
                print(f"wallcolors: Kitty palette was written, but live Kitty could not be reloaded: {exc}",
                      file=sys.stderr)

    data_home = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    gtk_theme_dir = data_home / "themes" / "Sparrow" / "gtk-3.0"
    try:
        atomic_write(gtk_theme_dir / "gtk-dark.css", render_sparrow_gtk(surfaces))
    except (OSError, ValueError) as exc:
        print(f"wallcolors: optional Matugen GTK theme was not written: {exc}", file=sys.stderr)

    folder_icon = render_folder_icon(surfaces)
    icon_changes = False
    for icon_name in (
        "folder", "folder-open", "folder-documents", "folder-download",
        "folder-music", "folder-pictures", "folder-publicshare",
        "folder-templates", "folder-videos", "folder-remote",
        "folder-bookmarks", "folder-desktop", "user-desktop",
        "system-file-manager",
    ):
        try:
            icon_changes |= atomic_write(
                data_home / "icons" / "Sparrow" / "scalable" / "places" /
                f"{icon_name}.svg", folder_icon
            )
        except OSError as exc:
            print(f"wallcolors: optional GTK folder icon {icon_name} was not written: {exc}",
                  file=sys.stderr)
    try:
        icon_changes |= atomic_write(
            data_home / "icons" / "Sparrow" / "symbolic" / "places" /
            "folder-symbolic.svg", folder_icon
        )
    except OSError as exc:
        print(f"wallcolors: optional symbolic folder icon was not written: {exc}",
              file=sys.stderr)
    try:
        icon_changes |= atomic_write(
            data_home / "icons" / "Sparrow" / "scalable" / "mimetypes" /
            "text-x-generic.svg", render_text_icon(surfaces)
        )
    except OSError as exc:
        print(f"wallcolors: optional themed text icon was not written: {exc}",
              file=sys.stderr)
    if icon_changes:
        icon_root = data_home / "icons" / "Sparrow"
        try:
            subprocess.run(
                ["gtk-update-icon-cache", "--force", str(icon_root)],
                check=True, capture_output=True, text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"wallcolors: Sparrow folder icons changed, but the icon cache could not be refreshed: {exc}",
                  file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"wallcolors: {exc}", file=sys.stderr)
        raise SystemExit(1)
