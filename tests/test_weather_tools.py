from evals_agent.weather_tools import geocode_location, get_weather_forecast


def test_geocode_location_returns_first_open_meteo_match(monkeypatch):
    def fake_fetch_json(url, params):
        assert "geocoding-api.open-meteo.com" in url
        assert params["name"] == "Moscow, Russia"
        return {
            "results": [
                {
                    "name": "Moscow",
                    "country": "Russia",
                    "latitude": 55.7522,
                    "longitude": 37.6156,
                    "timezone": "Europe/Moscow",
                }
            ]
        }

    monkeypatch.setattr("evals_agent.weather_tools._fetch_json", fake_fetch_json)

    result = geocode_location("Moscow, Russia")

    assert result["name"] == "Moscow"
    assert result["country"] == "Russia"
    assert result["latitude"] == 55.7522
    assert result["longitude"] == 37.6156
    assert result["timezone"] == "Europe/Moscow"


def test_get_weather_forecast_normalizes_daily_forecast(monkeypatch):
    def fake_fetch_json(url, params):
        assert "api.open-meteo.com" in url
        assert params["forecast_days"] == 3
        return {
            "timezone": "Europe/Moscow",
            "daily": {
                "time": ["2026-06-06", "2026-06-07", "2026-06-08"],
                "weather_code": [3, 61, 1],
                "temperature_2m_max": [21.0, 18.0, 23.0],
                "temperature_2m_min": [13.0, 11.0, 15.0],
                "precipitation_sum": [0.0, 4.2, 0.0],
                "wind_speed_10m_max": [12.0, 19.0, 10.0],
            },
        }

    monkeypatch.setattr("evals_agent.weather_tools._fetch_json", fake_fetch_json)

    result = get_weather_forecast(55.7522, 37.6156, forecast_days=3)

    assert result["timezone"] == "Europe/Moscow"
    assert result["forecast"][1] == {
        "date": "2026-06-07",
        "weather_code": 61,
        "condition": "rain",
        "temperature_max_c": 18.0,
        "temperature_min_c": 11.0,
        "precipitation_mm": 4.2,
        "wind_speed_max_kmh": 19.0,
    }
