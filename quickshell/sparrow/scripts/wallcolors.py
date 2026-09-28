#!/usr/bin/env python3
"""Generate Sparrow consumer files from Matugen's canonical Material palette."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "sparrow-shell"
STATIC_SEED = "#e0563b"
LOCK_DARK_FOREGROUND_THRESHOLD = 0.22
PALETTE_STYLES = ("auto", "tonal", "content", "monochrome")
APPEARANCE_MODES = ("auto", "dark", "light")
MATUGEN_STYLES = {
    "auto": "scheme-smart",
    "tonal": "scheme-tonal-spot",
    "content": "scheme-content",
    "monochrome": "scheme-monochrome",
}
LEGACY_STYLES = {
    "scheme-smart": "auto", "scheme-tonal-spot": "tonal",
    "scheme-content": "content", "scheme-monochrome": "monochrome",
    "scheme-neutral": "tonal", "neutral": "tonal",
    "scheme-fidelity": "tonal", "fidelity": "tonal",
    "scheme-expressive": "auto", "expressive": "auto",
    "scheme-vibrant": "auto", "vibrant": "content",
    "scheme-fruit-salad": "auto", "fruit": "auto", "alternate": "auto",
}
SEMANTIC_ROLES = (
    "background", "on_background", "surface", "on_surface", "on_surface_variant",
    "surface_dim", "surface_bright", "surface_container_lowest", "surface_container_low",
    "surface_container", "surface_container_high", "surface_container_highest",
    "surface_variant", "surface_tint", "primary", "on_primary", "primary_container",
    "on_primary_container", "primary_fixed", "primary_fixed_dim", "on_primary_fixed",
    "on_primary_fixed_variant", "secondary", "on_secondary", "secondary_container",
    "on_secondary_container", "secondary_fixed", "secondary_fixed_dim", "on_secondary_fixed",
    "on_secondary_fixed_variant", "tertiary", "on_tertiary", "tertiary_container",
    "on_tertiary_container", "tertiary_fixed", "tertiary_fixed_dim", "on_tertiary_fixed",
    "on_tertiary_fixed_variant", "error", "on_error", "error_container",
    "on_error_container", "outline", "outline_variant", "inverse_surface",
    "inverse_on_surface", "inverse_primary", "scrim", "shadow", "source_color",
)


def canonical_style(value: str | None) -> str:
    style = str(value or "auto").strip().lower()
    style = LEGACY_STYLES.get(style, style)
    if style not in PALETTE_STYLES:
        raise ValueError(f"unsupported Sparrow palette style: {style}")
    return style


def canonical_mode(value: str | None) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in APPEARANCE_MODES else "auto"


def linear_channel(value: int) -> float:
    value /= 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (linear_channel(value) for value in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def recommended_lock_foreground(luminance: float) -> str:
    """Keep the independent Qylock foreground choice based on actual wallpaper lightness."""
    return "dark" if luminance >= LOCK_DARK_FOREGROUND_THRESHOLD else "light"


def sample_wallpaper_luminance(path: Path, max_dimension: int = 200) -> float:
    """A small sample remains solely for lockscreen contrast metadata, not palette selection."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.BOX)
        pixels = image.tobytes()
    count = len(pixels) // 3
    total = sum(relative_luminance((pixels[i], pixels[i + 1], pixels[i + 2]))
                for i in range(0, len(pixels), 3))
    return total / max(count, 1)


