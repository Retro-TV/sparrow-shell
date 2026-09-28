from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "quickshell/sparrow/scripts/wallpaper.sh"


class WallpaperRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sparrow-wallpaper-test-")
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls"
        self.media = self.root / "wallpapers"
        self.media.mkdir()
        self.clip = self.media / "motion.mp4"
        self.clip.write_bytes(b"test video")
        self.image = self.media / "still.png"
        self.image.write_bytes(b"test image")
        self.gif = self.media / "motion.gif"
        self.gif.write_bytes(b"test gif")

        self._write_executable("awww", """#!/usr/bin/python3
import os, sys
with open(os.environ['SPARROW_TEST_CALLS'], 'a') as stream:
    stream.write('awww ' + ' '.join(sys.argv[1:]) + '\\n')
sys.exit(0)
""")
        self._write_executable("mpvpaper", """#!/usr/bin/python3
import json, os, sys, time
with open(os.environ['SPARROW_TEST_CALLS'], 'a') as stream:
    stream.write('mpvpaper ' + json.dumps(sys.argv[1:]) + '\\n')
while True:
    time.sleep(60)
""")
        self._write_executable("ffmpeg", """#!/usr/bin/python3
import sys
open(sys.argv[-1], 'wb').write(b'frame')
""")
        self._write_executable("jq", """#!/bin/sh
case "$*" in
  *wallpaperDir*) printf '\\n' ;;
  *paletteMode*) printf 'dynamic\\n' ;;
  *paletteVariant*) printf 'auto\\n' ;;
  *appearanceMode*) printf 'auto\\n' ;;
  *) printf '\\n' ;;
esac
""")
        self._write_executable("python3", """#!/usr/bin/python3
import os, sys
with open(os.environ['SPARROW_TEST_CALLS'], 'a') as stream:
    stream.write('palette\\n')
""")

        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.root),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "SPARROW_TEST_CALLS": str(self.calls),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
        })

    def tearDown(self) -> None:
        self._stop_all()
        self.temp.cleanup()

    def _write_executable(self, name: str, contents: str) -> None:
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o700)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), *args], env=self.env,
            text=True, capture_output=True, timeout=20, check=check,
        )

    def _select(self, path: Path) -> None:
        result = self._run("set", str(path), "", "eDP-1", "eDP-1", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def _calls(self, prefix: str) -> list[str]:
        if not self.calls.exists():
            return []
        return [line for line in self.calls.read_text().splitlines() if line.startswith(prefix)]

    def _pidfile(self) -> Path:
        return self.root / "state/sparrow-shell/mpvpaper-eDP-1.pid"

    def _stop_all(self) -> None:
        if self._pidfile().is_file():
            try:
                os.kill(int(self._pidfile().read_text()), signal.SIGTERM)
            except (OSError, ValueError):
                pass
            time.sleep(0.05)

    def test_video_and_gif_use_mpvpaper_and_images_use_awww_only(self) -> None:
        self._select(self.clip)
        first_pid = int(self._pidfile().read_text())
        self.assertTrue(os.path.exists(f"/proc/{first_pid}"))

        self._select(self.image)
        self.assertFalse(os.path.exists(f"/proc/{first_pid}"))
        self.assertEqual(len(self._calls("mpvpaper ")), 1, self.calls.read_text())

        self._select(self.gif)
        self.assertEqual(len(self._calls("mpvpaper ")), 2)
        self.assertIn("loop-file=inf", self._calls("mpvpaper ")[-1])
        self.assertNotIn("-p", self._calls("mpvpaper ")[-1])

    def test_same_video_and_palette_recolor_do_not_restart_player(self) -> None:
        self._select(self.clip)
        first_pid = int(self._pidfile().read_text())
        self._select(self.clip)
        recolor = self._run("recolor", check=False)
        self.assertEqual(recolor.returncode, 0, recolor.stderr)
        self.assertEqual(len(self._calls("mpvpaper ")), 1, self.calls.read_text())
        self.assertEqual(int(self._pidfile().read_text()), first_pid)
        self.assertEqual(len(self._calls("palette")), 3)

    def test_concurrent_startup_and_selection_do_not_duplicate_player(self) -> None:
        command = ["bash", str(SCRIPT), "set", str(self.clip), "", "eDP-1", "eDP-1"]
        first = subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = first.communicate(timeout=20)
        out2, err2 = second.communicate(timeout=20)
        self.assertEqual(first.returncode, 0, err1 or out1)
        self.assertEqual(second.returncode, 0, err2 or out2)
        self.assertEqual(len(self._calls("mpvpaper ")), 1)


if __name__ == "__main__":
    unittest.main()
