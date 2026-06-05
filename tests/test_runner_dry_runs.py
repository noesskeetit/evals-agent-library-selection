import json
import os
import subprocess
import sys

from evals_agent.runners.judge_config import JudgeConfig
from evals_agent.runners import run_openevals
from evals_agent.runners.run_deepeval import _test_case, build_trajectory_test_case
from evals_agent.runners.run_openevals import OpenEvalsJudgeClient


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return {"choices": [{"message": {"content": '{"score": true}'}}]}


class _FakeOpenAI:
    def __init__(self):
        self.completions = _FakeCompletions()
        self.chat = type("Chat", (), {"completions": self.completions})()


def test_openevals_judge_client_injects_cloudru_runtime_params():
    fake_openai = _FakeOpenAI()
    config = JudgeConfig(
        provider="cloudru_fm",
        api_key="secret",
        base_url="https://foundation-models.api.cloud.ru/v1",
        model="deepseek-ai/DeepSeek-V4-Pro",
        max_tokens=50_000,
        reasoning_effort="high",
    )
    client = OpenEvalsJudgeClient(fake_openai, config)

    client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": "Judge this output."}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "score", "schema": {"type": "object"}},
        },
    )

    assert fake_openai.completions.kwargs["max_tokens"] == 50_000
    assert fake_openai.completions.kwargs["reasoning_effort"] == "high"
    assert fake_openai.completions.kwargs["temperature"] == 0
    assert fake_openai.completions.kwargs["response_format"] == {"type": "json_object"}
    assert "Return only valid JSON" in fake_openai.completions.kwargs["messages"][-1]["content"]


def test_deepeval_trajectory_test_case_contains_actual_and_expected_trace():
    from evals_agent.agent import run_agent

    test_case = build_trajectory_test_case(run_agent("Need eval library"))

    assert "Actual trajectory" in test_case.actual_output
    assert "Expected golden path" in test_case.expected_output
    assert "search_repos" in test_case.actual_output


def test_deepeval_tool_correctness_uses_independent_expected_tools():
    from evals_agent.agent import run_agent
    from evals_agent.runners.common import expected_tool_names_for

    run = run_agent("Need eval library")
    test_case = _test_case(run)

    assert test_case.expected_tools is not test_case.tools_called
    assert [tool.name for tool in test_case.expected_tools] == expected_tool_names_for(run)
    for actual, expected in zip(test_case.tools_called, test_case.expected_tools):
        assert actual is not expected


def test_weather_runner_uses_agent_input_in_payload(monkeypatch):
    from evals_agent.llm_weather_agent import DEFAULT_WEATHER_TASK
    from evals_agent.trace_schema import AgentRun, FinalAnswer

    monkeypatch.setattr(
        "evals_agent.runners.common.run_weather_agent",
        lambda task: AgentRun(
            input=DEFAULT_WEATHER_TASK,
            trace=[],
            final_answer=FinalAnswer(
                recommended_repo="weather_plan",
                rationale="ok",
                evidence=[],
            ),
            metadata={"agent_type": "weather_llm", "answer_text": "ok"},
        ),
    )

    payload = run_openevals.run(dry_run=True, task="Need an eval library", agent="weather")

    assert payload["agent_run"]["input"] == DEFAULT_WEATHER_TASK


def _run_module(module: str, artifact_dir) -> dict:
    env = os.environ.copy()
    env["EVALS_ARTIFACT_DIR"] = str(artifact_dir)
    env["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

    completed = subprocess.run(
        [sys.executable, "-m", module, "--dry-run"],
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    artifact_path = completed.stdout.strip().splitlines()[-1]
    with open(artifact_path, encoding="utf-8") as handle:
        return json.load(handle)


def test_openevals_dry_run_writes_artifact(tmp_path):
    payload = _run_module("evals_agent.runners.run_openevals", tmp_path)

    assert payload["library"] == "openevals"
    assert payload["mode"] == "dry_run"
    assert payload["eval_inputs"]["blackbox_llm_as_judge"]["reference_outputs"]
    assert payload["results"]["trajectory_match"]["score"] is True


def test_deepeval_dry_run_writes_artifact(tmp_path):
    payload = _run_module("evals_agent.runners.run_deepeval", tmp_path)

    assert payload["library"] == "deepeval"
    assert payload["mode"] == "dry_run"
    assert payload["eval_inputs"]["tool_correctness"]["expected_tools"]
    assert payload["results"]["tool_correctness"]["success"] is True
