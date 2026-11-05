import fcntl
import subprocess
import sys
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("action_probe", Path(__file__).with_name("action-probe.py"))
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


class ActionProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.state = self.home / "sparrow-shell"
        self.state.mkdir()
        self.picture = self.home / "test image.png"
        self.picture.write_bytes(b"image test double")
        (self.state / "wallpaper").write_text(str(self.picture))
        self.env = {"XDG_STATE_HOME": str(self.home)}
        self.request = {"type": "wallpaper.output", "params": {"value": str(self.picture)}, "output": "DP-1"}

    def run_probe(self, request=None, which=lambda name: "/fake/" + name):
        return probe_module.probe(request or self.request, self.env, which)

    def test_preview_reads_state_and_does_not_change_any_files(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob("*") if p.is_file()}
        result = self.run_probe()
        self.assertTrue(result["supported"])
        self.assertEqual(result["value"], str(self.picture))
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_absent_state_is_not_created(self):
        result = probe_module.probe(self.request, {"XDG_STATE_HOME": str(self.home / "absent")}, lambda _: "/fake")
        self.assertTrue(result["supported"])
        self.assertFalse((self.home / "absent").exists())

    def test_missing_wallpaper_and_removed_restore_file(self):
        self.picture.unlink()
        self.assertFalse(self.run_probe()["supported"])

    def test_unreadable_wallpaper(self):
        with patch.object(probe_module.os, "access", return_value=False):
            self.assertFalse(self.run_probe()["supported"])

    def test_missing_tools_and_video_dependencies(self):
        self.assertIn("matugen", self.run_probe(which=lambda n: None if n == "matugen" else "/fake")["message"])
        self.picture = self.home / "video.mp4"
        self.picture.write_bytes(b"video")
        self.request["params"]["value"] = str(self.picture)
        self.assertIn("mpvpaper", self.run_probe(which=lambda n: None if n == "mpvpaper" else "/fake")["message"])

    def test_output_map_and_generation_change(self):
        mapping = self.state / "wallpaper-map"
        mapping.write_text("DP-1\t/other.png\n")
        first = self.run_probe()
        self.assertEqual(first["value"], "/other.png")
        mapping.write_text("DP-1\t/away.png\n")
        mapping.write_text("DP-1\t/other.png\n")
        self.assertNotEqual(first["revision"], self.run_probe()["revision"])

    def test_appearance_requires_current_wallpaper(self):
        request = {"type": "appearance.mode", "params": {"value": "dark"}}
        self.assertTrue(self.run_probe(request)["supported"])
        (self.state / "wallpaper").unlink()
        self.assertFalse(self.run_probe(request)["supported"])

    def test_appearance_reads_saved_preference_without_creating_flags(self):
        request = {"type": "appearance.mode", "params": {"value": "light"}}
        self.assertEqual(self.run_probe(request)["persistedMode"], "auto")
        self.assertFalse((self.state / "flags.json").exists())
        (self.state / "flags.json").write_text(json.dumps({"appearanceMode": "light", "paletteMode": "dynamic"}))
        self.assertEqual(self.run_probe(request)["persistedMode"], "light")

    def test_unknown_action_and_unsupported_file_type(self):
        self.assertFalse(self.run_probe({"type": "shell.command"})["supported"])
        other = self.home / "data.txt"
        other.write_text("data")
        self.request["params"]["value"] = str(other)
        self.assertFalse(self.run_probe()["supported"])

    def test_recovery_cannot_unlock_a_writer_surviving_shell_restart(self):
        lock = self.state / "wallpaper.lock"
        with lock.open("w") as writer:
            fcntl.flock(writer, fcntl.LOCK_EX)
            # A separate process models the newly started shell's probe.
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("action-probe.py"))],
                                    input='{"type":"recovery"}', text=True, capture_output=True,
                                    env=dict(os.environ, **self.env), timeout=3, check=True)
            evidence = json.loads(result.stdout)
            self.assertFalse(evidence["safe"])
            self.assertIn("writer is active", evidence["message"])
        self.assertTrue(self.run_probe({"type": "recovery"})["safe"])

    def test_recovery_does_not_create_state_or_a_lock(self):
        missing = self.home / "missing"
        result = probe_module.probe({"type": "recovery"}, {"XDG_STATE_HOME": str(missing)})
        self.assertTrue(result["safe"])
        self.assertFalse(missing.exists())

    def test_mixed_generation_state_read_is_rejected(self):
        mapping = self.state / "wallpaper-map"
        mapping.write_text("DP-1\t" + str(self.picture) + "\n")
        original = probe_module.read_state
        def concurrent_edit(path):
            if path.name == "flags.json":
                mapping.write_text("DP-1\t/changed.png\n")
            return original(path)
        with patch.object(probe_module, "read_state", side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValueError, "state changed"):
                self.run_probe()

    def test_duplicate_output_map_and_fifo_fail_closed(self):
        mapping = self.state / "wallpaper-map"
        mapping.write_text("DP-1\t/a.png\nDP-1\t/b.png\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_probe()
        mapping.unlink()
        os.mkfifo(mapping)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.run_probe()

    def test_asset_change_invalidates_revision_and_unrelated_flags_do_not(self):
        before = self.run_probe()
        (self.state / "flags.json").write_text('{"dnd":true}')
        self.assertEqual(before["revision"], self.run_probe()["revision"])
        self.picture.write_bytes(b"replacement image")
        after = self.run_probe()
        self.assertNotEqual(before["revision"], after["revision"])
        self.assertNotEqual(before["valueFingerprint"], after["valueFingerprint"])

    def test_video_recolor_also_requires_ffmpeg(self):
        movie = self.home / "test.mp4"
        movie.write_bytes(b"video")
        (self.state / "wallpaper").write_text(str(movie))
        result = self.run_probe({"type": "appearance.mode"}, which=lambda name: None if name == "ffmpeg" else "/fake")
        self.assertFalse(result["supported"])
        self.assertIn("ffmpeg", result["message"])

    def test_empty_xdg_state_uses_home_fallback(self):
        fallback = self.home / ".local/state/sparrow-shell"
        fallback.mkdir(parents=True)
        (fallback / "wallpaper").write_text(str(self.picture))
        result = probe_module.probe(self.request, {"XDG_STATE_HOME": "", "HOME": str(self.home)}, lambda name: "/fake")
        self.assertTrue(result["supported"])
        self.assertEqual(result["value"], str(self.picture))


if __name__ == "__main__":
    unittest.main()
