from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "quickshell/sparrow/scripts/wallhaven-key.py"


class WallhavenKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sparrow-wallhaven-key-")
        self.state = Path(self.temp.name) / "state"
        self.env = {**os.environ, "XDG_STATE_HOME": str(self.state)}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_helper(self, action: str, data: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), action],
            input=data,
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )

    def test_key_is_saved_privately_and_status_does_not_reveal_it(self) -> None:
        secret = "wallhaven-test-token-123"
        saved = self.run_helper("set", secret)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertNotIn(secret, saved.stdout + saved.stderr)

        path = self.state / "sparrow-shell/secrets/wallhaven-api-key"
        self.assertEqual(path.read_text().strip(), secret)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        status = self.run_helper("status")
        self.assertEqual(json.loads(status.stdout), {"configured": True})
        self.assertNotIn(secret, status.stdout + status.stderr)

    def test_remove_deletes_key_and_invalid_key_is_rejected(self) -> None:
        self.assertNotEqual(self.run_helper("set", "bad\tkey").returncode, 0)
        self.assertEqual(self.run_helper("set", "token").returncode, 0)
        removed = self.run_helper("remove")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse((self.state / "sparrow-shell/secrets/wallhaven-api-key").exists())
        self.assertEqual(json.loads(removed.stdout), {"configured": False})

    def test_set_finishes_on_newline_while_stdin_remains_open(self) -> None:
        process = subprocess.Popen(
            [sys.executable, str(HELPER), "set"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )
        assert process.stdin is not None
        process.stdin.write("synthetic-open-pipe-key\n")
        process.stdin.flush()
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=2)
            process.communicate()
            self.fail("key helper waited for stdin EOF after receiving a complete key line")
        finally:
            process.stdin.close()
        assert process.stdout is not None
        assert process.stderr is not None
        stdout = process.stdout.read()
        stderr = process.stderr.read()
        process.stdout.close()
        process.stderr.close()
        self.assertEqual(returncode, 0, stderr or stdout)
        self.assertTrue((self.state / "sparrow-shell/secrets/wallhaven-api-key").exists())


if __name__ == "__main__":
    unittest.main()
