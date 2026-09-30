from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.parse


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "quickshell/sparrow/scripts/wallpaper-search.sh"
KEY_HELPER = REPO / "quickshell/sparrow/scripts/wallhaven-key.py"


MOCK_PYTHON = r'''#!/usr/bin/python3
import json, os, sys, urllib.request
sys.dont_write_bytecode = True
source = sys.stdin.read()
script_args = sys.argv[2:] if len(sys.argv) > 1 and sys.argv[1] == "-" else sys.argv[1:]
sys.argv = ["wallpaper-search.py", *script_args]
entries = [
    {"purity": purity, "path": f"https://img.example/{purity}.jpg",
     "url": f"https://wallhaven.cc/w/{purity}", "dimension_x": 1920, "dimension_y": 1080,
     "thumbs": {"small": f"https://th.example/{purity}.jpg"}}
    for purity in ("sfw", "sketchy", "nsfw")
]
class Response:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return json.dumps({"data": entries}).encode()
def urlopen(request, timeout=0):
    with open(os.environ["SPARROW_TEST_URL"], "w") as capture:
        capture.write(request.full_url)
    return Response()
urllib.request.urlopen = urlopen
exec(compile(source, "wallpaper-search.py", "exec"), {"__name__": "__main__"})
'''


class WallpaperSearchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sparrow-wallhaven-search-")
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        shim = self.bin / "python3"
        shim.write_text(MOCK_PYTHON)
        shim.chmod(0o700)
        self.capture = self.root / "request-url"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "SPARROW_TEST_URL": str(self.capture),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def save_test_key(self, value: str) -> None:
        subprocess.run(
            [sys.executable, str(KEY_HELPER), "set"],
            input=value,
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )

    def search(self, *options: str) -> tuple[dict, dict[str, list[str]]]:
        result = subprocess.run(
            ["bash", str(SCRIPT), "search", "quiet forest", "all", *options],
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return json.loads(result.stdout), urllib.parse.parse_qs(self.capture.read_text().split("?", 1)[1])

    def test_custom_categories_purities_toplist_period_and_key(self) -> None:
        self.save_test_key("synthetic-wallhaven-test-key")
        result, params = self.search("011", "101", "toplist", "1y")
        self.assertEqual(params["categories"], ["011"])
        self.assertEqual(params["purity"], ["101"])
        self.assertEqual(params["sorting"], ["toplist"])
        self.assertEqual(params["topRange"], ["1y"])
        self.assertEqual(params["apikey"], ["synthetic-wallhaven-test-key"])
        self.assertEqual([item["url"].rsplit("/", 1)[-1] for item in result["results"]], ["sfw", "nsfw"])

    def test_no_key_keeps_search_limited_to_sfw_and_sketchy(self) -> None:
        result, params = self.search()
        self.assertEqual(params["categories"], ["110"])
        self.assertEqual(params["purity"], ["110"])
        self.assertNotIn("apikey", params)
        self.assertEqual([item["url"].rsplit("/", 1)[-1] for item in result["results"]], ["sfw", "sketchy"])

    def test_views_sort_omits_toplist_period_and_supports_people_category(self) -> None:
        result, params = self.search("001", "010", "views", "1M")
        self.assertEqual(params["categories"], ["001"])
        self.assertEqual(params["purity"], ["010"])
        self.assertEqual(params["sorting"], ["views"])
        self.assertNotIn("topRange", params)
        self.assertEqual([item["url"].rsplit("/", 1)[-1] for item in result["results"]], ["sketchy"])

    def test_nsfw_without_key_is_a_provider_error_not_an_empty_result(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT), "search", "quiet forest", "all", "110", "001", "toplist", "1M"],
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
            check=False,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["results"], [])
        self.assertIn("API key", payload["error"])
        self.assertFalse(self.capture.exists())


if __name__ == "__main__":
    unittest.main()
