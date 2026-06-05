from evals_agent.runners.common import (
    blackbox_rubric_for,
    expected_blackbox_answer_for,
    expected_tool_names_for,
    final_answer_text,
    run_agent_by_name,
)
from evals_agent.trace_schema import AgentRun, FinalAnswer


def test_final_answer_text_uses_weather_answer_text_metadata():
    run = AgentRun(
        input="weather",
        trace=[],
        final_answer=FinalAnswer(
            recommended_repo="weather_plan",
            rationale="legacy rationale",
            evidence=[],
        ),
        metadata={"agent_type": "weather_llm", "answer_text": "Use an umbrella."},
    )

    assert final_answer_text(run) == "Use an umbrella."


def test_weather_eval_prompts_are_weather_specific():
    run = AgentRun(
        input="weather",
        trace=[],
        final_answer=FinalAnswer(
            recommended_repo="weather_plan",
            rationale="Use an umbrella.",
            evidence=[],
        ),
        metadata={"agent_type": "weather_llm"},
    )

    assert "weather" in blackbox_rubric_for(run).lower()
    assert "forecast" in expected_blackbox_answer_for(run).lower()
    assert expected_tool_names_for(run) == ["geocode_location", "get_weather_forecast"]


def test_run_agent_by_name_dispatches_weather(monkeypatch):
    expected = AgentRun(
        input="task",
        trace=[],
        final_answer=FinalAnswer(
            recommended_repo="weather_plan",
            rationale="ok",
            evidence=[],
        ),
        metadata={"agent_type": "weather_llm"},
    )
    monkeypatch.setattr("evals_agent.runners.common.run_weather_agent", lambda task: expected)

    assert run_agent_by_name("weather", "task") is expected
