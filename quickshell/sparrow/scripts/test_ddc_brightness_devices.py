from pathlib import Path
import subprocess
import tempfile
import unittest

from ddc_brightness_devices import detect_monitors, label_monitors, monitor_identity


class DdcBrightnessDeviceTests(unittest.TestCase):
    def test_excludes_sysfs_backlight_and_ddc_displays_without_readable_vcp10(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sparrow-ddc-test-") as temporary:
            root = Path(temporary)
            backlight = root / "sys/class/backlight/intel_backlight"
            target = root / "sys/devices/pci/drm/card1/card1-eDP-1/intel_backlight"
            target.mkdir(parents=True)
            backlight.parent.mkdir(parents=True)
            backlight.symlink_to(target)

            detected = """Display 1
  I2C bus: /dev/i2c-1
  DRM connector: card1-eDP-1
  EDID synopsis:
    Model: Built-in panel
Display 2
  I2C bus: /dev/i2c-2
  DRM connector: card1-DP-1
  EDID synopsis:
    Model: LG ULTRAGEAR
Display 3
  I2C bus: /dev/i2c-3
  DRM connector: card1-DP-2
  EDID synopsis:
    Model: Unsupported
"""
            queried: list[str] = []

            def run(args, **_kwargs):
                if args[1] == "detect":
                    return subprocess.CompletedProcess(args, 0, detected, "")
                bus = args[-1]
                queried.append(bus)
                if bus == "2":
                    return subprocess.CompletedProcess(args, 0, "VCP code 10 C 47 M 100\n", "")
                return subprocess.CompletedProcess(args, 1, "", "unsupported VCP feature")

            result = detect_monitors(backlight_root=backlight.parent, run=run)

        self.assertEqual(result, [{"bus": "2", "label": "LG ULTRAGEAR", "brightness": 47}])
        self.assertEqual(queried, ["2", "3"])

    def test_monitor_identity_extracts_model_and_strips_kernel_card_prefix(self) -> None:
        model, connector = monitor_identity("""EDID synopsis:
  Mfg id: GSM - LG Electronics
  Model:  LG UltraGear 27GP850
""" + "  DRM connector: card2-HDMI-A-1\n")
        self.assertEqual(model, "LG UltraGear 27GP850")
        self.assertEqual(connector, "HDMI-A-1")

    def test_monitor_labels_fall_back_model_then_connector_then_display_number(self) -> None:
        monitors = [
            {"bus": "8", "model": "", "connector": "", "brightness": 40},
            {"bus": "5", "model": "", "connector": "DP-1", "brightness": 50},
            {"bus": "3", "model": "LG UltraGear", "connector": "DP-2", "brightness": 60},
        ]
        labels = label_monitors(monitors)
        self.assertEqual([monitor["label"] for monitor in labels], [
            "Display 1", "DP-1", "LG UltraGear",
        ])

    def test_identical_monitor_models_get_stable_disambiguators(self) -> None:
        monitors = [
            {"bus": "8", "model": "LG UltraGear", "connector": "DP-2", "brightness": 40},
            {"bus": "5", "model": "LG UltraGear", "connector": "DP-1", "brightness": 50},
        ]
        labels = label_monitors(monitors)
        self.assertEqual([monitor["label"] for monitor in labels], [
            "LG UltraGear · 1", "LG UltraGear · 2",
        ])
        self.assertEqual([monitor["bus"] for monitor in labels], ["5", "8"])

    def test_multiple_readable_ddc_displays_remain_separate_controllable_devices(self) -> None:
        detected = """Display 1
  I2C bus: /dev/i2c-8
  DRM connector: card0-HDMI-A-1
  EDID synopsis:
    Model: LG UltraGear
Display 2
  I2C bus: /dev/i2c-5
  DRM connector: card0-DP-1
  EDID synopsis:
    Model: Samsung Odyssey
"""
        queried: list[str] = []

        def run(args, **_kwargs):
            if args[1] == "detect":
                return subprocess.CompletedProcess(args, 0, detected, "")
            bus = args[-1]
            queried.append(bus)
            return subprocess.CompletedProcess(args, 0, "VCP code 10 C 55 M 100\n", "")

        result = detect_monitors(backlight_root=Path("/no/backlight"), run=run)
        self.assertEqual(result, [
            {"bus": "5", "label": "Samsung Odyssey", "brightness": 55},
            {"bus": "8", "label": "LG UltraGear", "brightness": 55},
        ])
        self.assertEqual(queried, ["8", "5"])


if __name__ == "__main__":
    unittest.main()
