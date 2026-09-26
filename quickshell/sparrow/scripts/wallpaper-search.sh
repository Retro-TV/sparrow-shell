#!/usr/bin/env bash
set -euo pipefail
UA='Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/126.0'
cmd="${1:-}"; shift || true

search() {
    local query="${1:-}" kind="${2:-all}"
    [[ -n "$query" ]] || { echo '[]'; return; }
    if [[ "$kind" == motion ]]; then
        UA="$UA" python3 - "$query" <<'PY'
import concurrent.futures, json, os, re, sys, urllib.parse, urllib.request
ua = os.environ['UA']
def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':ua,'Referer':'https://moewalls.com/'})
    with urllib.request.urlopen(req,timeout=12) as r: return r.read().decode('utf-8','ignore')
def item(url):
    html=fetch(url); prev=re.search(r'<source src="(/wp-content/uploads/preview/[^"]+)',html)
    token=re.search(r'id="moe-download"[^>]*data-url="([^"]+)',html); poster=re.search(r'poster="([^"]+)',html)
    size=re.search(r'resolutions-(\d+)x(\d+)',html)
    if not prev or not token: return None
    return {'image':'https://go.moewalls.com/download.php?video='+token.group(1),
      'thumb':urllib.parse.urljoin('https://moewalls.com/',poster.group(1)) if poster else '',
      'preview':urllib.parse.urljoin('https://moewalls.com/',prev.group(1)),
      'w':int(size.group(1)) if size else 0,'h':int(size.group(2)) if size else 0}
try:
    q=urllib.parse.quote(sys.argv[1]); html=fetch('https://moewalls.com/?s='+q)
    urls=list(dict.fromkeys(re.findall(r'href="(https://moewalls\.com/[a-z0-9-]+/[a-z0-9-]+-live-wallpaper/)"',html)))[:24]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: print(json.dumps([x for x in ex.map(item,urls) if x]))
except Exception: print('[]')
PY
        return
    fi
    local enc vqd raw filter=',,,'
    [[ "$kind" == still ]] && filter='type:photo'
    enc=$(jq -rn --arg q "$query" '$q|@uri')
    vqd=$(curl -fsSL --max-time 15 "https://duckduckgo.com/?q=${enc}&iax=images&ia=images" -A "$UA" | grep -oP 'vqd=\\?"?\K[0-9-]+' | head -1 || true)
    [[ -n "$vqd" ]] || { echo '[]'; return; }
    raw=$(curl -fsSL --max-time 20 "https://duckduckgo.com/i.js?l=us-en&o=json&q=${enc}&vqd=${vqd}&f=${filter}&p=-1" -A "$UA" -H 'Referer: https://duckduckgo.com/') || { echo '[]'; return; }
    jq -c --arg kind "$kind" '(.results // []) | if $kind == "motion" then map(select((.image // "")|test("\\.gif(\\?|$)";"i"))) elif $kind == "still" then map(select((.image // "")|test("\\.gif(\\?|$)";"i")|not)) else . end | map({image:.image,thumb:(.thumbnail//.image),w:(.width//0),h:(.height//0)}) | map(select(.image!=null and .image!="")) | .[0:60]' <<< "$raw" 2>/dev/null || echo '[]'
}

download() {
    local url="${1:-}" flags="${XDG_STATE_HOME:-$HOME/.local/state}/sparrow-shell/flags.json" dir
    dir=$(jq -r '.wallpaperDir // ""' "$flags" 2>/dev/null || true)
    [[ -n "$dir" ]] || dir="${SPARROW_WALLPAPER_DIR:-$HOME/Pictures/wallpapers}"
    dir="$dir/downloads"; mkdir -p "$dir"
    local ext=jpg
    [[ "$url" == *moewalls.com/download.php* ]] && ext=mp4
    [[ "$url" =~ \.([Jj][Pp][Ee]?[Gg]|[Pp][Nn][Gg]|[Ww][Ee][Bb][Pp]|[Gg][Ii][Ff])([?&]|$) ]] && ext="${BASH_REMATCH[1],,}"
    [[ "$ext" != jpeg ]] || ext=jpg
    local out="$dir/sparrow-$(date +%s)-$RANDOM.$ext" tmp="$dir/.sparrow-download-$RANDOM.tmp"
    trap 'rm -f -- "$tmp"' RETURN
    curl -fsSL --max-time 600 -A "$UA" -e 'https://duckduckgo.com/' -o "$tmp" "$url"
    [[ -s "$tmp" ]] || return 1
    if [[ "$ext" != mp4 ]]; then
        local fmt
        fmt=$(magick identify -format '%m' "${tmp}[0]" 2>/dev/null | head -1 || true)
        case "$fmt" in JPEG) ext=jpg;; PNG) ext=png;; GIF) ext=gif;; WEBP) ext=webp;; *) echo "Sparrow wallpaper search: unsupported downloaded image format" >&2; return 1;; esac
        out="$dir/sparrow-$(date +%s)-$RANDOM.$ext"
    fi
    mv -- "$tmp" "$out"; printf '%s\n' "$out"
}

case "$cmd" in
    search) search "${1:-}" "${2:-all}" ;;
    download) download "${1:-}" ;;
    *) echo '[]'; exit 2 ;;
esac
