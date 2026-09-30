#!/usr/bin/env bash
set -euo pipefail
UA='Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/126.0'
cmd="${1:-}"; shift || true

search() {
    local query="${1:-}" kind="${2:-all}"
    [[ -n "$query" ]] || { echo '{"ok":true,"results":[]}'; return; }
    if [[ "$kind" == motion ]]; then
        UA="$UA" python3 - "$query" <<'PY'
import concurrent.futures, json, os, re, sys, urllib.parse, urllib.request
ua = os.environ['UA']
query = sys.argv[1]
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
    q=urllib.parse.quote(query); html=fetch('https://moewalls.com/?s='+q)
    urls=list(dict.fromkeys(re.findall(r'href="(https://moewalls\.com/[a-z0-9-]+/[a-z0-9-]+-live-wallpaper/)"',html)))[:24]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: results=[x for x in ex.map(item,urls) if x]
    print(json.dumps({'ok':True,'query':query,'kind':'motion','results':results}))
except Exception:
    print(json.dumps({'ok':False,'query':query,'kind':'motion','error':'Moewalls search unavailable','results':[]}))
PY
        return
    fi
    python3 - "$query" "$kind" <<'PY'
import fcntl, json, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

query = sys.argv[1]
kind = sys.argv[2]
cache = pathlib.Path(os.environ.get('XDG_CACHE_HOME', pathlib.Path.home() / '.cache')) / 'sparrow-shell'
cache.mkdir(parents=True, exist_ok=True)
lock_path = cache / 'wallhaven-search-rate.lock'

def result(ok, results=(), error=''):
    print(json.dumps({'ok': ok, 'query': query, 'kind': kind, 'results': list(results), **({'error': error} if error else {})}))

try:
    params = urllib.parse.urlencode({
        'q': query,
        'categories': '111',
        'purity': '100',
        'sorting': 'relevance',
        'page': '1',
    })
    request = urllib.request.Request(
        'https://wallhaven.cc/api/v1/search?' + params,
        headers={'User-Agent': 'SparrowShell/1.0 (wallpaper search)'},
    )
    # Keep at least 1.5s between requests across picker processes (40/minute,
    # below Wallhaven's unauthenticated 45/minute limit).
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        try:
            last_request = float(lock.read().strip() or '0')
        except ValueError:
            last_request = 0.0
        delay = 1.5 - (time.time() - last_request)
        if delay > 0:
            time.sleep(delay)
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)

    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise ValueError('invalid response')
    items = []
    for entry in payload['data'][:24]:
        thumbs = entry.get('thumbs') or {}
        image = entry.get('path')
        page = entry.get('url')
        if entry.get('purity') != 'sfw' or not image or not page:
            continue
        items.append({
            'image': image,
            'thumb': thumbs.get('small') or thumbs.get('large') or image,
            'url': page,
            'w': entry.get('dimension_x') or 0,
            'h': entry.get('dimension_y') or 0,
        })
    result(True, items)
except urllib.error.HTTPError as exc:
    message = 'Wallhaven rate limit reached' if exc.code == 429 else f'Wallhaven returned HTTP {exc.code}'
    result(False, error=message)
except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
    result(False, error='Wallhaven search unavailable')
PY
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
    local referer='https://wallhaven.cc/'
    [[ "$url" == *moewalls.com/download.php* ]] && referer='https://moewalls.com/'
    curl -fsSL --max-time 600 -A "$UA" -e "$referer" -o "$tmp" "$url"
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
