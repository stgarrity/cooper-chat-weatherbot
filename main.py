"""WeatherBot for Cooper Chat — daily forecast + interactive weather chat."""

import logging
import os
import sys

from chat import CooperChatClient
from weather import get_weather_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("weatherbot")


def load_env() -> dict:
    """Load and validate required environment variables."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        log.info("Loading .env from %s", env_path)
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    required = ["COOPER_CHAT_URL", "FAMILY_SECRET", "BOT_USERNAME", "RECIPIENT_NAME", "WEATHER_LOCATION"]
    config = {}
    missing = []
    for key in required:
        val = os.environ.get(key)
        if not val:
            missing.append(key)
        else:
            config[key] = val

    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    return config


def send_daily_report(config: dict):
    """Send the daily weather forecast (original behavior)."""
    url = config["COOPER_CHAT_URL"]
    bot_name = config["BOT_USERNAME"]
    recipient_name = config["RECIPIENT_NAME"]
    location = config["WEATHER_LOCATION"]

    log.info("Authenticating as '%s' at %s", bot_name, url)
    client = CooperChatClient(url)
    client.register(bot_name, config["FAMILY_SECRET"], is_bot=True)
    log.info("Authenticated (user_id=%s)", client.user_id)

    log.info("Looking up recipient '%s'", recipient_name)
    recipient = client.find_user_by_name(recipient_name)
    recipient_id = recipient["id"]

    expired = client.expire_messages(recipient_id)
    if expired > 0:
        log.info("Expired %d old unread message(s)", expired)

    log.info("Fetching weather for '%s'", location)
    message = get_weather_message(location)
    log.info("Weather message:\n%s", message)

    result = client.send_message(recipient_id, message)
    log.info("Message sent (id=%s)", result.get("id"))
    log.info("Done!")


def listen(config: dict):
    """Run the interactive listener (long-running)."""
    from openai import OpenAI
    from conversation import listen_loop

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("OPENAI_API_KEY required for --listen mode")
        sys.exit(1)

    url = config["COOPER_CHAT_URL"]
    bot_name = config["BOT_USERNAME"]

    log.info("Authenticating as '%s' at %s", bot_name, url)
    client = CooperChatClient(url)
    client.register(bot_name, config["FAMILY_SECRET"], is_bot=True)
    log.info("Authenticated (user_id=%s)", client.user_id)

    openai_client = OpenAI(api_key=api_key)
    listen_loop(client, openai_client)


def main():
    config = load_env()

    if "--listen" in sys.argv:
        listen(config)
    else:
        send_daily_report(config)


if __name__ == "__main__":
    main()
