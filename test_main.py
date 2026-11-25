import unittest
from unittest.mock import Mock, call, patch

import requests

import main


CONFIG = {
    "COOPER_CHAT_URL": "https://chat.example.test",
    "FAMILY_SECRET": "test-secret",
    "BOT_USERNAME": "WeatherBot",
    "RECIPIENT_NAME": "Cooper",
    "WEATHER_LOCATION": "Sonora, CA",
}


class DailyReportTests(unittest.TestCase):
    @patch("main.get_weather_message", side_effect=requests.ReadTimeout("Unavailable"))
    @patch("main.CooperChatClient")
    def test_failed_weather_preserves_previous_unread_report(self, client_class, get_weather):
        client = client_class.return_value
        client.find_user_by_name.return_value = {"id": 6}

        with self.assertRaises(requests.ReadTimeout):
            main.send_daily_report(CONFIG)

        client.expire_messages.assert_not_called()
        client.send_message.assert_not_called()

    @patch("main.get_weather_message", return_value="Today's forecast")
    @patch("main.CooperChatClient")
    def test_successful_report_fetches_before_expiring_and_sending(self, client_class, get_weather):
        client = client_class.return_value
        client.find_user_by_name.return_value = {"id": 6}
        client.expire_messages.return_value = 1
        client.send_message.return_value = {"id": 123}
        operations = Mock()
        operations.attach_mock(get_weather, "fetch")
        operations.attach_mock(client.expire_messages, "expire")
        operations.attach_mock(client.send_message, "send")

        main.send_daily_report(CONFIG)

        self.assertEqual(operations.mock_calls, [
            call.fetch("Sonora, CA"),
            call.expire(6),
            call.send(6, "Today's forecast"),
        ])

    @patch("main.sys.argv", ["main.py"])
    @patch("main.load_env", return_value=CONFIG)
    @patch("main.send_daily_report", side_effect=requests.ReadTimeout("Unavailable"))
    def test_cli_reports_failure_and_exits_nonzero(self, send_report, load_env):
        with self.assertLogs("weatherbot", level="ERROR") as logs:
            with self.assertRaises(SystemExit) as raised:
                main.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Daily weather report failed: Unavailable", logs.output[0])
