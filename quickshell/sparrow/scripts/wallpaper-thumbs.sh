#!/usr/bin/env bash
set -u
wpdir="${1:-${SPARROW_WALLPAPER_DIR:-$HOME/Pictures/wallpapers}}"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/sparrow-shell/wallpaper-thumbs"
mkdir -p "$cache" || exit 1
[ -d "$wpdir" ] || exit 0
find "$wpdir" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.gif' -o -iname '*.webp' -o -iname '*.mp4' -o -iname '*.webm' -o -iname '*.mkv' -o -iname '*.mov' \) -print0 |
while IFS= read -r -d '' src; do
    name=$(basename "$src")
    thumb="$cache/$name.png"
    [ -s "$thumb" ] && [ ! "$src" -nt "$thumb" ] && continue
    tmp="$thumb.tmp.png"
    if ffmpeg -nostdin -y -loglevel error -i "$src" -frames:v 1 -vf 'scale=512:-2:force_original_aspect_ratio=decrease' -update 1 "$tmp" >/dev/null 2>&1 && [ -s "$tmp" ]; then
        mv -f -- "$tmp" "$thumb"
    else
        rm -f -- "$tmp"
    fi
done
