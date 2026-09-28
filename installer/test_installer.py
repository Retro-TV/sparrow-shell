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
        self.machine = {
            "os": "id=cachyos",
            "packages": set(),
            "commands": {"sudo", "pacman", "bash", "systemd-analyze", "systemctl", "env", "gio", "udevadm"},
            "modules": set(),
            "missing_after_install": set(),
            "existing_polkit_agent": False,
            "pacman_failure": False,
            "events": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def installer(self, *, confirm=None) -> SparrowInstaller:
        return SparrowInstaller(
            self.paths,
            REPO,
            testing=True,
            confirm=confirm or self.confirm_full_profile,
            test_machine=self.machine,
            output=self.messages.append,
        )

    @staticmethod
    def confirm_full_profile(prompt: str, _default: bool) -> bool:
        return "optional feature" not in prompt.lower() and "include optional group" not in prompt.lower()

    def test_portal_merge_preserves_routes_and_is_idempotent(self) -> None:
        original = """[preferred]\ndefault=gnome;gtk;\norg.freedesktop.impl.portal.ScreenCast=gnome;\norg.freedesktop.impl.portal.FileChooser=org.gtk.FileChooser;\n"""
        installer = self.installer()
        updated = installer.merge_portal(original, include_screencast=True)
        self.assertIn("ScreenCast=gnome;", updated)
        self.assertIn("FileChooser=gtk;", updated)
        self.assertEqual(installer.merge_portal(updated, include_screencast=True), updated)

    def test_portal_merge_adds_niri_screencast_route_without_overwriting_other_routes(self) -> None:
        existing = "[preferred]\norg.freedesktop.impl.portal.ScreenCast=custom;\norg.freedesktop.impl.portal.RemoteDesktop=other;\n"
        installer = self.installer()
        updated = installer.merge_portal(existing, include_screencast=True)
        self.assertIn("ScreenCast=custom;", updated)
        self.assertIn("RemoteDesktop=other;", updated)
        self.assertIn("FileChooser=gtk;", updated)
        restored = installer._restore_portal_key(updated, existing)
        self.assertEqual(restored, existing)

    def test_clean_cachyos_installs_packages_before_niri_and_systemd_validation(self) -> None:
        # The five missing binaries from the bare-metal report start absent.
        for executable in ("niri", "qs", "awww", "awww-daemon", "matugen", "lxqt-policykit-agent"):
            self.assertNotIn(executable, self.machine["commands"])
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        events = self.machine["events"]
        package_event = next(i for i, event in enumerate(events) if event[:3] == ("sudo", "pacman", "-S"))
        niri_validate = next(i for i, event in enumerate(events) if event[:2] == ("niri", "validate"))
        units_validate = next(i for i, event in enumerate(events) if event[:3] == ("systemd-analyze", "--user", "verify"))
        self.assertLess(package_event, niri_validate)
        self.assertLess(package_event, units_validate)
        self.assertTrue({"qs", "awww", "awww-daemon", "matugen", "lxqt-policykit-agent"}.issubset(self.machine["commands"]))
        self.assertTrue((self.paths.config / "systemd/user/sparrow-polkit-agent.service").is_file())

    def test_systemd_validation_fails_if_a_required_binary_remains_missing_after_pacman(self) -> None:
        self.machine["missing_after_install"].add("qs")
        installer = self.installer()
        self.assertEqual(installer.install(), 2)
        self.assertTrue(any("still missing after package resolution" in message for message in self.messages))
        self.assertFalse((self.paths.config / "systemd/user/sparrow-shell.service").exists())
        self.assertFalse(any(event[:3] == ("systemd-analyze", "--user", "verify") for event in self.machine["events"]))

    def test_required_package_decline_leaves_xdg_fixture_empty(self) -> None:
        installer = self.installer(confirm=lambda _prompt, _default: False)
        self.assertEqual(installer.install(), 2)
        self.assertFalse(any(event[:3] == ("sudo", "pacman", "-S") for event in self.machine["events"]))
        self.assertFalse(self.paths.config.exists())

    def test_pacman_failure_stops_before_configuration_deployment(self) -> None:
        self.machine["pacman_failure"] = True
        installer = self.installer()
        self.assertEqual(installer.install(), 2)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(any(event[0] == "niri" for event in self.machine["events"]))

    def test_existing_polkit_agent_is_preserved_and_sparrow_agent_is_not_staged(self) -> None:
        self.machine["existing_polkit_agent"] = True
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        self.assertFalse((self.paths.config / "systemd/user/sparrow-polkit-agent.service").exists())
        package_install = next(event for event in self.machine["events"] if event[:3] == ("sudo", "pacman", "-S"))
        self.assertNotIn("lxqt-policykit", package_install)

    def test_existing_custom_screencast_route_is_kept_without_installing_gnome_backend(self) -> None:
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        portal.parent.mkdir(parents=True)
        portal.write_text("[preferred]\norg.freedesktop.impl.portal.ScreenCast=custom;\n")
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        package_install = next(event for event in self.machine["events"] if event[:3] == ("sudo", "pacman", "-S"))
        self.assertNotIn("xdg-desktop-portal-gnome", package_install)
        result = portal.read_text()
        self.assertIn("ScreenCast=custom;", result)
        self.assertIn("FileChooser=gtk;", result)

    def test_declining_default_portal_bundle_does_not_create_route_to_missing_backend(self) -> None:
        installer = self.installer(
            confirm=lambda prompt, default: False if "recommended desktop apps" in prompt.lower() else default
        )
        self.assertEqual(installer.install(), 0)
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        result = portal.read_text()
        self.assertIn("FileChooser=gtk;", result)
        self.assertNotIn("ScreenCast=gnome;", result)
        self.assertNotIn("xdg-desktop-portal-gnome", self.machine["packages"])

    def test_absent_optional_tools_do_not_block_clean_install(self) -> None:
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        self.assertNotIn("cava", self.machine["commands"])
        self.assertNotIn("wlsunset", self.machine["commands"])
        self.assertNotIn("mpvpaper", self.machine["commands"])
        self.assertTrue(any("Rishot" in message and "Super+Shift+S" in message for message in self.messages))

    def test_cursor_default_is_not_written_without_bibata_asset(self) -> None:
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        cursor = self.paths.config / "niri/sparrow/cursor.kdl"
        self.assertIn(b"not installed", cursor.read_bytes())
        self.assertFalse((self.paths.config / "environment.d/90-cursor.conf").exists())

    def test_bibata_defaults_are_installed_only_when_asset_is_present(self) -> None:
        self.machine["themes"] = {"Bibata-Modern-Ice"}
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        cursor = self.paths.config / "niri/sparrow/cursor.kdl"
        self.assertIn(b'xcursor-theme "Bibata-Modern-Ice"', cursor.read_bytes())
        self.assertTrue((self.paths.config / "environment.d/90-cursor.conf").is_file())

    def test_testing_cannot_inject_a_live_command_runner(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbids external command runners"):
            SparrowInstaller(self.paths, REPO, testing=True, run=subprocess.run)

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
        self.assertTrue(any("validation is deferred until after" in line for line in self.messages))

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
        installer = self.installer(confirm=lambda prompt, _default: prompt.startswith("Install these official repository packages"))
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
        self.assertTrue((self.paths.config / "systemd/user/sparrow-polkit-agent.service").is_file())
        self.assertTrue((self.paths.config / "xdg-desktop-portal/niri-portals.conf").is_file())
        self.assertIn("ScreenCast=gnome;", (self.paths.config / "xdg-desktop-portal/niri-portals.conf").read_text())
        self.assertIn("xdg-desktop-portal-gnome", self.machine["packages"])
        self.assertIn("wl-clipboard", self.machine["packages"])
        self.assertIn("curl", self.machine["packages"])
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
        self.assertIn("bibata-cursor-theme-bin", sets["aur_manual"].values())


if __name__ == "__main__":
    unittest.main()
