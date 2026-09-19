#!/usr/bin/env bash

set -u

# Use the vivid accent selected by pywal for the current wallpaper. This keeps
# the lighting solid and saturated instead of letting pale screen pixels wash
# the result toward white. The ASRock controller is deliberately targeted so
# keyboards, mice, and the microphone keep their own lighting.
interval_seconds=10
device='ASRock B650M PG Lightning'
colors_file="$HOME/.cache/wal/colors.json"

while true; do
    color=$(sed -n 's/.*"color1": "#\([0-9A-Fa-f]\{6\}\)".*/\1/p' "$colors_file" 2>/dev/null | head -1 | tr '[:lower:]' '[:upper:]')

    if [[ "$color" =~ ^[0-9A-F]{6}$ ]]; then
        # OpenRGB's command-line client remains attached to its Qt event loop;
        # let it finish device detection and applying the color, then recycle it.
        timeout 8s env QT_QPA_PLATFORM=xcb openrgb --noautoconnect \
            --device "$device" --mode static --color "$color" >/dev/null 2>&1 || true
    fi

    sleep "$interval_seconds"
done