def run_matugen(image: Path, source_mode: str, style: str, appearance_mode: str):
    """Use Matugen's image/color source ranking, scheme, and mode generation directly."""
    source_mode = "static" if source_mode == "static" else "dynamic"
    style = canonical_style(style)
    appearance_mode = canonical_mode(appearance_mode) if source_mode == "dynamic" else "dark"
    scheme_type = MATUGEN_STYLES[style] if source_mode == "dynamic" else "scheme-tonal-spot"
    matugen_mode = "smart" if appearance_mode == "auto" else appearance_mode

    if source_mode == "static":
        style = "tonal"
        appearance_mode = "dark"
        command = ["matugen", "color", "hex", STATIC_SEED]
    else:
        command = ["matugen", "image", str(image), "--source-color-index", "0",
                   "--fallback-color", STATIC_SEED]
    command.extend(["--type", scheme_type, "--mode", matugen_mode,
                    "--dry-run", "--json", "hex"])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    generated = json.loads(result.stdout)
    resolved_mode = generated.get("mode")
    if resolved_mode not in ("dark", "light"):
        resolved_mode = "dark" if matugen_mode == "smart" else matugen_mode

    colors = generated["colors"]
    roles = {}
    for name, variants in colors.items():
        if not isinstance(variants, dict):
            continue
        selected = variants.get(resolved_mode) or variants.get("default")
        if isinstance(selected, dict) and isinstance(selected.get("color"), str):
            roles[name] = selected["color"]
    missing = sorted(set(SEMANTIC_ROLES).difference(roles))
    if missing:
        raise ValueError("Matugen output is missing semantic roles: " + ", ".join(missing))
    return roles, resolved_mode, style, appearance_mode, source_mode


def atomic_write(path: Path, data: str) -> bool:
    if path.is_file() and path.read_text() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def terminal_colors(palette: dict[str, str]) -> dict:
    """Map the same semantic palette into Kitty and the shell's ANSI slots."""
    semantic = {
        "red": palette["error"],
        "green": palette["tertiary"],
        "yellow": palette["secondary"],
        "blue": palette["primary"],
        "magenta": palette["tertiary"],
        "cyan": palette["secondary"],
    }
    background, foreground = palette["surface_container_lowest"], palette["on_surface"]
    return {
        "background": background, "foreground": foreground,
        "cursor": palette["primary"], "cursor_text": palette["on_primary"],
        "selection_background": palette["primary_container"],
        "selection_foreground": palette["on_primary_container"],
        "url_color": palette["primary"], "tab_bar_background": background,
        "active_tab_background": palette["primary_container"],
        "active_tab_foreground": palette["on_primary_container"],
        "inactive_tab_background": palette["surface_container"],
        "inactive_tab_foreground": palette["on_surface_variant"],
        "ansi": [background, semantic["red"], semantic["green"], semantic["yellow"],
                 semantic["blue"], semantic["magenta"], semantic["cyan"], foreground,
                 palette["outline_variant"], semantic["red"], semantic["green"],
                 semantic["yellow"], semantic["blue"], semantic["magenta"],
                 semantic["cyan"], palette["on_surface"]],
        "extended": {
            235: foreground, 240: foreground, 243: palette["primary"],
            244: semantic["red"], 245: palette["outline_variant"],
            248: palette["surface_container"], 249: semantic["red"],
            250: palette["surface_container_high"], 251: semantic["magenta"],
            252: palette["surface_container_highest"], 253: semantic["blue"],
            254: palette["primary_container"], 255: palette["surface_container_highest"],
        },
    }


def render_kitty(palette: dict) -> str:
    lines = ["# Generated by Sparrow from Matugen roles; do not edit."]
    for key in ("background", "foreground", "cursor", "cursor_text", "selection_background",
                "selection_foreground", "url_color", "tab_bar_background", "active_tab_background",
                "active_tab_foreground", "inactive_tab_background", "inactive_tab_foreground"):
        kitty_key = "cursor_text_color" if key == "cursor_text" else key
        lines.append(f"{kitty_key} {palette[key]}")
    lines.extend(f"color{index} {color}" for index, color in enumerate(palette["ansi"]))
    lines.extend(f"color{index} {color}" for index, color in palette["extended"].items())
    return "\n".join(lines) + "\n"


