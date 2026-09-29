from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WeatherPrivacyTests(unittest.TestCase):
    def test_unconfigured_weather_has_no_geolocation_endpoint_or_auto_lookup(self) -> None:
        weather = (ROOT / "Singletons/Weather.qml").read_text()
        pill = (ROOT / "Pill.qml").read_text()
        self.assertNotIn("ip-api.com", weather)
        self.assertNotIn("http://", weather)
        self.assertIn('if (!root.configured)\n            return;', weather)
        self.assertIn("running: root.located", weather)
        self.assertIn("visible: Weather.ready", pill)

    def test_calendar_keeps_city_setup_reachable_without_forecast(self) -> None:
        calendar = (ROOT / "Calendar.qml").read_text()
        self.assertIn('text: Weather.configured ? "WEATHER · CHECKING CITY" : "WEATHER · OPTIONAL"', calendar)
        self.assertIn('text: Weather.city.length > 0 ? Weather.city : "choose city"', calendar)
        self.assertIn("Flags.weatherCity = text.trim()", calendar)

    def test_cached_location_is_bound_to_explicit_city(self) -> None:
        weather = (ROOT / "Singletons/Weather.qml").read_text()
        self.assertIn("c.query === Flags.weatherCity.trim().toLowerCase()", weather)
        self.assertIn("query: Flags.weatherCity.trim().toLowerCase()", weather)


if __name__ == "__main__":
    unittest.main()
