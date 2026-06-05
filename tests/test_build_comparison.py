import json
from pathlib import Path

from evals_agent.runners.build_comparison import build_matrix


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _keys(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _keys(item)


def test_build_matrix_uses_fresh_artifact_paths(tmp_path):
    agent_run = {
        "input": "weather task",
        "trace": [
            {"tool_name": "geocode_location"},
            {"tool_name": "get_weather_forecast"},
        ],
        "metadata": {"agent_type": "weather_llm", "model": "moonshotai/Kimi-K2.6"},
    }
    judge = {
        "provider": "cloudru_fm",
        "base_url": "https://foundation-models.api.cloud.ru/v1",
        "model": "deepseek-ai/DeepSeek-V4-Pro",
        "max_tokens": 50000,
        "reasoning_effort": "high",
        "cloudru_host_in_no_proxy": True,
    }
    openevals = _write(
        tmp_path / "openevals.json",
        {
            "agent_run": agent_run,
            "judge": judge,
            "results": {
                "trajectory_match": {"score": True, "key": "trajectory_strict_match"},
                "trajectory_llm_as_judge": {"score": True, "comment": "ok"},
                "blackbox_llm_as_judge": {"score": True, "comment": "ok"},
            },
        },
    )
    deepeval = _write(
        tmp_path / "deepeval.json",
        {
            "agent_run": agent_run,
            "judge": judge,
            "results": {
                "tool_correctness": {"score": 1.0, "success": True},
                "trajectory_g_eval": {"score": 1.0, "success": True, "reason": "ok"},
                "blackbox_g_eval": {"score": 1.0, "success": True, "reason": "ok"},
            },
        },
    )

    matrix = build_matrix(openevals_path=openevals, deepeval_path=deepeval)

    assert matrix["agent_under_test"]["tools_called"] == [
        "geocode_location",
        "get_weather_forecast",
    ]
    assert len(matrix["variants"]) == 4
    assert matrix["selection"]["tracing_assessment_mode"] == "doc_based_not_live_otel_export"
    assert "env" not in set(_keys(matrix))
    assert "api_key" not in json.dumps(matrix)