def find_adw_gtk3_stylesheet(
    resolved_mode: str,
    data_home: Path | None = None,
    system_theme_root: Path = Path("/usr/share/themes/adw-gtk3"),
) -> Path:
    """Prefer the declared system package; the user copy is a dev-only fallback."""
    data_home = data_home or Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    filename = "gtk-dark.css" if resolved_mode == "dark" else "gtk.css"
    candidates = (
        system_theme_root / "gtk-3.0" / filename,
        data_home / "themes/adw-gtk3/gtk-3.0" / filename,
    )
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise FileNotFoundError(
            "adw-gtk3 GTK3 source is missing; install Arch package adw-gtk-theme"
        )
    return source


def find_adw_gtk4_theme(
    data_home: Path | None = None,
    system_theme_root: Path = Path("/usr/share/themes/adw-gtk3"),
) -> Path:
    """Prefer the installed adw-gtk3 GTK4 base, with the same dev fallback."""
    data_home = data_home or Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    candidates = (
        system_theme_root / "gtk-4.0",
        data_home / "themes/adw-gtk3/gtk-4.0",
    )
    required = ("gtk.css", "gtk-dark.css", "libadwaita.css", "libadwaita-tweaks.css")
    source = next(
        (path for path in candidates if all((path / name).is_file() for name in required)
         and (path / "assets").is_dir()),
        None,
    )
    if source is None:
        raise FileNotFoundError(
            "adw-gtk3 GTK4 source is missing; install Arch package adw-gtk-theme"
        )
    return source


def gtk_role_colors(palette: dict[str, str]) -> dict[str, str]:
    """Map the canonical Matugen roles to adw-gtk3's shared GTK named colors."""
    return {
        "blue_1": palette["primary"], "blue_2": palette["primary"],
        "blue_3": palette["primary"], "blue_4": palette["primary_container"],
        "blue_5": palette["primary_container"], "green_1": palette["tertiary"],
        "green_2": palette["tertiary"], "green_3": palette["tertiary"],
        "green_4": palette["tertiary_container"], "green_5": palette["tertiary_container"],
        "yellow_1": palette["secondary"], "yellow_2": palette["secondary"],
        "yellow_3": palette["secondary"], "yellow_4": palette["secondary_container"],
        "yellow_5": palette["secondary_container"], "orange_1": palette["secondary"],
        "orange_2": palette["secondary"], "orange_3": palette["secondary"],
        "orange_4": palette["secondary_container"], "orange_5": palette["secondary_container"],
        "red_1": palette["error"], "red_2": palette["error"], "red_3": palette["error"],
        "red_4": palette["error"], "red_5": palette["on_error"],
        "purple_1": palette["primary"], "purple_2": palette["primary"],
        "purple_3": palette["primary"], "purple_4": palette["primary_container"],
        "purple_5": palette["primary_container"], "brown_1": palette["tertiary"],
        "brown_2": palette["tertiary"], "brown_3": palette["tertiary"],
        "brown_4": palette["tertiary_container"], "brown_5": palette["tertiary_container"],
        "light_1": palette["on_surface"], "light_2": palette["on_surface"],
        "light_3": palette["on_surface_variant"], "light_4": palette["on_surface_variant"],
        "light_5": palette["outline"], "dark_1": palette["surface_container_highest"],
        "dark_2": palette["surface_container_high"], "dark_3": palette["surface_container"],
        "dark_4": palette["surface_container_low"], "dark_5": palette["background"],
        "accent_bg_color": palette["primary"], "accent_fg_color": palette["on_primary"],
        "destructive_bg_color": palette["error"], "destructive_fg_color": palette["on_error"],
        "success_bg_color": palette["tertiary_container"],
        "success_fg_color": palette["on_tertiary_container"],
        "warning_bg_color": palette["secondary_container"],
        "warning_fg_color": palette["on_secondary_container"],
        "error_bg_color": palette["error"], "error_fg_color": palette["on_error"],
        "window_bg_color": palette["background"], "window_fg_color": palette["on_background"],
        "view_bg_color": palette["surface_container_lowest"], "view_fg_color": palette["on_surface"],
        "headerbar_bg_color": palette["surface_container_low"],
        "headerbar_fg_color": palette["on_surface"],
        "headerbar_border_color": palette["outline_variant"],
        "headerbar_backdrop_color": palette["surface_container"],
        "sidebar_bg_color": palette["surface_container_low"],
        "sidebar_fg_color": palette["on_surface"],
        "sidebar_backdrop_color": palette["surface_container"],
        "sidebar_border_color": palette["outline_variant"],
        "card_bg_color": palette["surface_container"], "card_fg_color": palette["on_surface"],
        "dialog_bg_color": palette["surface_container_high"], "dialog_fg_color": palette["on_surface"],
        "popover_bg_color": palette["surface_container_high"], "popover_fg_color": palette["on_surface"],
        "thumbnail_bg_color": palette["surface_container"], "thumbnail_fg_color": palette["on_surface"],
        "panel_bg_color": palette["surface_container"], "panel_fg_color": palette["on_surface"],
    }


