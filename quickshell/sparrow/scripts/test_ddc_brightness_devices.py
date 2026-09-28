from pathlib import Path
import subprocess
import tempfile
import unittest

from ddc_brightness_devices import detect_monitors


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
Display 2
  I2C bus: /dev/i2c-2
  DRM connector: card1-DP-1
Display 3
  I2C bus: /dev/i2c-3
  DRM connector: card1-DP-2
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

        self.assertEqual(result, [{"bus": "2", "label": "DP-1", "brightness": 47}])
        self.assertEqual(queried, ["2", "3"])


if __name__ == "__main__":
    unittest.main()
