#!/usr/bin/env python3
"""
Generate the rice colour set from a wallpaper and fan it out to the consumers.
One histogram pass yields both the area-dominant chromatic hue (binned by hue
family so a small vivid accent never hijacks the theme) and the mean lightness.
The mean lightness drives the pill's whole tone: a bright wallpaper makes a light
pill with dark text, a dark or OLED-black one makes a near-black pill with cream
text, so the surfaces and the text flip together for contrast across the full
range. The dominant hue tints every tier in HSL. An achromatic wallpaper drops to
a neutral grey ramp. matugen still builds the dark base16 the always-dark terminal
reads; the pill JSON carries surfaces, accent and the contrast-matched text.
"""
import colorsys
import json
import re
import subprocess
import sys
from pathlib import Path

CACHE = Path.home() / ".cache" / "ricelin"

SURF_NAMES = ["surface", "surface_container_low", "surface_container",
              "surface_container_high", "surface_container_highest", "outline_variant"]
DARK_STEPS = [0.0, 0.035, 0.070, 0.110, 0.160, 0.300]
LIGHT_STEPS = [0.0, -0.025, -0.050, -0.075, -0.105, -0.175]
TEXT_KEYS = ["cream", "bright", "subtle", "dim", "faint", "icon_dim", "tick_rest"]
DARK_TEXT = [(0.90, 0.05), (0.97, 0.03), (0.73, 0.07), (0.54, 0.06),
             (0.44, 0.05), (0.81, 0.07), (0.75, 0.08)]
LIGHT_TEXT = [(0.20, 0.18), (0.10, 0.20), (0.36, 0.14), (0.48, 0.10),
              (0.56, 0.08), (0.28, 0.12), (0.34, 0.12)]


