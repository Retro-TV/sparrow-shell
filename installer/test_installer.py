from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

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
            "pacman_failure_exit_code": 1,
            "pacman_query_failure": False,
            "pacman_transaction_count": 0,
            "interrupt_at_transaction": None,
            "interrupt_at_prompt": False,
            "invocations": [],
            "events": [],
            "gsettings": {},
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

    def test_fresh_defaults_include_canonical_niri_font_icon_and_welcome_behavior(self) -> None:
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        appearance = (self.paths.config / "niri/sparrow/appearance.kdl").read_text()
        self.assertRegex(appearance, r"(?m)^\s*top -6$")
        rules = (self.paths.config / "niri/sparrow/appearance.kdl").read_text()
        self.assertIn("geometry-corner-radius 12", rules)
        self.assertIn("clip-to-geometry true", rules)
        entry = (self.paths.config / "niri/sparrow/entry.kdl").read_text()
        self.assertIn("slowdown 1.5", entry)
        self.assertLess(entry.index("slowdown 1.5"), entry.index('include "appearance.kdl"'))
        self.assertLess(rules.index("geometry-corner-radius 12"), rules.index('include optional=true "user-appearance.kdl"'))
        theme = (REPO / "quickshell/sparrow/Singletons/Theme.qml").read_text()
        self.assertIn(': "Inter Black"', theme)
        self.assertEqual(self.machine["gsettings"].get("icon-theme"), "Sparrow")
        hello = self.paths.config / "autostart/cachyos-hello.desktop"
        self.assertEqual(hello.read_text(), "[Desktop Entry]\nHidden=true\n")

    def test_blank_home_bootstrap_has_wallpaper_before_shell_without_seeding_generated_state(self) -> None:
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        runtime = self.paths.data / "sparrow-shell/runtime"
        self.assertTrue((runtime / "wallpapers/default.png").is_file())
        wallpaper_unit = (self.paths.config / "systemd/user/sparrow-wallpaper.service").read_text()
        shell_unit = (self.paths.config / "systemd/user/sparrow-shell.service").read_text()
        self.assertIn("Before=graphical-session.target", wallpaper_unit)
        self.assertIn("ExecStartPost=/usr/bin/env SPARROW_AWWW_DAEMON_MANAGED=1", wallpaper_unit)
        self.assertIn("wallpaper.sh init", wallpaper_unit)
        self.assertIn("After=graphical-session.target", shell_unit)
        self.assertIn('include "sparrow/entry.kdl"', (self.paths.config / "niri/config.kdl").read_text())
        wallpaper_script = (runtime / "scripts/wallpaper.sh").read_text()
        self.assertIn('default_wallpaper="$helper/../wallpapers/default.png"', wallpaper_script)
        self.assertFalse((self.paths.config / "niri/sparrow/generated-colors.kdl").exists())
        self.assertFalse((self.paths.cache / "sparrow-shell/palette.json").exists())

    def test_explicit_icon_theme_and_cachyos_hello_choice_are_preserved(self) -> None:
        self.machine["gsettings"]["icon-theme"] = "Adwaita"
        hello = self.paths.config / "autostart/cachyos-hello.desktop"
        hello.parent.mkdir(parents=True)
        hello.write_text("[Desktop Entry]\nType=Application\nName=CachyOS Hello\nExec=/usr/bin/cachyos-hello\nHidden=false\n")
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        self.assertEqual(self.machine["gsettings"]["icon-theme"], "Adwaita")
        self.assertIn("Hidden=false", hello.read_text())

    def test_icon_preference_converges_only_while_sparrow_still_owns_it(self) -> None:
        self.assertEqual(self.installer().install(), 0)
        self.machine["gsettings"]["icon-theme"] = "Papirus"
        self.assertEqual(self.installer().install(), 0)
        self.assertEqual(self.machine["gsettings"]["icon-theme"], "Papirus")
        manifest = json.loads((self.paths.state / "sparrow-shell/installer/manifest.json").read_text())
        self.assertNotIn("org.gnome.desktop.interface/icon-theme", manifest.get("managed_settings", {}))

    def test_welcome_override_restore_preserves_later_unrelated_edits(self) -> None:
        target = self.paths.config / "autostart/cachyos-hello.desktop"
        target.parent.mkdir(parents=True)
        original = "[Desktop Entry]\nType=Application\nName=CachyOS Hello\nExec=/usr/bin/cachyos-hello\nComment=hello\n"
        target.write_text(original)
        self.assertEqual(self.installer().install(), 0)
        self.assertIn("Hidden=true", target.read_text())
        target.write_text(target.read_text().replace("Comment=hello", "Comment=my note"))
        self.assertEqual(self.installer().install(), 0)
        self.assertIn("Comment=my note", target.read_text())
        self.assertIn("Hidden=true", target.read_text())
        self.assertEqual(self.installer().uninstall(), 0)
        self.assertNotIn("Hidden=", target.read_text())
        self.assertIn("Comment=my note", target.read_text())

    def test_welcome_override_does_not_recreate_user_deleted_entry_on_update(self) -> None:
        target = self.paths.config / "autostart/cachyos-hello.desktop"
        self.assertEqual(self.installer().install(), 0)
        target.unlink()
        self.assertEqual(self.installer().install(), 0)
        self.assertFalse(target.exists())

    def test_managed_niri_fragment_updates_on_convergence(self) -> None:
        self.assertEqual(self.installer().install(), 0)
        target = self.paths.config / "niri/sparrow/appearance.kdl"
        manifest_path = self.paths.state / "sparrow-shell/installer/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        record = manifest["managed"][str(target)]
        old = target.read_text()
        record["sha256"] = hashlib.sha256(old.encode()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        target.write_text(old.replace("top -6", "top 0"))
        # Model an installer-owned file from the previous release: its recorded
        # hash, not the current contents, identifies it as safe to converge.
        manifest["managed"][str(target)]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        self.assertEqual(self.installer().install(), 0)
        self.assertIn("top -6", target.read_text())

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
        self.machine["pacman_failure_exit_code"] = 42
        installer = self.installer()
        self.assertEqual(installer.install(), 42)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(any(event[0] == "niri" for event in self.machine["events"]))
        self.assertTrue(any("failed with exit status" in message for message in self.messages))

    def test_default_package_failure_stops_without_continuing_to_optional_prompt_or_deploying(self) -> None:
        self.machine["pacman_failure_at_transaction"] = 2
        installer = self.installer()
        self.assertEqual(installer.install(), 1)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(any("Choose optional feature packages" in message for message in self.messages))
        self.assertTrue(any("failed with exit status" in message for message in self.messages))

    def test_package_command_inherits_terminal_io_instead_of_capturing_progress(self) -> None:
        installer = self.installer()
        self.machine["commands"].update({"sudo", "pacman"})
        self.machine["packages"].update(installer.package_sets()["required"])
        installer._installed_package_cache = None
        self.assertTrue(installer._install_package_list(["kitty"], label="stdio test"))
        args, kwargs = next(
            (args, kwargs)
            for args, kwargs in reversed(self.machine["invocations"])
            if args[:3] == ("sudo", "pacman", "-S")
        )
        self.assertEqual(args[:4], ("sudo", "pacman", "-S", "--needed"))
        self.assertNotIn("stdout", kwargs)
        self.assertNotIn("stderr", kwargs)
        self.assertNotIn("text", kwargs)
        self.assertTrue(any("Starting pacman transaction" in message for message in self.messages))
        self.assertTrue(any("completed successfully" in message for message in self.messages))

    def test_production_command_runner_receives_inherited_stdio_options(self) -> None:
        calls = []

        def inert_runner(args, **kwargs):
            calls.append((tuple(args), dict(kwargs)))
            return subprocess.CompletedProcess(args, 0)

        installer = SparrowInstaller(self.paths, REPO, testing=False, run=inert_runner, output=self.messages.append)
        installer._command(["sudo", "pacman", "-S", "--needed", "kitty"], inherit_stdio=True)
        args, kwargs = calls[0]
        self.assertEqual(args[:3], ("sudo", "pacman", "-S"))
        self.assertNotIn("stdout", kwargs)
        self.assertNotIn("stderr", kwargs)
        self.assertNotIn("stdin", kwargs)
        self.assertNotIn("text", kwargs)

    def test_interrupted_default_transaction_is_resumable_without_deployment(self) -> None:
        self.machine["interrupt_at_transaction"] = 2
        first = self.installer()
        self.assertEqual(first.install(), 130)
        self.assertTrue(set(first.package_sets()["required"]).issubset(self.machine["packages"]))
        self.assertFalse(self.paths.config.exists())
        self.assertTrue(any("Pacman transaction for Default desktop profile was interrupted" in message for message in self.messages))
        self.assertFalse(any("Choose optional feature packages" in message for message in self.messages))

        self.machine["interrupt_at_transaction"] = None
        resumed = self.installer()
        self.assertEqual(resumed.install(), 0)
        self.assertTrue((self.paths.config / "niri/config.kdl").is_file())
        transactions = [event for event in self.machine["events"] if event[:3] == ("sudo", "pacman", "-S")]
        self.assertEqual(len(transactions), 3)
        self.assertTrue(any("Required Sparrow runtime: already installed" in message for message in self.messages))
        self.assertTrue((self.paths.config / "systemd/user/sparrow-shell.service").is_file())

    def test_prompt_interrupt_is_clean_and_does_not_traceback_or_deploy(self) -> None:
        def interrupt_prompt(_prompt, _default):
            raise KeyboardInterrupt
        installer = self.installer(confirm=interrupt_prompt)
        self.assertEqual(installer.install(), 130)
        self.assertTrue(any(message == "Installation cancelled by user. No further Sparrow changes were made." for message in self.messages))
        self.assertFalse(any("Traceback" in message for message in self.messages))
        self.assertFalse(self.paths.config.exists())

    def test_pacman_unavailable_is_reported_before_queries_or_deployment(self) -> None:
        self.machine["commands"].discard("pacman")
        installer = self.installer()
        self.assertEqual(installer.install(), 2)
        self.assertTrue(any("pacman is unavailable" in message for message in self.messages))
        self.assertFalse(self.paths.config.exists())

    def test_pacman_query_failure_does_not_assume_everything_is_missing(self) -> None:
        self.machine["pacman_query_failure"] = True
        installer = self.installer()
        self.assertEqual(installer.install(), 1)
        self.assertFalse(any(event[:3] == ("sudo", "pacman", "-S") for event in self.machine["events"]))
        self.assertFalse(self.paths.config.exists())

    def test_sudo_unavailable_stops_after_consent_without_deployment(self) -> None:
        self.machine["commands"].discard("sudo")
        installer = self.installer()
        self.assertEqual(installer.install(), 1)
        self.assertTrue(any("sudo is unavailable" in message for message in self.messages))
        self.assertFalse(self.paths.config.exists())

    def test_malformed_package_set_is_rejected_before_transactions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sparrow-invalid-manifest-") as temp:
            repository = Path(temp)
            package_dir = repository / "installer"
            package_dir.mkdir()
            (package_dir / "package-sets.json").write_text('{"required": "sudo pacman"}', encoding="utf-8")
            installer = SparrowInstaller(self.paths, repository, testing=True, test_machine=self.machine, output=self.messages.append)
            with self.assertRaisesRegex(ValueError, "required.*list"):
                installer.package_sets()
        self.assertEqual(self.machine["events"], [])

    def test_uninstall_after_interrupted_package_stage_is_safe_noop(self) -> None:
        self.machine["interrupt_at_transaction"] = 2
        self.assertEqual(self.installer().install(), 130)
        self.assertEqual(self.installer().uninstall(), 0)
        self.assertFalse(self.paths.config.exists())
        self.assertFalse(self.paths.state.exists())

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

    def test_full_noninteractive_install_stops_before_package_transaction(self) -> None:
        installer = SparrowInstaller(self.paths, REPO, testing=True, test_machine=self.machine, output=self.messages.append)
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertEqual(installer.install(), 2)
        self.assertFalse(any(event[:3] == ("sudo", "pacman", "-S") for event in self.machine["events"]))
        self.assertFalse(self.paths.config.exists())

    def test_preinstalled_package_group_is_skipped_without_transaction(self) -> None:
        installer = self.installer()
        self.machine["packages"].add("kitty")
        self.machine["commands"].add("kitty")
        self.assertTrue(installer._install_package_list(["kitty"], label="already present"))
        self.assertEqual(self.machine["pacman_transaction_count"], 0)
        self.assertTrue(any("already installed" in message for message in self.messages))

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
