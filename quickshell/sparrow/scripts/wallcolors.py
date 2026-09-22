#!/usr/bin/env python3
"""Generate Sparrow's Ricelin-derived palette and Niri border color fragment."""
import colorsys
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageStat

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "sparrow-shell"
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


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: wallcolors.py IMAGE | --hue DEGREES dark|light SATURATION")
    mode = "dark"
    if sys.argv[1] == "--hue":
        hue = float(sys.argv[2]) % 360 / 360
        mode = "light" if len(sys.argv) >= 4 and sys.argv[3] == "light" else "dark"
        sat = max(0, min(1, float(sys.argv[4]) if len(sys.argv) > 4 else .5))
        chromatic = sat > .02
    else:
        wallpaper = Path(sys.argv[1])
        if not wallpaper.is_file():
            raise SystemExit(f"wallcolors: image not found: {wallpaper}")
        hue, sat, mean_l, chromatic = analyze(wallpaper)
    # Brightness never selects a light scheme.  Matugen's wallpaper-seeded
    # Material tonal palettes provide a perceptual, hue-preserving dark ramp.
    seed = tint(hue, sat, .45) if chromatic else "#787878"
    command = ["matugen", "color", "hex", seed, "-m", mode if sys.argv[1] == "--hue" else "dark", "-j", "hex"]
    if not chromatic:
        # Matugen's default tonal-spot scheme invents a blue-green hue for an
        # achromatic seed; its native monochrome scheme preserves grayscale.
        command.extend(["-t", "scheme-monochrome"])
    matugen = subprocess.run(command,
                             check=True, capture_output=True, text=True)
    generated = json.loads(matugen.stdout)
    material = generated["colors"]
    scheme = mode if sys.argv[1] == "--hue" else "dark"
    role = lambda name: material[name][scheme]["color"]
    surfaces = {"source_color": seed}
    if scheme == "dark":
        tones = generated["palettes"]["primary" if chromatic else "neutral"]
        tone = lambda value: tones[str(value)]["color"]
        surfaces.update(background=tone(5), surface=tone(10),
                         surface_container_lowest=tone(5), surface_container_low=tone(15),
                         surface_container=tone(20), surface_container_high=tone(25),
                         surface_container_highest=tone(30), surface_bright=tone(40),
                         outline_variant=tone(35), outline=tone(60))
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
    if scheme == "dark" and not chromatic:
        # The Material monochrome scheme can inherit a default blue-green hue
        # when the source has no defined hue. Use its neutral tonal palette for
        # wallpaper UI roles instead of letting that fallback invent a color.
        surfaces.update(primary=tone(80), on_primary=tone(20), primary_container=tone(30),
                        on_primary_container=tone(90), secondary=tone(70), on_secondary=tone(20),
                        secondary_container=tone(30), on_secondary_container=tone(90),
                        tertiary=tone(70), on_tertiary=tone(20), tertiary_container=tone(30),
                        on_tertiary_container=tone(90), outline=tone(60), outline_variant=tone(35))
    surfaces.update(cream=surfaces["on_surface"], bright=surfaces["on_surface"],
                    subtle=surfaces["on_surface_variant"],
                    dim=tone(80) if scheme == "dark" else role("on_surface_variant"),
                    faint=tone(70) if scheme == "dark" else role("on_surface_variant"),
                    icon_dim=tone(90) if scheme == "dark" else role("on_surface"),
                    tick_rest=tone(80) if scheme == "dark" else role("on_surface_variant"))
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


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"wallcolors: {exc}", file=sys.stderr)
        raise SystemExit(1)