def recolor_gtk_roles(stylesheet: str, palette: dict[str, str], *, strict: bool = True) -> str:
    """Recolor upstream named roles and GTK4 theme CSS variables from Matugen."""
    import re

    for name, color in gtk_role_colors(palette).items():
        stylesheet, count = re.subn(
            rf"(@define-color\s+{re.escape(name)}\s+)[^;]+;",
            lambda match: match.group(1) + color + ";", stylesheet,
        )
        if strict and count != 1:
            raise ValueError(f"adw-gtk3 stylesheet lacks expected color token: {name}")

        css_name = name.replace("_", "-")
        stylesheet = re.sub(
            rf"(--{re.escape(css_name)}\s*:\s*)#[0-9a-fA-F]{{6}}",
            lambda match: match.group(1) + color, stylesheet,
        )
    return stylesheet


def render_sparrow_gtk(palette: dict, source: Path | None = None) -> str:
    """Recolor upstream adw-gtk3 GTK3 named roles without replacing its widgets."""
    upstream = source or find_adw_gtk3_stylesheet("dark")
    stylesheet = recolor_gtk_roles(upstream.read_text(), palette)
    return (
        "/* Generated by Sparrow from upstream adw-gtk3 GTK3 CSS (LGPL-2.1).\n"
        f" * Source: {upstream}\n"
        " * Matugen semantic roles replace its named palette; upstream widget/state rules remain. */\n"
        + stylesheet
    )


def render_sparrow_gtk4(palette: dict, source: Path) -> str:
    """Recolor the installed adw-gtk3 GTK4 base used by plain GTK4 apps."""
    stylesheet = recolor_gtk_roles(
        (source / "libadwaita.css").read_text(), palette, strict=False,
    )
    stylesheet = recolor_gtk4_accents(stylesheet, palette)
    return (
        "/* Generated by Sparrow from upstream adw-gtk3 GTK4 CSS (LGPL-2.1).\n"
        f" * Source: {source / 'libadwaita.css'}\n"
        " * Matugen semantic roles replace its named palette; upstream rules remain. */\n"
        + stylesheet
    )


