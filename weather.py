"""Open-Meteo weather client for WeatherBot."""

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather Codes → (description, emoji)
WMO_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌦️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow", "🌨️"),
    73: ("Moderate snow", "🌨️"),
    75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "❄️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


def geocode(location: str) -> tuple[float, float, str]:
    """Resolve a location name to coordinates. Returns (lat, lon, display_name)."""
    resp = requests.get(GEOCODING_URL, params={"name": location.split(",")[0].strip(), "count": 1, "format": "json"}, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("results"):
        raise ValueError(f"Could not find location: {location}")

    result = data["results"][0]
    name = result.get("name", location)
    admin = result.get("admin1", "")
    display = f"{name}, {admin}" if admin else name
    return result["latitude"], result["longitude"], display


def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather and daily forecast from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "auto",
        "forecast_days": 1,
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def format_message(weather: dict, location_name: str) -> str:
    """Format weather data into a friendly chat message."""
    current = weather.get("current", {})
    daily = weather.get("daily", {})

    current_temp = current.get("temperature_2m")
    current_code = current.get("weather_code", 0)
    wind_speed = current.get("wind_speed_10m")

    high = daily.get("temperature_2m_max", [None])[0]
    low = daily.get("temperature_2m_min", [None])[0]
    daily_code = daily.get("weather_code", [0])[0]
    precip_chance = daily.get("precipitation_probability_max", [None])[0]

    description, emoji = WMO_CODES.get(daily_code, ("Unknown", "🌡️"))

    lines = [f"{emoji} Good morning! Here's today's weather for {location_name}:"]
    lines.append("")

    if high is not None and low is not None:
        lines.append(f"🌡️ High {high:.0f}°F / Low {low:.0f}°F")

    lines.append(f"🌤️ {description}")

    if precip_chance is not None and precip_chance > 0:
        lines.append(f"🌧️ {precip_chance}% chance of precipitation")

    if wind_speed is not None:
        lines.append(f"💨 Wind {wind_speed:.0f} mph")

    if current_temp is not None:
        lines.append(f"\nRight now: {current_temp:.0f}°F")

    return "\n".join(lines)


def get_weather_message(location: str) -> str:
    """Full pipeline: geocode location, fetch weather, format message."""
    lat, lon, display_name = geocode(location)
    weather = fetch_weather(lat, lon)
    return format_message(weather, display_name)
