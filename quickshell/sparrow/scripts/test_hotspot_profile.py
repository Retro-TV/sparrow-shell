from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("hotspot-profile.py")
spec = importlib.util.spec_from_file_location("hotspot_profile", SCRIPT)
hotspot = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = hotspot
spec.loader.exec_module(hotspot)


class HotspotProfileTests(unittest.TestCase):
    def test_password_validation_matches_networkmanager_wpa_psk(self) -> None:
        for password in ("12345678", "correct horse battery", "A" * 63, "ab" * 32):
            self.assertTrue(hotspot.valid_password(password), password)
        for password in ("short", "A" * 65, "z" * 64, "password\n123", "é" * 8):
            self.assertFalse(hotspot.valid_password(password), password)

    def test_no_password_generation_mode(self) -> None:
        with mock.patch.object(hotspot, "persist_profile") as persist:
            self.assertEqual(hotspot.main(["generate"]), 2)
        persist.assert_not_called()

    def test_password_is_consumed_from_stdin_and_not_forwarded_to_nmcli(self) -> None:
        secret = "correct-horse-battery-staple"
        with mock.patch.object(hotspot, "persist_profile") as persist, \
                mock.patch.object(hotspot.subprocess, "run") as run, \
                mock.patch.object(sys, "stdin") as stdin:
            stdin.readline.return_value = __import__("json").dumps({
                "name": "Sparrow Test", "password": secret, "interface": "wlan0",
            }) + "\n"
            self.assertEqual(hotspot.main(["apply"]), 0)
        self.assertEqual(persist.call_args.args[0]["password"], secret)
        self.assertEqual(run.call_args.args[0], ["nmcli", "connection", "up", "SparrowHotspot"])
        self.assertNotIn(secret, repr(run.call_args))

    def test_profile_builder_places_secret_in_libnm_settings(self) -> None:
        try:
            connection = hotspot.build_profile({
                "name": "Sparrow Test", "password": "correct-horse-battery", "interface": "wlan0",
            })
        except (ImportError, ValueError) as exc:
            self.skipTest(f"libnm introspection is unavailable: {exc}")
        wireless = connection.get_setting_wireless()
        security = connection.get_setting_wireless_security()
        self.assertEqual(wireless.get_ssid().get_data().decode(), "Sparrow Test")
        self.assertEqual(security.get_psk(), "correct-horse-battery")
        self.assertEqual(connection.get_setting_connection().get_interface_name(), "wlan0")

    def test_existing_profile_keeps_identity_and_original_untouched(self) -> None:
        try:
            original = hotspot.build_profile({
                "name": "Existing hotspot", "password": "existing-password", "interface": "wlan0",
            })
            uuid = original.get_setting_connection().get_uuid()
            updated = hotspot.build_profile({
                "name": "Renamed hotspot", "password": "new-password-123", "interface": "wlan0",
            }, original)
        except (ImportError, ValueError) as exc:
            self.skipTest(f"libnm introspection is unavailable: {exc}")
        self.assertEqual(updated.get_setting_connection().get_uuid(), uuid)
        self.assertEqual(original.get_setting_wireless_security().get_psk(), "existing-password")
        self.assertEqual(updated.get_setting_wireless_security().get_psk(), "new-password-123")

    def test_invalid_credential_is_rejected_before_networkmanager(self) -> None:
        with mock.patch.object(hotspot, "persist_profile") as persist, \
                mock.patch.object(sys, "stdin") as stdin:
            stdin.readline.return_value = '{"name":"Sparrow","password":"short","interface":"wlan0"}\n'
            self.assertEqual(hotspot.main(["save"]), 1)
        persist.assert_not_called()

    def test_qml_hotspot_flow_never_generates_or_passes_secret_in_argv(self) -> None:
        qml = (SCRIPT.parent.parent / "WifiSurface.qml").read_text()
        self.assertNotIn("hsGenerateProc", qml)
        self.assertNotIn("ensureHotspotPassword", qml)
        self.assertIn("onStarted: write(root.profilePayload())", qml)
        self.assertIn('hsApplyProc.command = ["python3", hotspotHelper, "apply"]', qml)
        self.assertIn('command: ["nmcli", "connection", "up", root.hsCon]', qml)
        self.assertIn("else if (hsProfileExists)", qml)


if __name__ == "__main__":
    unittest.main()
