from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from evals_agent.runners.judge_config import resolve_judge_config
from evals_agent.trace_schema import AgentRun, FinalAnswer, TraceStep
from evals_agent.weather_tools import geocode_location, get_weather_forecast


WEATHER_AGENT_MODEL = "moonshotai/Kimi-K2.6"
DEFAULT_WEATHER_TASK = "Give me a short weather plan for Moscow, Russia for the next 3 days."


WEATHER_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "geocode_location",
            "description": "Resolve a city or place name to latitude, longitude, and timezone using Open-Meteo geocoding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location name, for example 'Moscow, Russia'.",
                    }
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Fetch a daily weather forecast from Open-Meteo for coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "forecast_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "default": 3,
                    },
                },
                "required": ["latitude", "longitude"],
                "additionalProperties": False,
            },
        },
    },
]


SYSTEM_PROMPT = """You are a weather planning agent.
Use tools to get real weather data before answering.
First geocode the requested location, then fetch a forecast, then answer concisely.
Do not invent weather values that are not present in tool observations.
Mention the evidence you used: temperature, precipitation, wind, and dates.
"""


def execute_weather_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "geocode_location":
        return geocode_location(location=str(arguments["location"]))
    if name == "get_weather_forecast":
        return get_weather_forecast(
            latitude=float(arguments["latitude"]),
            longitude=float(arguments["longitude"]),
            forecast_days=int(arguments.get("forecast_days", 3)),
        )
    return {"status": "error", "error": f"unknown tool: {name}"}


def run_weather_agent(
    task: str = DEFAULT_WEATHER_TASK,
    *,
    client: Any | None = None,
    max_steps: int = 6,
) -> AgentRun:
    config = resolve_judge_config()
    model = WEATHER_AGENT_MODEL
    if client is None:
        client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    trace: list[TraceStep] = []

    final_text = ""
    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=WEATHER_TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0,
            max_tokens=4096,
        )
        message = response.choices[0].message
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        if not tool_calls:
            final_text = str(getattr(message, "content", "") or "")
            break

        messages.append(_assistant_tool_call_message(message))
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")
            observation = execute_weather_tool(tool_name, arguments)
            trace.append(
                TraceStep(
                    tool_name=tool_name,
                    arguments=arguments,
                    observation=observation,
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(observation, ensure_ascii=False),
                }
            )

    if not final_text:
        final_text = "Unable to produce a weather plan within the step budget."

    evidence = _weather_evidence(trace)
    return AgentRun(
        input=task,
        trace=trace,
        final_answer=FinalAnswer(
            recommended_repo="weather_plan",
            rationale=final_text,
            evidence=evidence,
        ),
        metadata={
            "fixture": "weather_agent_v1",
            "agent_type": "weather_llm",
            "model": model,
            "answer_text": final_text,
        },
    )


def _assistant_tool_call_message(message: Any) -> dict[str, Any]:
    tool_calls = []
    for call in getattr(message, "tool_calls", None) or []:
        tool_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
        )
    return {
        "role": "assistant",
        "content": getattr(message, "content", "") or "",
        "tool_calls": tool_calls,
    }


def _weather_evidence(trace: list[TraceStep]) -> list[str]:
    evidence: list[str] = []
    for step in trace:
        if step.tool_name == "geocode_location" and step.observation.get("status") == "ok":
            evidence.append(
                f"Geocoded {step.observation.get('name')}, {step.observation.get('country')} "
                f"to {step.observation.get('latitude')}, {step.observation.get('longitude')}."
            )
        if step.tool_name == "get_weather_forecast" and step.observation.get("status") == "ok":
            forecast = step.observation.get("forecast") or []
            evidence.append(f"Fetched {len(forecast)} daily forecast rows from Open-Meteo.")
    return evidence
