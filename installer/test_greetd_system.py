from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from greetd_system import GreetdSystemManager


REPO = Path(__file__).resolve().parents[1]


class SimulatedSystemctl:
    def __init__(self, etc_root: Path):
        self.enabled: set[str] = set()
        self.active: set[str] = set()
        self.events: list[tuple[str, ...]] = []
        self.etc_root = etc_root

    def __call__(self, args, **kwargs):
        self.events.append(tuple(args))
        code, stdout = 0, ""
        if args[0] == "systemctl":
            operation, unit = args[1], args[-1] if len(args) > 2 else ""
            if operation == "is-enabled":
                code = 0 if unit in self.enabled else 1
                stdout = "enabled" if code == 0 else "disabled"
            elif operation == "is-active":
                code = 0 if unit in self.active else 3
                stdout = "active" if code == 0 else "inactive"
            elif operation == "enable":
                if "--now" in args:
                    unit = args[-1]
                    self.active.add(unit)
                self.enabled.add(unit)
                if unit.endswith(".service") and unit != "getty@tty2.service":
                    alias = self.etc_root / "systemd/system/display-manager.service"
                    alias.parent.mkdir(parents=True, exist_ok=True)
                    alias.unlink(missing_ok=True)
                    alias.symlink_to(f"/usr/lib/systemd/system/{unit}")
            elif operation == "disable":
                self.enabled.discard(unit)
                if unit == "greetd.service":
                    alias = self.etc_root / "systemd/system/display-manager.service"
                    if alias.is_symlink() and alias.resolve(strict=False).name == "greetd.service":
                        alias.unlink()
                elif unit.endswith(".service"):
                    alias = self.etc_root / "systemd/system/display-manager.service"
                    if alias.is_symlink() and alias.resolve(strict=False).name == unit:
                        alias.unlink()
            elif operation == "daemon-reload":
                pass
            else:
                raise AssertionError(f"unexpected systemctl operation: {args}")
        else:
            raise AssertionError(f"unexpected command: {args}")
        return subprocess.CompletedProcess(args, code, stdout, "")


class GreetdSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sparrow-greetd-test-")
        self.root = Path(self.temp.name)
        self.etc = self.root / "etc"
        self.state = self.root / "var/lib/sparrow-shell/installer/greetd"
        self.backups = self.root / "var/backups/sparrow/greetd"
        self.run = SimulatedSystemctl(self.etc)

    def tearDown(self):
        self.temp.cleanup()

    def manager(self):
        return GreetdSystemManager(
            REPO, etc_root=self.etc, state_root=self.state,
            backup_root=self.backups, run=self.run, require_root=False,
        )

    def test_fresh_setup_copies_tested_files_enables_tty2_then_greetd_without_start(self):
        result = self.manager().install()
        self.assertEqual(result["status"], "installed")
        self.assertFalse(result["started"])
        self.assertEqual((self.etc / "greetd/config.toml").read_bytes(), (REPO / "greetd/config.toml").read_bytes())
        self.assertEqual((self.etc / "tuigreet/config.toml").read_bytes(), (REPO / "greetd/tuigreet.toml").read_bytes())
        mutations = [event for event in self.run.events if event[1] in {"enable", "disable"}]
        self.assertEqual(mutations[0], ("systemctl", "enable", "--now", "getty@tty2.service"))
        self.assertIn(("systemctl", "enable", "greetd.service"), self.run.events)
        self.assertFalse(any(event[1] in {"start", "restart"} and "greetd.service" in event for event in self.run.events))

    def test_existing_config_requires_consent_and_uninstall_restores_original(self):
        target = self.etc / "greetd/config.toml"
        target.parent.mkdir(parents=True)
        original = b"[custom]\nvalue = true\n"
        target.write_bytes(original)
        with self.assertRaisesRegex(RuntimeError, "explicit replacement consent"):
            self.manager().install()
        self.assertFalse(self.run.events)

        self.manager().install(replace_existing=True)
        state = self.manager()._load()
        backup = Path(state["files"][str(target)]["initial"]["backup"])
        self.assertEqual(backup.read_bytes(), original)
        result = self.manager().uninstall()
        self.assertIn(str(target), result["restored"])
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.etc / "tuigreet/config.toml").exists())

    def test_custom_display_manager_is_never_disabled_without_explicit_consent(self):
        alias = self.etc / "systemd/system/display-manager.service"
        alias.parent.mkdir(parents=True)
        alias.symlink_to("/usr/lib/systemd/system/sddm.service")
        self.run.enabled.add("sddm.service")
        self.assertEqual(self.manager().plan()["display_manager"], "sddm.service")
        with self.assertRaisesRegex(RuntimeError, "explicit replacement consent"):
            self.manager().install()
        self.assertFalse(self.run.events)
        self.manager().install(replace_display_manager=True)
        self.assertIn(("systemctl", "disable", "sddm.service"), self.run.events)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(strict=False).name, "greetd.service")
        self.manager().uninstall()
        self.assertIn("sddm.service", self.run.enabled)
        self.assertEqual(alias.resolve(strict=False).name, "sddm.service")

    def test_user_edited_system_file_is_preserved_on_uninstall(self):
        target = self.etc / "tuigreet/config.toml"
        self.manager().install()
        custom = b"# user changed this after install\n"
        target.write_bytes(custom)
        result = self.manager().uninstall()
        self.assertIn(str(target), result["preserved"])
        self.assertEqual(target.read_bytes(), custom)
        self.assertFalse(result["unit_state_restored"])
        self.assertIn("greetd.service", self.run.enabled)

    def test_rerun_is_idempotent_and_keeps_original_recovery_snapshot(self):
        self.manager().install()
        state_before = self.manager()._load()
        events_before = len(self.run.events)
        self.manager().install()
        state_after = self.manager()._load()
        self.assertEqual(state_before["files"], state_after["files"])
        self.assertEqual(len(self.run.events), events_before + 4)


if __name__ == "__main__":
    unittest.main()
