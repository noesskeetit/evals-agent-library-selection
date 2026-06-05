from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "evals-weather-agent/0.1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _weather_condition(code: int | None) -> str:
    if code is None:
        return "unknown"
    if code == 0:
        return "clear"
    if code in {1, 2, 3}:
        return "partly_cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return "unknown"


def geocode_location(location: str) -> dict[str, Any]:
    payload = _fetch_json(
        GEOCODING_URL,
        {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )
    results = payload.get("results") or []
    if not results:
        return {"status": "not_found", "location": location}

    first = results[0]
    return {
        "status": "ok",
        "name": first.get("name"),
        "country": first.get("country"),
        "latitude": first.get("latitude"),
        "longitude": first.get("longitude"),
        "timezone": first.get("timezone"),
        "source": "open-meteo-geocoding",
    }


def get_weather_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 3,
) -> dict[str, Any]:
    payload = _fetch_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                ]
            ),
            "timezone": "auto",
            "forecast_days": forecast_days,
        },
    )
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    forecast: list[dict[str, Any]] = []
    for index, date in enumerate(dates):
        weather_code = _list_value(daily, "weather_code", index)
        forecast.append(
            {
                "date": date,
                "weather_code": weather_code,
                "condition": _weather_condition(weather_code),
                "temperature_max_c": _list_value(daily, "temperature_2m_max", index),
                "temperature_min_c": _list_value(daily, "temperature_2m_min", index),
                "precipitation_mm": _list_value(daily, "precipitation_sum", index),
                "wind_speed_max_kmh": _list_value(daily, "wind_speed_10m_max", index),
            }
        )
    return {
        "status": "ok",
        "latitude": latitude,
        "longitude": longitude,
        "timezone": payload.get("timezone"),
        "forecast": forecast,
        "source": "open-meteo-forecast",
    }


def _list_value(payload: dict[str, Any], key: str, index: int) -> Any:
    values = payload.get(key) or []
    if index >= len(values):
        return None
    return values[index]
