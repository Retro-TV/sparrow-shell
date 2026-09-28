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
from sparrow_installer import tree_digest


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

    def test_fresh_defaults_copy_live_niri_appearance_and_gtk_icons(self) -> None:
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        appearance = (self.paths.config / "niri/sparrow/appearance.kdl").read_text()
        self.assertRegex(appearance, r"(?m)^\s*top -6$")
        self.assertIn("geometry-corner-radius 12", appearance)
        self.assertIn("clip-to-geometry true", appearance)
        self.assertIn("slowdown 1.5", appearance)
        self.assertFalse((self.paths.config / "niri/sparrow/user-appearance.kdl").exists())
        theme = (REPO / "quickshell/sparrow/Singletons/Theme.qml").read_text()
        self.assertIn(': "Inter Black"', theme)
        self.assertEqual(self.machine["gsettings"].get("icon-theme"), "Sparrow")
        self.assertTrue((self.paths.config / "gtk-3.0/settings.ini").is_file())

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
        niri_config = (self.paths.config / "niri/config.kdl").read_text()
        self.assertIn('include "sparrow/appearance.kdl"', niri_config)
        self.assertIn('include optional=true "sparrow/generated-colors.kdl"', niri_config)
        wallpaper_script = (runtime / "scripts/wallpaper.sh").read_text()
        self.assertIn('default_wallpaper="$helper/../wallpapers/default.png"', wallpaper_script)
        self.assertFalse((self.paths.config / "niri/sparrow/generated-colors.kdl").exists())
        self.assertFalse((self.paths.cache / "sparrow-shell/palette.json").exists())

    def test_installed_portable_files_converge_with_the_live_ssd_source_map(self) -> None:
        source_map = json.loads((REPO / "installer/live-source-map.json").read_text())
        live_home = Path(os.environ.get("SPARROW_LIVE_HOME", str(Path.home())))
        live_config = live_home / ".config/niri/config.kdl"
        if not live_config.is_file():
            self.skipTest("known-good live Niri source is not available; set SPARROW_LIVE_HOME to audit it")

        represented_repo_files = {
            Path(path)
            for path in subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=REPO
            ).decode().split("\0")
            if path
        }

        root_text = live_config.read_text()
        cursor_start = root_text.index("\ncursor {") + 1
        cursor_end = root_text.index("\n}", cursor_start) + 2
        live_cursor = root_text[cursor_start:cursor_end] + "\n"
        root_text = root_text[:cursor_start] + 'include optional=true "sparrow/cursor.kdl"' + root_text[cursor_end:]
        root_text = root_text.replace(
            'include "sparrow/generated-colors.kdl"',
            'include optional=true "sparrow/generated-colors.kdl"',
        )
        machine_comment = (
            "// Keep the existing output setup commented until it is intentionally selected.\n"
            "// -output \"eDP-1\" {\n"
            "//     mode \"1920x1080@120.030\"\n"
            "//     scale 2\n"
            "//     transform \"normal\"\n"
            "//     position x=1280 y=0\n"
            "// }\n"
        )
        root_text = root_text.replace(machine_comment, "")
        root_text = root_text.replace("\n\n\nhotkey-overlay", "\n\nhotkey-overlay")
        self.assertEqual((REPO / "niri/config.kdl").read_text(), root_text)
        self.assertEqual((REPO / "niri/sparrow/cursor.kdl").read_text(), live_cursor)

        mapped_live_files = set()
        for item in source_map["home_relative_sources"]:
            live_rel = item["live"].split("#", 1)[0]
            repo_source = REPO / item["repo"]
            self.assertTrue(repo_source.exists(), f"unrepresented repository source: {item['repo']}")
            repo_rel = Path(item["repo"])
            if repo_source.is_dir():
                for candidate in repo_source.rglob("*"):
                    if candidate.is_file():
                        self.assertIn(
                            candidate.relative_to(REPO), represented_repo_files,
                            f"portable source is not represented in the Git worktree: {candidate}",
                        )
            else:
                self.assertIn(repo_rel, represented_repo_files, f"portable source is not represented in the Git worktree: {repo_source}")
            if item["policy"] == "copy-tree-exact-through-current-development-link":
                live_tree = (live_home / live_rel).resolve()
                self.assertEqual(tree_digest(repo_source), tree_digest(live_tree), item["live"])
            elif item["policy"].startswith("copy-scaffold"):
                live_tree = live_home / live_rel
                self.assertTrue(live_tree.is_dir(), f"missing live theme tree: {item['live']}")
                for source_file in repo_source.rglob("*"):
                    if source_file.is_file():
                        live_file = live_tree / source_file.relative_to(repo_source)
                        self.assertTrue(live_file.is_file(), f"unrepresented theme source: {live_file}")
                        if source_file.name == "index.theme":
                            self.assertEqual(source_file.read_bytes(), live_file.read_bytes(), str(live_file))
            elif "#cursor-block" in item["live"]:
                self.assertEqual(repo_source.read_text(), live_cursor)
            elif item["live"] == ".config/niri/config.kdl":
                self.assertEqual(repo_source.read_text(), root_text)
            elif item["policy"] == "copy-with-generated-look-defaults-promoted":
                live_source = live_home / live_rel
                self.assertTrue(live_source.is_file(), f"missing live source: {item['live']}")
                mapped_live_files.add(live_rel)
                repo_text = repo_source.read_text()
                canonical_defaults = (
                    "    // Balance the pill's top gap against the app gap at the default scale.\n"
                    "    struts {\n        left 12\n        right 12\n        top -6\n        bottom 12\n    }"
                )
                live_struts = (
                    "    // The top edge is balanced against Sparrow's pill reservation in the\n"
                    "    // managed user fragment; keep the other outer struts fixed here.\n"
                    "    struts {\n        left 12\n        right 12\n        bottom 12\n    }"
                )
                self.assertIn(canonical_defaults, repo_text)
                normalized = repo_text.replace(canonical_defaults, live_struts)
                normalized = normalized.replace(
                    "\nwindow-rule {\n    geometry-corner-radius 12\n    clip-to-geometry true\n}\n\n"
                    "// Product motion default; Look-generated preferences override this when saved.\n"
                    "animations {\n    slowdown 1.5\n}\n",
                    "",
                )
                self.assertIn("gaps 6", (live_home / ".config/niri/sparrow/user-appearance.kdl").read_text())
                self.assertIn("top -6", (live_home / ".config/niri/sparrow/user-appearance.kdl").read_text())
                self.assertIn("geometry-corner-radius 12", (live_home / ".config/niri/sparrow/user-appearance.kdl").read_text())
                self.assertIn("slowdown 1.5", (live_home / ".config/niri/sparrow/user-appearance.kdl").read_text())
                self.assertEqual(normalized, live_source.read_text(), item["live"])
            elif item["policy"] == "copy-with-rishot-home-path-sanitized-to-path":
                live_source = live_home / live_rel
                self.assertTrue(live_source.is_file(), f"missing live source: {item['live']}")
                mapped_live_files.add(live_rel)
                normalized = live_source.read_text().replace(
                    'spawn-sh "\\"$HOME/.local/bin/rishot\\""',
                    'spawn "rishot"',
                )
                self.assertNotEqual(normalized, live_source.read_text(), "expected captured absolute Rishot invocation")
                self.assertEqual(repo_source.read_text(), normalized, item["live"])
            elif item["policy"] == "copy-with-unavailable-secret-route-removed-after-conflict-consent":
                live_source = live_home / live_rel
                self.assertTrue(live_source.is_file(), f"missing live source: {item['live']}")
                mapped_live_files.add(live_rel)
                normalized = live_source.read_text().replace(
                    "org.freedesktop.impl.portal.Secret=gnome-keyring;\n", ""
                )
                self.assertIn("FileChooser=gtk;", normalized)
                self.assertIn("ScreenCast=gnome;", normalized)
                self.assertNotIn("org.freedesktop.impl.portal.Secret=", repo_source.read_text())
                self.assertEqual(repo_source.read_text(), normalized, item["live"])
            else:
                live_source = live_home / live_rel
                self.assertTrue(live_source.is_file(), f"missing live source: {item['live']}")
                mapped_live_files.add(live_rel)
                if item["policy"].startswith("copy-exact"):
                    self.assertEqual(repo_source.read_bytes(), live_source.read_bytes(), item["live"])

        live_sparrow_fragments = {
            f".config/niri/sparrow/{path.name}"
            for path in (live_home / ".config/niri/sparrow").glob("*.kdl")
            if ".backup" not in path.name and ".bak" not in path.name
        }
        excluded_fragments = {
            ".config/niri/sparrow/generated-colors.kdl",
            ".config/niri/sparrow/display-outputs.kdl",
            ".config/niri/sparrow/display-binds.kdl",
            ".config/niri/sparrow/user-binds.kdl",
            ".config/niri/sparrow/user-input.kdl",
            ".config/niri/sparrow/user-appearance.kdl",
        }
        mapped_fragments = {path for path in mapped_live_files if path.startswith(".config/niri/sparrow/")}
        self.assertEqual(live_sparrow_fragments - excluded_fragments, mapped_fragments)

        # These active Sparrow-owned file families are source inputs, not
        # generated state. Fail closed if the live SSD gains one that the
        # source map (and therefore repository deployment) does not cover.
        mapped_sources = {
            item["live"].split("#", 1)[0]
            for item in source_map["home_relative_sources"]
        }
        required_live_families = (
            (".config/systemd/user", "sparrow-*.service"),
            (".config/systemd/user/xdg-desktop-portal-gtk.service.d", "*.conf"),
            (".local/share/applications", "sparrow*.desktop"),
        )
        for directory, pattern in required_live_families:
            for live_file in (live_home / directory).glob(pattern):
                self.assertIn(
                    (Path(directory) / live_file.name).as_posix(),
                    mapped_sources,
                    f"live Sparrow-owned file is missing from the source map: {live_file}",
                )

        self.machine["themes"] = {"Bibata-Modern-Ice"}
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        for item in source_map["home_relative_sources"]:
            repo_source = REPO / item["repo"]
            destination = self.root / item["install"]
            if item["policy"] == "copy-tree-exact-through-current-development-link":
                runtime_target = destination.resolve()
                for source_file in repo_source.rglob("*"):
                    if not source_file.is_file():
                        continue
                    relative = source_file.relative_to(repo_source)
                    if relative.as_posix() in {
                        "lib/monitors.test.mjs",
                        "scripts/test_wallcolors.py",
                        "scripts/test_niri_config_transaction.py",
                    }:
                        continue
                    deployed = runtime_target / relative
                    self.assertTrue(deployed.is_file(), f"not deployed: {relative}")
                    self.assertEqual(deployed.read_bytes(), source_file.read_bytes(), str(relative))
            elif item["policy"].startswith("copy-exact") or item["policy"].startswith("copy-with-") or item["policy"].startswith("extract-exact") or item["policy"] == "sanitize-generated-and-machine-comment":
                if item["policy"] == "copy-exact-when-no-agent-exists":
                    self.assertTrue(destination.is_file())
                    self.assertEqual(destination.read_bytes(), repo_source.read_bytes(), item["install"])
                elif item["policy"] == "copy-exact-when-bibata-exists":
                    self.assertTrue(destination.is_file())
                    self.assertEqual(destination.read_bytes(), repo_source.read_bytes(), item["install"])
                else:
                    self.assertEqual(destination.read_bytes(), repo_source.read_bytes(), item["install"])

        for tree_source, installed in (
            (REPO / "gtk/Sparrow", self.paths.data / "themes/Sparrow"),
            (REPO / "icons/Sparrow", self.paths.data / "icons/Sparrow"),
        ):
            for source_file in tree_source.rglob("*"):
                if source_file.is_file():
                    relative = source_file.relative_to(tree_source)
                    self.assertEqual((installed / relative).read_bytes(), source_file.read_bytes(), str(relative))

    def test_icon_preference_converges_only_while_sparrow_still_owns_it(self) -> None:
        self.assertEqual(self.installer().install(), 0)
        self.machine["gsettings"]["icon-theme"] = "Papirus"
        self.assertEqual(self.installer().install(), 0)
        self.assertEqual(self.machine["gsettings"]["icon-theme"], "Papirus")
        manifest = json.loads((self.paths.state / "sparrow-shell/installer/manifest.json").read_text())
        self.assertNotIn("org.gnome.desktop.interface/icon-theme", manifest.get("managed_settings", {}))

    def test_generated_look_override_is_not_seeded_or_overwritten(self) -> None:
        self.assertEqual(self.installer().install(), 0)
        target = self.paths.config / "niri/sparrow/user-appearance.kdl"
        self.assertFalse(target.exists())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// user's mutable Look choices\nlayout { gaps 9 }\n")
        self.assertEqual(self.installer().install(), 0)
        self.assertEqual(target.read_text(), "// user's mutable Look choices\nlayout { gaps 9 }\n")

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

    def test_portal_config_is_copied_from_the_repository_after_conflict_consent(self) -> None:
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        portal.parent.mkdir(parents=True)
        portal.write_text("[preferred]\norg.freedesktop.impl.portal.ScreenCast=custom;\n")
        installer = self.installer()
        self.assertEqual(installer.install(), 0)
        package_events = [event for event in self.machine["events"] if event[:3] == ("sudo", "pacman", "-S")]
        self.assertTrue(any("xdg-desktop-portal-gnome" in event for event in package_events))
        self.assertEqual(portal.read_bytes(), (REPO / "xdg-desktop-portal/niri-portals.conf").read_bytes())

    def test_declining_default_profile_leaves_portal_configuration_unmodified(self) -> None:
        installer = self.installer(
            confirm=lambda prompt, default: False if "recommended desktop apps" in prompt.lower() else default
        )
        self.assertEqual(installer.install(), 0)
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        self.assertFalse(portal.exists())
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

    def test_niri_root_is_installed_as_the_tracked_file_not_synthesized(self) -> None:
        installer = self.installer()
        _, planned, _ = installer._planned_niri(validate=False)
        self.assertEqual(planned[self.paths.config / "niri/config.kdl"], (REPO / "niri/config.kdl").read_bytes())

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
        self.assertEqual(root_config.read_text().count('include "sparrow/appearance.kdl"'), 1)
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

    def test_replaced_niri_and_portal_files_restore_from_backup_on_uninstall(self) -> None:
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
        self.assertEqual(niri.read_bytes(), (REPO / "niri/config.kdl").read_bytes())
        self.assertEqual(portal.read_bytes(), (REPO / "xdg-desktop-portal/niri-portals.conf").read_bytes())

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

    def test_uninstall_preserves_user_edits_to_replaced_niri_and_portal_files(self) -> None:
        niri = self.paths.config / "niri/config.kdl"
        niri.parent.mkdir(parents=True)
        original_niri = 'output "DP-1" {}\n'
        niri.write_text(original_niri)
        portal = self.paths.config / "xdg-desktop-portal/niri-portals.conf"
        portal.parent.mkdir(parents=True)
        portal.write_text("[preferred]\norg.freedesktop.impl.portal.FileChooser=gnome;\n")
        self.assertEqual(self.installer().install(), 0)

        niri.write_text(niri.read_text() + '\ninclude "user-extra.kdl"\n')
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