def recolor_gtk4_accents(
    stylesheet: str, palette: dict[str, str], *, named_colors: bool = False,
) -> str:
    """Replace adw-gtk3's standalone GTK4 accent slots with Matugen roles."""
    import re

    accents = {
        "blue": palette["primary"], "teal": palette["secondary"],
        "green": palette["tertiary"], "yellow": palette["secondary"],
        "orange": palette["secondary"], "red": palette["error"],
        "pink": palette["tertiary"], "purple": palette["primary"],
        "slate": palette["outline"],
    }
    for name, color in accents.items():
        stylesheet, count = re.subn(
            rf"(--accent-{name}\s*:\s*)#[0-9a-fA-F]{{6}}",
            lambda match: match.group(1) + color, stylesheet,
        )
        if count == 0:
            raise ValueError(f"adw-gtk3 GTK4 CSS lacks accent slot: {name}")
    if named_colors:
        for name, color in (
            ("accent_bg_color", palette["primary"]),
            ("accent_fg_color", palette["on_primary"]),
        ):
            stylesheet, count = re.subn(
                rf"(@define-color\s+{name}\s+)[^;]+;",
                lambda match: match.group(1) + color + ";", stylesheet,
            )
            if count == 0:
                raise ValueError(f"adw-gtk3 GTK4 CSS lacks named color: {name}")
    return stylesheet


def render_sparrow_gtk4_tweaks(source: Path, palette: dict[str, str]) -> str:
    """Keep adw-gtk3's GTK4 tweaks while routing their accent slots to Matugen."""
    stylesheet = recolor_gtk4_accents(
        (source / "libadwaita-tweaks.css").read_text(), palette, named_colors=True,
    )
    return (
        "/* Generated by Sparrow from upstream adw-gtk3 GTK4 tweaks (LGPL-2.1). */\n"
        + stylesheet
    )


def write_sparrow_gtk4_theme(palette: dict[str, str], data_home: Path) -> None:
    """Materialize the installed adw-gtk3 GTK4 theme with Sparrow palette roles."""
    import shutil

    source = find_adw_gtk4_theme(data_home)
    destination = data_home / "themes/Sparrow/gtk-4.0"
    atomic_write(destination / "gtk.css", source.joinpath("gtk.css").read_text())
    atomic_write(destination / "gtk-dark.css", source.joinpath("gtk-dark.css").read_text())
    atomic_write(destination / "libadwaita.css", render_sparrow_gtk4(palette, source))
    atomic_write(destination / "libadwaita-tweaks.css",
                 render_sparrow_gtk4_tweaks(source, palette))
    shutil.copytree(source / "assets", destination / "assets", dirs_exist_ok=True)


def render_folder_icon(palette: dict[str, str]) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <path fill="{palette["primary_container"]}" d="M4 12a4 4 0 0 1 4-4h12l5 5h15a4 4 0 0 1 4 4v20a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"/>
  <path fill="{palette["primary"]}" d="M4.5 18h39l-3.2 17.7a4 4 0 0 1-3.9 3.3H8.6a4 4 0 0 1-3.9-4.7z"/>
  <path fill="{palette["on_primary"]}" opacity=".12" d="M6.2 20h35.6l-.5 2.8H5.7z"/>
</svg>
'''


def render_text_icon(palette: dict[str, str]) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <path fill="{palette["primary"]}" d="M2.75 1C2.33 1 2 1.333 2 1.75v12.5c0 .417.333.75.75.75h10.5c.418 0 .75-.333.75-.75V5.667L9.875 4.792 9 1z"/>
  <path fill="{palette["primary_container"]}" d="M9 1v4.167c0 .458.375.833.833.833H14z"/>
  <path fill="{palette["on_primary"]}" opacity=".68" d="M5 7h6v1H5zm0 2h6v1H5zm0 2h6v1H5zm0 2h3v1H5z"/>
</svg>
'''


