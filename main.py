"""WeatherBot for Cooper Chat — sends a daily weather forecast message."""

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
    # Support .env file mounted into container
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


def main():
    config = load_env()

    url = config["COOPER_CHAT_URL"]
    bot_name = config["BOT_USERNAME"]
    recipient_name = config["RECIPIENT_NAME"]
    location = config["WEATHER_LOCATION"]

    # 1. Authenticate
    log.info("Authenticating as '%s' at %s", bot_name, url)
    client = CooperChatClient(url)
    client.register(bot_name, config["FAMILY_SECRET"], is_bot=True)
    log.info("Authenticated (user_id=%s)", client.user_id)

    # 2. Find recipient
    log.info("Looking up recipient '%s'", recipient_name)
    recipient = client.find_user_by_name(recipient_name)
    recipient_id = recipient["id"]
    log.info("Found recipient: %s (id=%s)", recipient["name"], recipient_id)

    # 3. Expire old unread messages
    expired = client.expire_messages(recipient_id)
    if expired > 0:
        log.info("Expired %d old unread message(s)", expired)

    # 4. Fetch weather
    log.info("Fetching weather for '%s'", location)
    message = get_weather_message(location)
    log.info("Weather message:\n%s", message)

    # 5. Send message
    log.info("Sending weather to %s", recipient["name"])
    result = client.send_message(recipient_id, message)
    log.info("Message sent (id=%s)", result.get("id"))

    log.info("Done!")


if __name__ == "__main__":
    main()
