#!/usr/bin/env bash
set -euo pipefail

state_root="${XDG_STATE_HOME:-$HOME/.local/state}/sparrow-shell"
flags_file="${XDG_STATE_HOME:-$HOME/.local/state}/sparrow-shell/flags.json"
configured_dir="$(jq -r '.wallpaperDir // ""' "$flags_file" 2>/dev/null || true)"
wall_dir="${SPARROW_WALLPAPER_DIR:-${configured_dir:-$HOME/Pictures/wallpapers}}"
state="$state_root/wallpaper"
map="$state_root/wallpaper-map"
bag="$state_root/wallpaper-bag"
still="$state_root/wallpaper-still.png"
helper="$(cd -- "$(dirname -- "$0")" && pwd)"
default_wallpaper="$helper/../wallpapers/default.png"
focused_output_name=""
outputs_csv=""
mkdir -p "$state_root"

is_video() { [[ "$1" =~ \.(mp4|webm|mkv|mov)$ ]]; }
is_media() { [[ "$1" =~ \.(jpg|jpeg|png|gif|webp|mp4|webm|mkv|mov)$ ]]; }
outputs() { [[ -n "$outputs_csv" ]] && tr ',' '\n' <<< "$outputs_csv"; }
focused_output() { printf '%s\n' "$focused_output_name"; }
map_get() { awk -F '\t' -v o="$1" '$1 == o {sub($1 FS, ""); print; exit}' "$map" 2>/dev/null || true; }
map_put() {
    local out="$1" pic="$2" tmp="$map.tmp"
    awk -F '\t' -v o="$out" '$1 != o' "$map" 2>/dev/null > "$tmp" || true
    printf '%s\t%s\n' "$out" "$pic" >> "$tmp"
    mv -f -- "$tmp" "$map"
}
map_put_all() {
    local pic="$1" tmp="$map.tmp" out
    : > "$tmp"
    while IFS= read -r out; do [[ -n "$out" ]] && printf '%s\t%s\n' "$out" "$pic" >> "$tmp"; done < <(outputs)
    mv -f -- "$tmp" "$map"
}
ensure_awww() {
    awww query >/dev/null 2>&1 && return 0
    if [[ "${SPARROW_AWWW_DAEMON_MANAGED:-0}" == 1 ]]; then
        for _ in {1..40}; do awww query >/dev/null 2>&1 && return 0; sleep 0.15; done
        echo "Sparrow wallpaper: systemd-managed awww daemon did not become available" >&2
        return 1
    fi
    if pgrep -x awww-daemon >/dev/null 2>&1; then
        for _ in {1..40}; do awww query >/dev/null 2>&1 && return 0; sleep 0.15; done
        echo "Sparrow wallpaper: existing awww daemon did not become available" >&2
        return 1
    fi
    awww-daemon >/dev/null 2>&1 &
    for _ in {1..40}; do awww query >/dev/null 2>&1 && return 0; sleep 0.15; done
    echo "Sparrow wallpaper: awww daemon did not become available" >&2
    return 1
}
awww_image_for_output() {
    awww query --json | jq -r --arg output "$1" '.[""][]? | select(.name == $output) | .displaying.image // empty'
}
mpvpaper_pid_is_sparrow() {
    local pid="$1" out="$2" expected_pic="${3:-}" cmd
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    cmd="$(tr '\0' ' ' 2>/dev/null < "/proc/$pid/cmdline" || true)"
    [[ "$cmd" == *mpvpaper* && "$cmd" == *"input-ipc-server=/tmp/sparrow-wallpaper-$out"* ]] || return 1
    [[ -z "$expected_pic" || "$cmd" == *" $out $expected_pic" ]]
}
video_is_current() {
    local out="$1" pic="$2" safe_out pidfile pid=""
    safe_out="${out//[^[:alnum:]_.-]/_}"
    pidfile="$state_root/mpvpaper-$safe_out.pid"
    [[ -r "$pidfile" ]] || return 1
    read -r pid < "$pidfile" || true
    mpvpaper_pid_is_sparrow "${pid:-}" "$out" "$pic"
}
stop_video() {
    local out="$1" safe_out pidfile pid=""
    safe_out="${out//[^[:alnum:]_.-]/_}"
    pidfile="$state_root/mpvpaper-$safe_out.pid"
    [[ -r "$pidfile" ]] || return 0
    read -r pid < "$pidfile" || true
    if mpvpaper_pid_is_sparrow "${pid:-}" "$out"; then
        kill "$pid" 2>/dev/null || true
        for _ in {1..30}; do
            mpvpaper_pid_is_sparrow "$pid" "$out" || break
            sleep 0.1
        done
        if mpvpaper_pid_is_sparrow "$pid" "$out"; then
            kill -KILL "$pid" 2>/dev/null || true
            for _ in {1..10}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.05; done
        fi
    fi
    rm -f -- "$pidfile"
    rm -f -- "/tmp/sparrow-wallpaper-$out"
}
start_video() {
    local pic="$1" out="$2" safe_out pidfile log pid
    safe_out="${out//[^[:alnum:]_.-]/_}"
    pidfile="$state_root/mpvpaper-$safe_out.pid"
    log="$state_root/mpvpaper-$safe_out.log"
    rm -f -- "/tmp/sparrow-wallpaper-$out"
    setsid mpvpaper -p -o "no-audio loop-file=inf hwdec=auto panscan=1.0 input-ipc-server=/tmp/sparrow-wallpaper-$out" "$out" "$pic" >"$log" 2>&1 &
    pid=$!
    for _ in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null || true
            echo "Sparrow wallpaper: mpvpaper failed on $out; see $log" >&2
            return 1
        fi
        if mpvpaper_pid_is_sparrow "$pid" "$out"; then
            printf '%s\n' "$pid" > "$pidfile"
            return 0
        fi
        sleep 0.1
    done
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo "Sparrow wallpaper: mpvpaper did not confirm startup on $out; see $log" >&2
    return 1
}
make_still() {
    local pic="$1" target="$2"
    ffmpeg -nostdin -y -loglevel error -i "$pic" -frames:v 1 -update 1 "$target.tmp.png" || { rm -f "$target.tmp.png"; return 1; }
    mv -f -- "$target.tmp.png" "$target"
}
apply_visual() {
    local pic="$1" out="${2:-}" instant="${3:-false}" show="$1" target_out previous; local -a output_args=() video_outputs=() transition_args=()
    [[ -z "$out" ]] || output_args=(--outputs "$out")
    if [[ "$instant" == true ]]; then
        transition_args=(--transition-type none)
    else
        transition_args=(--transition-type wave --transition-angle 30 --transition-wave "60,30" --transition-fps 60 --transition-step 90)
    fi
    if is_video "$pic"; then
        command -v mpvpaper >/dev/null || { echo "Sparrow wallpaper: mpvpaper is required for video wallpapers; install it to enable video playback" >&2; return 1; }
        show="$still"; make_still "$pic" "$show"
    elif [[ "${pic,,}" == *.gif ]]; then
        show="$still"; make_still "$pic" "$show"
    fi
    awww img "${output_args[@]}" "$show" "${transition_args[@]}"
    if [[ "$show" != "$pic" ]]; then
        if ! is_video "$pic"; then
            [[ "$instant" == true ]] || sleep 0.9
            awww img "${output_args[@]}" "$pic" --transition-type none
        fi
    fi
    if is_video "$pic"; then
        if [[ -n "$out" ]]; then video_outputs=("$out")
        else mapfile -t video_outputs < <(outputs); fi
        ((${#video_outputs[@]})) || { echo "Sparrow wallpaper: no Niri outputs were supplied" >&2; return 1; }
        for target_out in "${video_outputs[@]}"; do
            # mpvpaper permits one wallpaper surface per output: replace only
            # Sparrow's recorded process, and don't commit a failed launch.
            previous="$(map_get "$target_out")"
            stop_video "$target_out"
            if ! start_video "$pic" "$target_out"; then
                if [[ -f "$previous" ]] && is_video "$previous"; then
                    start_video "$previous" "$target_out" || true
                elif [[ -f "$previous" ]]; then
                    awww img --outputs "$target_out" "$previous" --transition-type none || true
                fi
                return 1
            fi
        done
    else
        if [[ -n "$out" ]]; then video_outputs=("$out")
        else
            shopt -s nullglob
            for f in "$state_root"/mpvpaper-*.pid; do
                target_out="${f##*/mpvpaper-}"; target_out="${target_out%.pid}"
                video_outputs+=("$target_out")
            done
        fi
        for target_out in "${video_outputs[@]}"; do stop_video "$target_out"; done
    fi
}
palette() {
    local pic="$1" variant="${2:-}"
    if [[ -z "$variant" ]]; then
        variant="$(jq -r '.paletteVariant // "tonal"' "$flags_file" 2>/dev/null || echo tonal)"
    fi
    if is_video "$pic" || [[ "${pic,,}" == *.gif ]]; then
        make_still "$pic" "$still" || return 1
        pic="$still"
    fi
    python3 "$helper/wallcolors.py" "$pic" --style "$variant"
}
list_media() {
    [[ -d "$wall_dir" ]] || return 0
    find "$wall_dir" -type f -print | while IFS= read -r f; do is_media "$f" && printf '%s\n' "$f"; done
}
refill_bag() {
    local current=""; [[ -r "$state" ]] && read -r current < "$state" || true
    mapfile -t shuffled < <(list_media | shuf)
    ((${#shuffled[@]})) || return 1
    if ((${#shuffled[@]} > 1)) && [[ "${shuffled[0]}" == "$current" ]]; then
        shuffled+=("${shuffled[0]}"); shuffled=("${shuffled[@]:1}")
    fi
    printf '%s\n' "${shuffled[@]}" > "$bag.tmp"
    mv -f -- "$bag.tmp" "$bag"
}
next_pic() {
    exec 9>"$bag.lock"; flock 9
    [[ -s "$bag" ]] || refill_bag || return 1
    while IFS= read -r pic; do
        if [[ -f "$pic" ]]; then
            tail -n +2 "$bag" > "$bag.tmp" || true
            mv -f -- "$bag.tmp" "$bag"
            printf '%s' "$pic"; return 0
        fi
        refill_bag || return 1
    done < "$bag"
    return 1
}
commit_state() {
    local pic="$1" out="${2:-}" tmp active
    if [[ -n "$out" ]]; then map_put "$out" "$pic"; else map_put_all "$pic"; fi
    active="$(map_get "$(focused_output)")"; [[ -n "$active" ]] || active="$pic"
    tmp="$state.tmp"; printf '%s\n' "$active" > "$tmp"; mv -f -- "$tmp" "$state"
    palette "$active" || echo "Sparrow wallpaper: wallpaper changed, but palette generation failed; keeping previous palette" >&2
}

cmd="${1:-next}"
shift || true
case "$cmd" in
    resolve) printf '%s\n' "$wall_dir" > "$state_root/wallpaper-dir.tmp"; mv -f "$state_root/wallpaper-dir.tmp" "$state_root/wallpaper-dir"; exit 0 ;;
    list-dir) printf '%s\n' "$wall_dir"; exit 0 ;;
    manual)
        python3 "$helper/wallcolors.py" --hue "${1:-30}" "${2:-dark}" "${3:-0.5}" --style "${4:-tonal}"
        exit 0 ;;
    init)
        focused_output_name="${1:-}"; outputs_csv="${2:-}"
        if [[ -z "$outputs_csv" ]]; then
            outputs_json="$(niri msg --json outputs)" || { echo "Sparrow wallpaper: could not query Niri outputs" >&2; exit 1; }
            outputs_csv="$(jq -r 'keys | join(",")' <<< "$outputs_json")"
            focused_json="$(niri msg --json focused-output)" || { echo "Sparrow wallpaper: could not query Niri focused output" >&2; exit 1; }
            focused_output_name="$(jq -r '.name // empty' <<< "$focused_json")"
        fi
        ensure_awww || exit 1
        any=false; active=""; saved="$(cat "$state" 2>/dev/null || true)"
        while IFS= read -r out; do
            [[ -n "$out" ]] || continue
            pic="$(map_get "$out")"; [[ -f "$pic" ]] || pic="$saved"
            [[ -f "$pic" ]] || pic="$default_wallpaper"
            [[ -f "$pic" ]] || pic="$(next_pic || true)"
            [[ -n "$pic" && -f "$pic" ]] || continue
            if is_video "$pic" && ! command -v mpvpaper >/dev/null; then
                echo "Sparrow wallpaper: saved video on $out not restored (mpvpaper missing)" >&2; continue
            fi
            if { is_video "$pic" && video_is_current "$out" "$pic"; } \
                    || { ! is_video "$pic" && [[ "$(awww_image_for_output "$out")" == "$pic" ]]; }; then
                map_put "$out" "$pic"; any=true
                [[ "$out" == "$(focused_output)" ]] && active="$pic"
                continue
            fi
            if apply_visual "$pic" "$out" true; then
                map_put "$out" "$pic"; any=true
                [[ "$out" == "$(focused_output)" ]] && active="$pic"
            fi
        done < <(outputs)
        if [[ "$any" == true ]]; then
            [[ -n "$active" ]] || active="$saved"
            if [[ -n "$active" ]]; then
                printf '%s\n' "$active" > "$state.tmp"
                mv -f "$state.tmp" "$state"
                palette_file="${XDG_CACHE_HOME:-$HOME/.cache}/sparrow-shell/palette.json"
                if [[ "$active" != "$saved" || ! -s "$palette_file" ]]; then
                    palette "$active" || true
                fi
            fi
        fi
        exit 0 ;;
    recolor)
        variant="${1:-}"
        focused_output_name="${2:-}"; outputs_csv="${3:-}"
        [[ -s "$state" ]] || exit 0; palette "$(cat "$state")" "$variant"; exit 0 ;;
    set)
        pic="${1:-}"; out="${2:-}"; focused_output_name="${3:-}"; outputs_csv="${4:-}"
        [[ "$out" == all ]] && out="" ;;
    next)
        focused_output_name="${1:-}"; outputs_csv="${2:-}"
        pic="$(next_pic)" || { echo "Sparrow wallpaper: no supported files in $wall_dir" >&2; exit 1; }
        out=""
        if [[ "$(jq -r '.randomScope // "all"' "$flags_file" 2>/dev/null || echo all)" == cursor ]]; then out="$focused_output_name"; fi ;;
    *) echo "usage: wallpaper.sh {init|resolve|recolor|set FILE [OUTPUT]|next}" >&2; exit 2 ;;
esac
[[ -f "$pic" ]] || { echo "Sparrow wallpaper: file not found: $pic" >&2; exit 1; }
ensure_awww || exit 1
apply_visual "$pic" "$out"
commit_state "$pic" "$out"
