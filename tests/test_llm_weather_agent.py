import json
from types import SimpleNamespace

from evals_agent.llm_weather_agent import WEATHER_AGENT_MODEL, run_weather_agent


class FakeCompletions:
    def __init__(self):
        self.calls = 0
        self.requests = []

    def create(self, **kwargs):
        self.calls += 1
        self.requests.append(kwargs)
        if self.calls == 1:
            return _response(
                tool_calls=[
                    _tool_call(
                        "call_1",
                        "geocode_location",
                        {"location": "Moscow, Russia"},
                    )
                ]
            )
        if self.calls == 2:
            return _response(
                tool_calls=[
                    _tool_call(
                        "call_2",
                        "get_weather_forecast",
                        {
                            "latitude": 55.7522,
                            "longitude": 37.6156,
                            "forecast_days": 3,
                        },
                    )
                ]
            )
        return _response(content="In Moscow, take an umbrella tomorrow and plan indoor backup activities.")


class FakeClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _response(content="", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_weather_agent_runs_llm_tool_loop(monkeypatch):
    monkeypatch.setattr(
        "evals_agent.llm_weather_agent.execute_weather_tool",
        lambda name, arguments: {"tool": name, "arguments": arguments, "status": "ok"},
    )
    client = FakeClient()

    result = run_weather_agent(
        "Give me a short weather plan for Moscow, Russia for the next 3 days.",
        client=client,
    )

    assert result.metadata["agent_type"] == "weather_llm"
    assert result.metadata["model"] == WEATHER_AGENT_MODEL
    assert [step.tool_name for step in result.trace] == [
        "geocode_location",
        "get_weather_forecast",
    ]
    assert result.metadata["answer_text"].startswith("In Moscow")
    assert result.final_answer.recommended_repo == "weather_plan"
    assert client.completions.requests[0]["model"] == WEATHER_AGENT_MODEL
    assert client.completions.requests[0]["tools"]