def render_niri_colors(palette: dict[str, str]) -> str:
    return (
        "// Generated by Sparrow wallpaper palette; do not edit.\n"
        "layout {\n    border {\n"
        f'        active-color "{palette["primary"]}"\n'
        f'        inactive-color "{palette["outline_variant"]}"\n'
        "    }\n}\n"
        "recent-windows {\n    highlight {\n"
        f'        active-color "{palette["primary"]}"\n'
        f'        urgent-color "{palette["error"]}"\n'
        "    }\n}\n"
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--style", default="auto")
    parser.add_argument("--mode", default="auto")
    parser.add_argument("--source-mode", choices=("static", "dynamic"), default="dynamic")
    args = parser.parse_args()
    if not args.image.is_file():
        raise SystemExit(f"wallcolors: image not found: {args.image}")

    style = canonical_style(args.style)
    mode = canonical_mode(args.mode)
    roles, resolved_mode, style, mode, source_mode = run_matugen(
        args.image, args.source_mode, style, mode,
    )
    luminance = sample_wallpaper_luminance(args.image)
    palette = dict(roles)
    palette.update({
        "cream": roles["on_surface"], "bright": roles["on_surface"],
        "subtle": roles["on_surface_variant"], "dim": roles["outline"],
        "faint": roles["outline_variant"], "icon_dim": roles["on_surface_variant"],
        "tick_rest": roles["outline"],
        "wallpaper_luminance": round(luminance, 6),
        "recommended_lock_foreground": recommended_lock_foreground(luminance),
        "theme_source": source_mode, "palette_style": style,
        "appearance_mode": mode, "resolved_mode": resolved_mode,
    })
    terminal = terminal_colors(palette)
    palette["terminal"] = terminal
    palette_json = json.dumps(palette, indent=2) + "\n"
    niri_kdl = render_niri_colors(roles)
    data_home = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    # These are required Sparrow appearance inputs. Resolve and render them
    # before committing any generated state, so a missing base theme fails the
    # first palette run instead of leaving a partial, silently unthemed desktop.
    gtk_source = find_adw_gtk3_stylesheet(resolved_mode, data_home)
    gtk_rendered = render_sparrow_gtk(palette, gtk_source)
    gtk4_source = find_adw_gtk4_theme(data_home)
    render_sparrow_gtk4(palette, gtk4_source)
    render_sparrow_gtk4_tweaks(gtk4_source, palette)
    transaction = Path(__file__).with_name("niri-config-transaction.py")
    request = json.dumps({"fragment": "generated-colors", "content": niri_kdl}) + "\n"
    result = subprocess.run([sys.executable, str(transaction)], input=request,
                            text=True, capture_output=True, check=False)
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        response = {}
    if result.returncode != 0 or response.get("status") != "success":
        detail = response.get("message") or result.stderr.strip() or "Niri config transaction failed"
        raise RuntimeError(f"Niri colors were not applied: {detail}")

    atomic_write(CACHE / "palette.json", palette_json)
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
    changed = atomic_write(config_home / "kitty/sparrow-colors.conf", render_kitty(terminal))
    if changed:
        subprocess.run(["pkill", "-USR1", "-x", "kitty"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    gtk_dir = data_home / "themes/Sparrow/gtk-3.0"
    # Both GTK3 preference variants resolve to the one selected canonical palette.
    atomic_write(gtk_dir / "gtk.css", gtk_rendered)
    atomic_write(gtk_dir / "gtk-dark.css", gtk_rendered)

    write_sparrow_gtk4_theme(palette, data_home)

    icons = data_home / "icons/Sparrow"
    icon_changes = False
    for name in (
        "folder", "folder-open", "folder-documents", "folder-download", "folder-music",
        "folder-pictures", "folder-publicshare", "folder-templates", "folder-videos",
        "folder-remote", "folder-bookmarks", "folder-desktop", "user-desktop",
        "system-file-manager",
    ):
        icon_changes |= atomic_write(icons / f"scalable/places/{name}.svg", render_folder_icon(palette))
    icon_changes |= atomic_write(icons / "symbolic/places/folder-symbolic.svg", render_folder_icon(palette))
    icon_changes |= atomic_write(icons / "scalable/mimetypes/text-x-generic.svg", render_text_icon(palette))
    if icon_changes:
        try:
            subprocess.run(["gtk-update-icon-cache", "--force", str(icons)],
                           check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"wallcolors: Sparrow icon cache could not be refreshed: {error}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"wallcolors: {error}", file=sys.stderr)
        raise SystemExit(1)
