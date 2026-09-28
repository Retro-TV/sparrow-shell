from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from sparrow_installer import SparrowInstaller, XdgPaths


REPO = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sparrow-installer-test-")
        self.root = Path(self.temp.name)
        self.paths = XdgPaths(
            self.root,
            self.root / ".config",
            self.root / ".local/share",
            self.root / ".local/state",
            self.root / ".cache",
        )
        self.messages: list[str] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def installer(self, *, confirm=None) -> SparrowInstaller:
        return SparrowInstaller(
            self.paths,
            REPO,
            testing=True,
            confirm=confirm or (lambda _prompt, default: True),
            output=self.messages.append,
        )

    def test_portal_merge_preserves_routes_and_is_idempotent(self) -> None:
        original = """[preferred]\ndefault=gnome;gtk;\norg.freedesktop.impl.portal.ScreenCast=gnome;\norg.freedesktop.impl.portal.FileChooser=org.gtk.FileChooser;\n"""
        installer = self.installer()
        updated = installer.merge_portal(original)
        self.assertIn("ScreenCast=gnome;", updated)
        self.assertIn("FileChooser=gtk;", updated)
        self.assertEqual(installer.merge_portal(updated), updated)

    def test_niri_merge_has_one_marker_and_preserves_user_output(self) -> None:
        original = 'output "DP-1" {\n    mode "1920x1080@60"\n}\n'
        installer = self.installer()
        merged = installer.merge_niri_root(original)
        self.assertIn('output "DP-1"', merged)
        self.assertIn('include "sparrow/entry.kdl"', merged)
        self.assertEqual(installer.merge_niri_root(merged), merged)
        self.assertEqual(SparrowInstaller._remove_niri_marker(merged), original)

    def test_fresh_niri_validation_can_wait_until_required_package_install(self) -> None:
        installer = self.installer()
        root, planned, _ = installer._planned_niri(validate=False)
        self.assertEqual(root, self.paths.config / "niri/config.kdl")
        self.assertTrue(planned[root])
        self.assertTrue(any("validation will run after" in line for line in self.messages))

    def test_noninteractive_consent_never_accepts_package_prompt_default(self) -> None:
        installer = self.installer()
        self.assertFalse(installer._confirm("Install required packages?", True))
        self.assertTrue(any("without an interactive terminal" in line for line in self.messages))

    def test_installed_units_follow_custom_xdg_config_home(self) -> None:
        paths = XdgPaths(
            self.root,
            self.root / "config-alt",
            self.root / ".local/share",
            self.root / ".local/state",
            self.root / ".cache",
        )
        installer = SparrowInstaller(paths, REPO, testing=True, output=self.messages.append)
        unit = installer._unit_payload(REPO / "quickshell/sparrow/systemd/sparrow-shell.service")
        self.assertIn(b"%h/config-alt/quickshell/sparrow", unit)
        self.assertNotIn(b"%h/.config/quickshell/sparrow", unit)

    def test_existing_direct_fragment_includes_gain_missing_sparrow_fragments_only(self) -> None:
        original = 'include "sparrow/appearance.kdl"\ninclude "sparrow/binds.kdl"\n'
        installer = self.installer()
        merged = installer.merge_niri_root(original)
        block = merged.split("// >>> BEGIN SPARROW INSTALLER INCLUDES\n", 1)[1]
        self.assertNotIn('include "sparrow/entry.kdl"', block)
        self.assertNotIn('include "sparrow/session-defaults.kdl"', block)
        self.assertNotIn('include "sparrow/cursor.kdl"', block)
        self.assertNotIn('include "sparrow/appearance.kdl"', block)

    def test_conflict_is_preserved_when_user_declines(self) -> None:
        target = self.paths.config / "kitty/kitty.conf"
        target.parent.mkdir(parents=True)
        target.write_text("user kitty config\n")
        installer = self.installer(confirm=lambda _prompt, _default: False)
        installed = installer.write_file(target, b"Sparrow defaults\n", role="Kitty defaults")
        self.assertFalse(installed)
        self.assertEqual(target.read_text(), "user kitty config\n")

    def test_unrelated_runtime_collision_stops_before_canonical_link(self) -> None:
        runtime = self.paths.data / "sparrow-shell/runtime"
        runtime.mkdir(parents=True)
        marker = runtime / "keep.txt"
        marker.write_text("not Sparrow\n")
        installer = self.installer(confirm=lambda _prompt, _default: False)
        self.assertEqual(installer.install(), 1)
        self.assertEqual(marker.read_text(), "not Sparrow\n")
        self.assertFalse((self.paths.config / "quickshell/sparrow").exists())
        self.assertFalse((self.paths.config / "niri/config.kdl").exists())

    def test_fresh_install_is_idempotent_and_restorable(self) -> None:
        first = self.installer()
        self.assertEqual(first.install(), 0)
        runtime = self.paths.data / "sparrow-shell/runtime"
        entry = self.paths.config / "quickshell/sparrow"
        self.assertTrue((runtime / "shell.qml").is_file())
        self.assertTrue(entry.is_symlink())
        self.assertEqual(entry.resolve(), runtime)
        root_config = self.paths.config / "niri/config.kdl"
        self.assertTrue(root_config.is_file())
        self.assertTrue((self.paths.config / "systemd/user/sparrow-shell.service").is_file())
        self.assertTrue((self.paths.config / "xdg-desktop-portal/niri-portals.conf").is_file())
        manifest_before = json.loads(first.manifest_path.read_text())
        self.assertTrue(manifest_before["managed"])

        second = self.installer()
        self.assertEqual(second.install(), 0)
        self.assertEqual(entry.resolve(), runtime)
        self.assertEqual(root_config.read_text().count('include "sparrow/entry.kdl"'), 1)
        self.assertEqual((self.paths.config / "xdg-desktop-portal/niri-portals.conf").read_text().count("FileChooser=gtk;"), 1)

        uninstaller = self.installer()
        self.assertEqual(uninstaller.uninstall(), 0)
        self.assertFalse(entry.exists())
        self.assertFalse(root_config.exists())
        self.assertFalse(runtime.exists())
        self.assertFalse((self.paths.config / "xdg-desktop-portal/niri-portals.conf").exists())
        self.assertTrue((self.paths.state / "sparrow-shell/installer/backups").is_dir())

    def test_dry_run_validates_and_leaves_xdg_fixture_unchanged(self) -> None:
        installer = SparrowInstaller(
            self.paths, REPO, dry_run=True, testing=True,
            confirm=lambda _prompt, default: default, output=self.messages.append,
        )
        self.assertEqual(installer.install(), 0)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(self.paths.data.exists())
        self.assertFalse(self.paths.state.exists())

    def test_existing_niri_and_portal_routes_survive_uninstall(self) -> None:
        niri = self.paths.config / "niri/config.kdl"
        niri.parent.mkdir(parents=True)
        original_niri = 'output "DP-1" {\n    mode "1920x1080@60"\n}\n'
        niri.write_text(original_niri)
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        portal.parent.mkdir(parents=True)
        original_portal = "[preferred]\norg.freedesktop.impl.portal.ScreenCast=gnome;\n"
        portal.write_text(original_portal)

        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        self.assertIn('output "DP-1"', niri.read_text())
        self.assertIn("ScreenCast=gnome;", portal.read_text())
        self.assertIn("FileChooser=gtk;", portal.read_text())

        self.assertEqual(self.installer().uninstall(), 0)
        self.assertEqual(niri.read_text(), original_niri)
        self.assertEqual(portal.read_text(), original_portal)

    def test_uninstall_keeps_user_edits_to_managed_file(self) -> None:
        target = self.paths.config / "starship.toml"
        installer = self.installer()
        self.assertTrue(installer.write_file(target, b"Sparrow\n", role="Starship"))
        installer._save_manifest()
        target.write_text("my later customization\n")
        self.assertEqual(self.installer().uninstall(), 0)
        self.assertEqual(target.read_text(), "my later customization\n")

    def test_uninstall_preserves_edits_inside_niri_merge_and_portal_route(self) -> None:
        niri = self.paths.config / "niri/config.kdl"
        niri.parent.mkdir(parents=True)
        original_niri = 'output "DP-1" {}\n'
        niri.write_text(original_niri)
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        portal.parent.mkdir(parents=True)
        portal.write_text("[preferred]\norg.freedesktop.impl.portal.FileChooser=gnome;\n")
        self.assertEqual(self.installer().install(), 0)

        niri.write_text(niri.read_text().replace('include "sparrow/entry.kdl"', 'include "sparrow/entry.kdl"\ninclude "user-extra.kdl"'))
        portal.write_text(portal.read_text().replace("FileChooser=gtk;", "FileChooser=custom;"))
        self.assertEqual(self.installer().uninstall(), 0)
        self.assertIn('include "user-extra.kdl"', niri.read_text())
        self.assertIn("FileChooser=custom;", portal.read_text())

    def test_uninstall_defers_runtime_removal_while_shell_is_active(self) -> None:
        self.assertEqual(self.installer().install(), 0)
        runtime = self.paths.data / "sparrow-shell/runtime"
        entry = self.paths.config / "quickshell/sparrow"

        def systemctl_stub(args, **_kwargs):
            active = args[:3] == ["systemctl", "--user", "is-active"]
            is_shell = active and args[-1] == "sparrow-shell.service"
            return subprocess.CompletedProcess(args, 0 if is_shell else 3, "active" if is_shell else "inactive", "")

        active_uninstaller = SparrowInstaller(
            self.paths, REPO, testing=False, run=systemctl_stub,
            confirm=lambda _prompt, default: default, output=self.messages.append,
        )
        self.assertEqual(active_uninstaller.uninstall(), 0)
        self.assertTrue(runtime.is_dir())
        self.assertTrue(entry.is_symlink())
        self.assertTrue(active_uninstaller.manifest_path.is_file())

        def inactive_stub(args, **_kwargs):
            return subprocess.CompletedProcess(args, 3 if args[:3] == ["systemctl", "--user", "is-active"] else 0, "inactive", "")

        after_logout = SparrowInstaller(
            self.paths, REPO, testing=False, run=inactive_stub,
            confirm=lambda _prompt, default: default, output=self.messages.append,
        )
        self.assertEqual(after_logout.uninstall(), 0)
        self.assertFalse(runtime.exists())
        self.assertFalse(entry.exists())
        self.assertFalse(after_logout.manifest_path.exists())

    def test_rollback_restores_original_symlink(self) -> None:
        path = self.paths.config / "quickshell/sparrow"
        path.parent.mkdir(parents=True)
        path.symlink_to("../../old/sparrow")
        installer = self.installer()
        installer._snapshot_once(path)
        path.unlink()
        path.mkdir()
        installer._rollback()
        self.assertTrue(path.is_symlink())
        self.assertEqual(os.readlink(path), "../../old/sparrow")

    def test_failed_deployment_rolls_back_partial_files(self) -> None:
        installer = self.installer()
        apply_plan = installer._apply_plan

        def fail_after_plan(plan):
            apply_plan(plan)
            raise RuntimeError("simulated deployment failure")

        installer._apply_plan = fail_after_plan
        self.assertEqual(installer.install(), 1)
        self.assertFalse((self.paths.config / "niri/config.kdl").exists())
        self.assertFalse((self.paths.config / "quickshell/sparrow").exists())
        self.assertFalse((self.paths.data / "sparrow-shell/runtime").exists())
        self.assertFalse(installer.manifest_path.exists())

    def test_package_sets_keep_aur_out_of_automatic_lists(self) -> None:
        sets = self.installer().package_sets()
        automatic = set(sets["required"] + sets["defaults"])
        for group in sets["optional"].values():
            automatic.update(group)
        self.assertNotIn("bibata-cursor-theme", automatic)
        self.assertNotIn("mpvpaper", automatic)
        self.assertIn("bibata-cursor-theme", sets["aur_manual"].values())


if __name__ == "__main__":
    unittest.main()