def analyze(wallpaper):
    out = subprocess.run(
        ["magick", wallpaper, "-alpha", "off", "-resize", "200x200", "-colors", "48",
         "-format", "%c", "histogram:info:-"],
        capture_output=True, text=True).stdout
    buckets, total, lum, chroma = {}, 0, 0.0, 0
    for line in out.splitlines():
        m = re.search(r"\s*(\d+):\s*\([^)]*\)\s*#([0-9A-Fa-f]{6})", line)
        if not m:
            continue
        count, hex_str = int(m.group(1)), m.group(2)
        r, g, b = (int(hex_str[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        total += count
        lum += count * l
        if s < 0.15 or l < 0.05 or l > 0.92:
            continue
        chroma += count
        bucket = buckets.setdefault((int(h * 360) // 30) % 12, {"wsat": 0.0, "best": None})
        bucket["wsat"] += count * s
        score = count * s * (1 if 0.12 < l < 0.55 else 0.4)
        if not bucket["best"] or score > bucket["best"][0]:
            bucket["best"] = (score, h, s)
    mean_l = lum / total if total else 0.0
    if not buckets or chroma < 0.08 * total:
        return None, 0.0, mean_l
    win = max(buckets.values(), key=lambda v: v["wsat"])
    return win["best"][1], win["best"][2], mean_l


def matugen(source_hex):
    out = subprocess.run(
        ["matugen", "color", "hex", source_hex, "-m", "dark", "-j", "hex"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def matugen_image(wallpaper, mode):
    """Generate Material roles from the wallpaper itself.

    The previous generator selected one histogram hue and rebuilt every UI
    surface in HSL. That makes bright wallpapers turn into a flat, muddy
    monochrome. Matugen's fidelity scheme keeps the source character while
    deriving surfaces and on-colors from Material's tonal roles.
    """
    out = subprocess.run(
        ["matugen", "image", wallpaper, "-m", mode, "-t", "scheme-fidelity",
         "--prefer", "saturation", "-j", "hex"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def role(colors, name, mode, fallback):
    value = colors.get(name, {})
    if isinstance(value, dict):
        value = value.get(mode) or value.get("default")
    if isinstance(value, dict):
        value = value.get("color")
    return value or fallback


def tint(hue, sat, light):
    r, g, b = colorsys.hls_to_rgb(hue % 1.0, max(0.0, min(1.0, light)), max(0.0, min(1.0, sat)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def lerp(x, x0, x1, y0, y1):
    t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
    return y0 + t * (y1 - y0)


def render_fastfetch(pill):
    """
    Recolour the fastfetch readout from the same pill palette. fastfetch has no
    daemon, so writing the rendered config is enough, the next run picks it up.
    The accent drives the keys and the torii, the surface ramp the lantern body,
    and a dim text tone the section rules, so it tracks the wallpaper like the
    pill and terminal do.
    """
    ff = Path.home() / ".config" / "fastfetch"
    tmpl = ff / "config.jsonc.in"
    if not tmpl.is_file():
        print("wallcolors: config.jsonc.in missing in ~/.config/fastfetch, skipping "
              "fastfetch recolour (apply the Ricelin update or re-run the installer)",
              file=sys.stderr)
        return
    seq = lambda h: "%d;%d;%d" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    repl = {
        "__LANTERN__": str(ff / "lantern.txt"),
        "__KEYS__": seq(pill["primary"]),
        "__SEP__": seq(pill["dim"]),
        "__LOGO1__": seq(pill["primary"]),
        "__LOGO2__": seq(pill["on_primary_container"]),
        "__LOGO3__": seq(pill["surface_container"]),
        "__LOGO4__": seq(pill["surface_container_high"]),
        "__LOGO5__": seq(pill["subtle"]),
        "__LOGO6__": seq(pill["outline"]),
        "__LOGO7__": seq(pill["bright"]),
    }
    out = tmpl.read_text()
    for key, val in repl.items():
        out = out.replace(key, val)
    (ff / "config.jsonc").write_text(out)


def rgba(hex_color, alpha):
    """Return a CSS rgba() value from one of the generated hex colors."""
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def render_vesktop(pill, hue, sat, light):
    """Generate the transparent, rounded Vesktop override from Ricelin colors."""
    settings = Path.home() / ".config" / "vesktop" / "settings"
    quick_css = settings / "quickCss.css"
    settings.mkdir(parents=True, exist_ok=True)

    # Use the same light/dark decision and surface family as the rest of the
    # rice. Chromatic bright wallpapers stay hue-forward instead of becoming
    # white with a colored accent; genuinely grayscale bright wallpapers can
    # still use a readable light palette.
    discord_surface = pill["surface"]
    discord_low = pill["surface_container_low"]
    discord_high = pill["surface_container_high"]
    discord_raised = pill["surface_container_highest"]
    if light:
        discord_text = pill["bright"]
        discord_subtle = pill["subtle"]
        discord_muted = pill["dim"]
    else:
        discord_text = "#f7f7f8"
        discord_subtle = "#d3cdd8"
        discord_muted = "#aaa2b2"

    # The structural theme supplies transparency and panel layout. These
    # variables deliberately keep Discord's rounded UI while making its
    # surfaces translucent over the real Hyprland wallpaper.
    css = f"""/* Generated by Ricelin wallpaper palette. Do not edit by hand. */
body {{
    --font: '';
    --code-font: '';
    --unrounding: off;
    --panel-labels: off;
    --ascii-titles: off;
    --ascii-loader: off;
    --background-image: off;
    --transparency-tweaks: off;
    --remove-bg-layer: off;
    --panel-blur: off;
    --blur-amount: 0px;
    --gap: 8px;
    --border-thickness: 1px;
}}

:root {{
    --systemcolor-base: {pill['primary']};
    --bg-1: {rgba(discord_raised, 0.98)};
    --bg-2: {rgba(discord_high, 0.98)};
    --bg-3: {rgba(discord_low, 0.98)};
    --bg-4: {rgba(discord_surface, 0.98)};
    --hover: {rgba(discord_text, 0.08)};
    --active: {rgba(pill['primary'], 0.22)};
    --active-2: {rgba(pill['primary'], 0.30)};
    --message-hover: var(--hover);
    --text-0: {discord_text};
    --text-1: {discord_text};
    --text-2: {discord_text};
    --text-3: {discord_subtle};
    --text-4: {discord_muted};
    --text-5: {discord_muted};
    --accent-1: {pill['primary']};
    --accent-2: {pill['primary']};
    --accent-3: {pill['primary']};
    --accent-4: {pill['on_primary_container']};
    --accent-5: {pill['primary_container']};
    --border-light: {rgba(discord_text, 0.09)};
    --border: {rgba(discord_text, 0.13)};
    --border-hover: {rgba(discord_text, 0.24)};
}}

html, body, #app-mount {{
    background: transparent !important;
}}
"""
    quick_css.write_text(css)


def render_spotify(pill):
    """Write a high-contrast wallpaper palette into a native-layout theme."""
    theme_dir = Path.home() / ".config" / "spicetify" / "Themes" / "RicelinNative"
    theme_dir.mkdir(parents=True, exist_ok=True)

    def bare(value):
        return value.lstrip("#")

    color_ini = f"""[ricelin]
main            = {bare(pill['surface'])}
sidebar         = {bare(pill['surface_container_low'])}
player          = {bare(pill['surface_container'])}
card            = {bare(pill['surface_container_high'])}
shadow          = {bare(pill['surface_container'])}
selected-row    = {bare(pill['primary'])}
button          = {bare(pill['primary'])}
button-active   = {bare(pill['on_primary_container'])}
button-disabled = {bare(pill['dim'])}
tab-active      = {bare(pill['primary'])}
text            = {bare(pill['bright'])}
subtext         = {bare(pill['subtle'])}
notification    = {bare(pill['surface_container_high'])}
notification-error = ff6b6b
misc            = {bare(pill['outline_variant'])}
"""
    (theme_dir / "color.ini").write_text(color_ini)


def render_pywalfox(pill):
    """Expose the Ricelin palette in pywal's format for the Firefox bridge."""
    wal_dir = Path.home() / ".cache" / "wal"
    wal_dir.mkdir(parents=True, exist_ok=True)
    colors = [
        pill["surface"], pill["primary_container"], pill["primary"],
        pill["on_primary_container"], pill["surface_container_high"],
        pill["outline_variant"], pill["secondary"], pill["subtle"],
        pill["dim"], pill["tertiary"], pill["on_primary_container"],
        pill["bright"], pill["primary"], pill["outline"],
        pill["primary_container"], pill["bright"],
    ]
    (wal_dir / "colors.json").write_text(json.dumps({
        "special": {
            "background": pill["surface"],
            "foreground": pill["bright"],
            "cursor": pill["primary"],
        },
        "wallpaper": str(pill.get("wallpaper", "")),
        "colors": {f"color{i}": color for i, color in enumerate(colors)},
    }, indent=2) + "\n")


def render_gtk(pill, light):
    """Keep GTK3/GTK4 and portal-backed file choosers in the wallpaper theme."""
    gtk3 = Path.home() / ".config" / "gtk-3.0"
    gtk4 = Path.home() / ".config" / "gtk-4.0"
    for directory in (gtk3, gtk4):
        directory.mkdir(parents=True, exist_ok=True)
    theme = "adw-gtk3" if light else "adw-gtk3-dark"
    icon_theme = "Papirus" if light else "Papirus-Dark"
    settings = """[Settings]
gtk-theme-name={theme}
gtk-icon-theme-name={icon_theme}
gtk-application-prefer-dark-theme={dark}
gtk-primary-button-warps-slider=false
""".format(theme=theme, icon_theme=icon_theme, dark=0 if light else 1)
    for path in (gtk3 / "settings.ini", gtk4 / "settings.ini"):
        path.write_text(settings)
    accent, accent_text = pill["primary"], pill["on_primary_container"]
    bg = pill["surface"]
    base = pill["surface_container_low"]
    raised = pill["surface_container"]
    fg = pill["bright"]
    muted = pill["subtle"]
    (gtk3 / "gtk.css").write_text(f"""/* Generated by Ricelin wallpaper palette; keep Thunar neutral gray. */
@define-color theme_fg_color {fg};
@define-color theme_text_color {fg};
@define-color theme_bg_color {bg};
@define-color theme_base_color {base};
@define-color theme_selected_bg_color {accent};
@define-color theme_selected_fg_color {accent_text};
@define-color insensitive_fg_color {muted};
window, dialog {{ background-color: {bg}; color: {fg}; }}
entry, textview, treeview, iconview {{ background-color: {base}; color: {fg}; }}
selection {{ background-color: {accent}; color: {accent_text}; }}
button.suggested-action, button.default {{ background-color: {accent}; color: {accent_text}; }}
""")
    (gtk4 / "gtk.css").write_text(f"""/* Generated by Ricelin wallpaper palette; keep Thunar neutral gray. */
window, dialog {{ background-color: {bg}; color: {fg}; }}
entry, textview, list, gridview, columnview {{ background-color: {base}; color: {fg}; }}
selection {{ background-color: {accent}; color: {accent_text}; }}
button.suggested-action, button.default {{ background-color: {accent}; color: {accent_text}; }}
headerbar, .toolbar {{ background-color: {raised}; color: {fg}; }}
""")
    gtk3_extra = f"""
/* GTK file chooser and Thunar content surfaces. */
@define-color window_bg_color {bg};
@define-color view_bg_color {base};
@define-color view_fg_color {fg};
@define-color content_view_bg {base};
@define-color text_view_bg {base};
.view, .view text, iconview, iconview text, treeview.view, textview,
filechooser, filechooser paned, filechooser scrolledwindow,
filechooser viewport, filechooser .view, filechooser .content-view,
filechooser placessidebar, filechooser .sidebar {{ background-color: {base}; color: {fg}; }}
filechooser .dialog-action-area, filechooser .path-bar, filechooser .search-bar {{ background-color: {raised}; color: {fg}; }}
"""
    gtk4_extra = f"""
/* GTK4 file chooser content surfaces. */
    window.background, .view, .content-view, .navigation-sidebar,
    .sidebar, viewport, scrolledwindow, paned, list, grid, listview, gridview,
    columnview, navigation-view, navigation-page, filechooser,
    filechooser > box, filechooser paned, filechooser scrolledwindow,
    filechooser viewport, filechooser .view, filechooser listview,
    filechooser gridview, filechooser columnview, filechooser contents,
    filechooser placessidebar, filechooser .sidebar {{ background-color: {base}; color: {fg}; }}
filechooser headerbar, filechooser .dialog-action-area, filechooser .path-bar,
filechooser .search-bar {{ background-color: {raised}; color: {fg}; }}
"""
    with (gtk3 / "gtk.css").open("a") as path:
        path.write(gtk3_extra)
    with (gtk4 / "gtk.css").open("a") as path:
        path.write(gtk4_extra)
    if Path("/usr/bin/gsettings").exists():
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", theme], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
                        "prefer-light" if light else "prefer-dark"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", icon_theme], check=False)


def main():
    if len(sys.argv) < 2:
        return 1
    wallpaper_path = ""
    if sys.argv[1] == "--hue":
        hue = (float(sys.argv[2]) % 360) / 360.0
        mode = sys.argv[3] if len(sys.argv) > 3 else "dark"
        sat = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
        sat = max(0.0, min(1.0, sat))
        mean_l = 0.85 if mode == "light" else 0.12
        chromatic = sat > 0.02
    else:
        wallpaper = sys.argv[1]
        wallpaper_path = wallpaper
        if not Path(wallpaper).is_file():
            return 0
        hue, sat, mean_l = analyze(wallpaper)
        chromatic = hue is not None
        if not chromatic:
            hue, sat = 0.09, 0.0
    CACHE.mkdir(parents=True, exist_ok=True)

    # Brightness alone should not wash chromatic wallpapers into white. Keep a
    # dark aesthetic for colorful wallpapers; use light mode only when the
    # wallpaper is genuinely bright and close to grayscale.
    light = mean_l >= 0.72 and not chromatic
    mat = None
    if wallpaper_path:
        try:
            mat = matugen_image(wallpaper_path, "light" if light else "dark")
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            mat = None

    if mat and isinstance(mat.get("colors"), dict):
        colors = mat["colors"]
        mode = "light" if light else "dark"
        # Consume Material's tonal roles directly. These roles are deliberately
        # shared by GTK, Firefox, the terminal, Vesktop and the shell so the
        # apps agree without flattening everything into one HSL hue.
        fallback = tint(hue, min(max(sat, 0.34 if chromatic else 0.0), 0.56),
                        0.78 if light else 0.10)
        pill = {
            "surface": role(colors, "surface", mode, fallback),
            "surface_container_low": role(colors, "surface_container_low", mode, fallback),
            "surface_container": role(colors, "surface_container", mode, fallback),
            "surface_container_high": role(colors, "surface_container_high", mode, fallback),
            "surface_container_highest": role(colors, "surface_container_highest", mode, fallback),
            "outline_variant": role(colors, "outline_variant", mode, fallback),
            "primary": role(colors, "primary", mode, fallback),
            "secondary": role(colors, "secondary", mode, fallback),
            "tertiary": role(colors, "tertiary", mode, fallback),
            "primary_container": role(colors, "primary_container", mode, fallback),
            "on_primary_container": role(colors, "on_primary_container", mode,
                                          "#111319" if light else "#ffffff"),
            "outline": role(colors, "outline", mode, fallback),
            "bright": role(colors, "on_surface", mode, "#191c21" if light else "#e1e2ea"),
            "subtle": role(colors, "on_surface_variant", mode, "#414752" if light else "#c1c6d4"),
            "dim": role(colors, "outline", mode, "#727783" if light else "#8b919d"),
            "cream": role(colors, "on_surface", mode, "#191c21" if light else "#e1e2ea"),
            "faint": role(colors, "outline_variant", mode, fallback),
            "icon_dim": role(colors, "on_surface_variant", mode, "#414752" if light else "#c1c6d4"),
            "tick_rest": role(colors, "on_surface_variant", mode, "#414752" if light else "#c1c6d4"),
        }
    else:
        # Keep the old path only as a safety fallback if Matugen cannot parse
        # a particular image.
        surf_sat = min(max(sat, 0.34 if chromatic else 0.0), 0.56)
        base = lerp(mean_l, 0.0, 0.40, 0.045, 0.20)
        pill = {name: tint(hue, surf_sat, base + step) for name, step in zip(SURF_NAMES, DARK_STEPS)}
        pill["primary"] = tint(hue, min(max(sat, 0.30) + 0.12, 0.82), 0.70)
        pill["secondary"] = tint(hue, 0.25, 0.62)
        pill["tertiary"] = tint((hue + 0.08) % 1.0, 0.35, 0.68)
        pill["primary_container"] = tint(hue, min(max(sat, 0.30) + 0.18, 0.9), 0.34)
        pill["on_primary_container"] = "#ffffff"
        pill["outline"] = tint(hue, surf_sat, base + 0.35)
        for key, (lit, st) in zip(TEXT_KEYS, DARK_TEXT):
            pill[key] = tint(hue, st, lit)
    (CACHE / "colors.json").write_text(json.dumps(pill, indent=2) + "\n")
    render_vesktop(pill, hue, sat, light)
    render_spotify(pill)
    pill["wallpaper"] = wallpaper_path
    render_pywalfox(pill)
    render_gtk(pill, light)
    render_fastfetch(pill)

    try:
        terminal_mode = "light" if light else "dark"
        if mat and isinstance(mat.get("base16"), dict):
            b = {k: role(mat["base16"], k, terminal_mode, "#000000")
                 for k in mat["base16"]}
        else:
            b = {k: v[terminal_mode]["color"] for k, v in
                 matugen(tint(hue, sat, 0.45) if chromatic else "#787878")["base16"].items()}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return 0

    # Keep the terminal's main background exactly equal to the shared surface.
    terminal_bg = pill["surface"]
    terminal_fg = pill["bright"]
    terminal_selection = pill["surface_container_highest"]

    (CACHE / "hypr-colors.lua").write_text(
        'return {\n    active = "%s",\n    inactive = "%s",\n}\n'
        % (pill["primary"], b["base01"]))

    lines = [
        f'background = {terminal_bg}',
        f'foreground = {terminal_fg}',
        f'cursor-color = {pill["primary"]}',
        f'selection-background = {terminal_selection}',
        f'selection-foreground = {terminal_fg}',
    ]
    for i in range(16):
        lines.append(f'palette = {i}={b["base%02x" % i]}')
    (CACHE / "ghostty-colors").write_text("\n".join(lines) + "\n")
    kitty = [
        f'background            {terminal_bg}',
        f'foreground            {terminal_fg}',
        f'cursor                {terminal_fg}',
        f'selection_background  {pill["on_primary_container"]}',
        f'selection_foreground  {terminal_fg}',
    ]
    for i in range(16):
        kitty.append(f'color{i}                {b["base%02x" % i]}')
    kitty.extend([
        f'color255              {pill["surface_container_highest"]}',
        f'color254              {pill["primary_container"]}',
        f'color253              {b["base0d"]}',
        f'color252              {pill["surface_container_highest"]}',
        f'color251              {b["base0e"]}',
        f'color250              {pill["surface_container_high"]}',
        f'color249              {b["base08"]}',
        f'color248              {pill["surface_container"]}',
        f'color240              {b["base07"]}',
        f'color243              {pill["primary"]}',
        f'color244              {b["base08"]}',
        f'color245              {pill["outline_variant"]}',
        f'color235              {b["base07"]}',
    ])
    (CACHE / "kitty-colors.conf").write_text("\n".join(kitty) + "\n")
    subprocess.run([str(Path.home() / ".local/bin/ricelin-personal-palette.py")], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
