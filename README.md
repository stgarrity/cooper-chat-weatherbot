# WeatherBot for Cooper Chat

A bot that sends a daily weather forecast message via [Cooper Chat](https://chat.garrity.org:8443).

## How It Works

1. Authenticates as a bot user (`is_bot: true`)
2. Finds the recipient by name in the contacts list
3. Fetches weather from [Open-Meteo](https://open-meteo.com/) (free, no API key)
4. Expires (marks as read) any previous unread messages to the recipient
5. Sends a formatted weather message

This ensures there's never more than one unread message from the bot.

Weather lookups use 15-second connect and 30-second read timeouts. Timeouts,
connection failures, and HTTP 429/500/502/503/504 responses are retried up to
three times, waiting 2, 4, then 8 seconds. Permanent HTTP errors and certificate
errors fail immediately. If fetching fails, the previous unread report is kept
and the daily task exits nonzero with an error message.

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `COOPER_CHAT_URL` | Yes | `https://chat.garrity.org:8443` | Server base URL |
| `FAMILY_SECRET` | Yes | `ReadingAndWriting` | Auth secret |
| `BOT_USERNAME` | Yes | `WeatherBot` | Bot's display name |
| `RECIPIENT_NAME` | Yes | `Cooper` | Who to send weather to |
| `WEATHER_LOCATION` | Yes | `Sonora, CA` | Location for forecast |

## Running Locally

```bash
# Create and configure .env
cp .env.example .env
# Edit .env with your values

# Install dependencies in a virtual environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run
.venv/bin/python main.py

# Run regression tests
.venv/bin/python -m unittest discover -v
```

## Docker

```bash
# Build
docker build -t cooper-chat-weatherbot .

# Run with mounted .env file
docker run --rm -v $(pwd)/.env:/app/.env:ro cooper-chat-weatherbot

# Build for Synology NAS (AMD64)
docker buildx build --platform linux/amd64 -t cooper-chat-weatherbot:latest --load .
```

## Synology NAS Deployment

1. Push image to Docker Hub (CI does this on merge to master)
2. On NAS, create config directory:
   ```bash
   mkdir -p /volume1/docker/weatherbot/config
   ```
3. Copy `.env` to NAS:
   ```bash
   cat .env | ssh nas.internal.projectoxbow.com "cat > /volume1/docker/weatherbot/config/.env"
   ssh nas.internal.projectoxbow.com "chmod 600 /volume1/docker/weatherbot/config/.env"
   ```
4. Create Task Scheduler entry (DSM → Control Panel → Task Scheduler):
   - **User**: root
   - **Schedule**: Daily at 7:00 AM
   - **Script**:
     ```bash
     docker pull stgarrity/cooper-chat-weatherbot:latest
     docker run --rm \
       -v /volume1/docker/weatherbot/config/.env:/app/.env:ro \
       stgarrity/cooper-chat-weatherbot:latest \
       >> /volume1/docker/weatherbot/run.log 2>&1
     ```
