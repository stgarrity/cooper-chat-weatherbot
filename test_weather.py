import unittest
from unittest.mock import Mock, call, patch

import requests

import weather


class WeatherRequestTests(unittest.TestCase):
    def setUp(self):
        self.get = patch("weather.requests.get").start()
        self.sleep = patch("weather.time.sleep").start()
        self.addCleanup(patch.stopall)

    def response(self, status=200, data=None):
        response = Mock(status_code=status)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.json.return_value = data
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    def test_forecast_recovers_from_tls_handshake_timeout(self):
        data = {"current": {"temperature_2m": 50}}
        self.get.side_effect = [requests.ReadTimeout("TLS handshake timed out"), self.response(data=data)]

        with self.assertLogs("weatherbot.weather", level="WARNING"):
            self.assertEqual(weather.fetch_weather(37.98, -120.38), data)

        self.assertEqual(self.get.call_count, 2)
        self.sleep.assert_called_once_with(2)
        self.assertEqual(self.get.call_args.kwargs["timeout"], (15, 30))

    def test_geocoding_recovers_from_connection_failure(self):
        data = {"results": [{"latitude": 37.98, "longitude": -120.38, "name": "Sonora", "admin1": "California"}]}
        self.get.side_effect = [requests.ConnectionError("Connection reset"), self.response(data=data)]

        with self.assertLogs("weatherbot.weather", level="WARNING"):
            result = weather.geocode("Sonora, CA")

        self.assertEqual(result, (37.98, -120.38, "Sonora, California"))
        self.assertEqual(self.get.call_args.args[0], weather.GEOCODING_URL)

    def test_transient_http_errors_are_retried(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                failed = self.response(status=status)
                self.get.side_effect = [failed, self.response(data={"ok": True})]
                with self.assertLogs("weatherbot.weather", level="WARNING"):
                    self.assertEqual(weather.fetch_weather(0, 0), {"ok": True})
                failed.__exit__.assert_called_once()

    def test_repeated_timeouts_fail_after_bounded_backoff(self):
        error = requests.ReadTimeout("Still unavailable")
        self.get.side_effect = error

        with self.assertLogs("weatherbot.weather", level="WARNING") as logs:
            with self.assertRaises(requests.ReadTimeout) as raised:
                weather.fetch_weather(0, 0)

        self.assertIs(raised.exception, error)
        self.assertEqual(self.get.call_count, 4)
        self.assertEqual(self.sleep.call_args_list, [call(2), call(4), call(8)])
        self.assertEqual(len(logs.output), 3)

    def test_permanent_errors_are_not_retried(self):
        for error in (requests.HTTPError(response=Mock(status_code=400)), requests.exceptions.SSLError("Invalid certificate")):
            with self.subTest(error=type(error).__name__):
                self.get.reset_mock()
                self.get.side_effect = error
                with self.assertRaises(type(error)):
                    weather.fetch_weather(0, 0)
                self.get.assert_called_once()
                self.sleep.assert_not_called()

    def test_exhausted_http_errors_remain_failures(self):
        self.get.return_value = self.response(status=503)
        with self.assertLogs("weatherbot.weather", level="WARNING"):
            with self.assertRaises(requests.HTTPError):
                weather.fetch_weather(0, 0)
        self.assertEqual(self.get.call_count, 4)

    def test_unknown_location_is_not_retried(self):
        self.get.return_value = self.response(data={"results": []})
        with self.assertRaisesRegex(ValueError, "Could not find location"):
            weather.geocode("Missing town")
        self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_invalid_json_is_not_retried(self):
        response = self.response()
        response.json.side_effect = requests.exceptions.JSONDecodeError("Invalid JSON", "", 0)
        self.get.return_value = response
        with self.assertRaises(requests.exceptions.JSONDecodeError):
            weather.fetch_weather(0, 0)
        self.get.assert_called_once()
        self.sleep.assert_not_called()
