"""Interactive conversation handler using OpenAI for WeatherBot.

Polls for incoming messages and replies using GPT with weather tools.
NOTE: Cooper Chat does not support emoji. Keep all responses ASCII-only.
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta

from openai import OpenAI

from chat import CooperChatClient
from weather import geocode, fetch_weather

log = logging.getLogger("weatherbot.conversation")

SYSTEM_PROMPT = """You are WeatherBot, a friendly weather assistant in a family chat app called Cooper Chat. You help kids and family members learn about weather.

Rules:
- Keep responses SHORT (2-4 sentences max). You're chatting with kids.
- Do NOT use emoji. Cooper Chat doesn't support them.
- Be fun, friendly, and educational.
- Use the tools to look up real weather data. Never make up weather info.
- Temperatures are in Fahrenheit.
- If asked about something not weather-related, be brief and redirect: "I'm WeatherBot! I know about weather. Ask me about the forecast, temperature, or if it'll rain!"
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and today's forecast for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and state/country, e.g. 'Sonora, CA' or 'London, UK'",
                    }
                },
                "required": ["location"],
            },
        },
    },
]


SESSION_TIMEOUT = timedelta(hours=1)


def _build_history_messages(
    history: list[dict], bot_user_id: int, sender_name: str,
) -> list[dict]:
    """Build OpenAI message array from conversation history within session timeout."""
    cutoff = datetime.now(timezone.utc) - SESSION_TIMEOUT
    messages = []
    for msg in history:
        created_str = msg.get("created_at", "")
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if created < cutoff:
            continue
        content = msg.get("content", "")
        if msg.get("sender_id") == bot_user_id:
            messages.append({"role": "assistant", "content": content})
        else:
            messages.append({"role": "user", "content": f"{sender_name} says: {content}"})
    return messages


def _handle_tool_call(name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "get_weather":
        location = args.get("location", "")
        try:
            lat, lon, display = geocode(location)
            weather = fetch_weather(lat, lon)
            current = weather.get("current", {})
            daily = weather.get("daily", {})
            return json.dumps({
                "location": display,
                "current_temp_f": current.get("temperature_2m"),
                "wind_mph": current.get("wind_speed_10m"),
                "high_f": daily.get("temperature_2m_max", [None])[0],
                "low_f": daily.get("temperature_2m_min", [None])[0],
                "precip_chance": daily.get("precipitation_probability_max", [None])[0],
                "weather_code": daily.get("weather_code", [None])[0],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown tool: {name}"})


def reply_to_message(
    openai_client: OpenAI, sender_name: str, message_text: str,
    history: list[dict] | None = None, bot_user_id: int | None = None,
) -> str:
    """Generate a reply to a user message using GPT with weather tools."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    history_msgs = (
        _build_history_messages(history, bot_user_id, sender_name)
        if history and bot_user_id is not None
        else []
    )
    if history_msgs:
        messages.extend(history_msgs)
    else:
        messages.append({"role": "user", "content": f"{sender_name} says: {message_text}"})

    response = openai_client.chat.completions.create(
        model="gpt-5.4",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    msg = response.choices[0].message

    # Handle tool calls
    if msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            result = _handle_tool_call(tc.function.name, json.loads(tc.function.arguments))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        response = openai_client.chat.completions.create(
            model="gpt-5.4",
            messages=messages,
        )
        msg = response.choices[0].message

    return msg.content or "Sorry, I couldn't come up with a response!"


def listen_loop(
    chat_client: CooperChatClient,
    openai_client: OpenAI,
    poll_interval: int = 10,
):
    """Poll for new messages and reply to them. Runs forever."""
    log.info("Listening for messages (poll every %ds)...", poll_interval)
    seen_ids: set[int] = set()

    # Mark all current unread as seen (don't reply to old messages on startup)
    existing = chat_client.get_inbox(unread_only=True)
    for msg in existing:
        seen_ids.add(msg["id"])
        chat_client.mark_as_read(msg["id"])
    if existing:
        log.info("Marked %d existing unread messages as seen", len(existing))

    # Build sender ID → name map
    contacts = chat_client.get_contacts()
    sender_names: dict[int, str] = {c["id"]: c["name"] for c in contacts}

    while True:
        try:
            unread = chat_client.get_inbox(unread_only=True)
            for msg in unread:
                msg_id = msg["id"]
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)

                sender_id = msg["sender_id"]
                sender_name = sender_names.get(sender_id, f"User {sender_id}")
                content = msg.get("content", "")

                log.info("Message from %s: %s", sender_name, content[:80])

                try:
                    history = chat_client.get_conversation(sender_id, limit=20)
                    reply = reply_to_message(
                        openai_client, sender_name, content,
                        history=history, bot_user_id=chat_client.user_id,
                    )
                    chat_client.send_message(sender_id, reply)
                    log.info("Replied to %s: %s", sender_name, reply[:80])
                except Exception as e:
                    log.error("Failed to reply to %s: %s", sender_name, e)

                chat_client.mark_as_read(msg_id)

        except Exception as e:
            log.error("Poll error: %s", e)

        time.sleep(poll_interval)
