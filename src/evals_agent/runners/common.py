from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals_agent.agent import run_agent
from evals_agent.fixtures import DEFAULT_TASK
from evals_agent.llm_weather_agent import DEFAULT_WEATHER_TASK, run_weather_agent
from evals_agent.runners.judge_config import resolve_judge_config
from evals_agent.trace_schema import AgentRun, agent_run_to_dict


ROOT = Path(__file__).resolve().parents[3]

BLACKBOX_RUBRIC = """
Score whether the final answer recommends a relevant eval library for a platform
that needs both blackbox LLM-as-judge and golden-path trajectory evaluation.
The answer should cite concrete evidence and avoid unsupported claims.
"""

WEATHER_BLACKBOX_RUBRIC = """
Score whether the final answer gives a useful weather plan in blackbox mode.
Judge only the user input, final answer, and reference expectation; do not require
raw tool observations to be present. The answer should mention forecast dates,
temperature, precipitation or wind evidence, and practical recommendations. Fail
answers that are vague, do not answer the weather task, or contain obvious
unsupported contradictions.
"""


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true", help="Skip live LLM judge calls.")
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--agent",
        choices=["fixture", "weather"],
        default="fixture",
        help="Agent scenario to run before evaluating.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_root() -> Path:
    return Path(os.environ.get("EVALS_ARTIFACT_DIR", ROOT / "artifacts"))


def write_artifact(library: str, payload: dict[str, Any]) -> Path:
    directory = artifact_root() / library
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def env_status() -> dict[str, str]:
    names = [
        "FM_API_KEY",
        "CLOUDRU_FM_API_KEY",
        "CLOUDRU_FM_BASE_URL",
        "CLOUDRU_FM_MODEL",
        "CLOUDRU_FM_MAX_TOKENS",
        "CLOUDRU_FM_REASONING_EFFORT",
        "EVALS_JUDGE_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING",
        "CONFIDENT_API_KEY",
        "ANTHROPIC_API_KEY",
    ]
    return {name: "set" if os.environ.get(name) else "missing" for name in names}


def missing_live_judge_reason() -> str | None:
    return resolve_judge_config().missing_reason()


def run_fixture_agent(task: str) -> AgentRun:
    return run_agent(task)


def run_agent_by_name(agent: str, task: str | None = None) -> AgentRun:
    if agent == "fixture":
        return run_agent(task or DEFAULT_TASK)
    if agent == "weather":
        weather_task = DEFAULT_WEATHER_TASK if not task or task == DEFAULT_TASK else task
        return run_weather_agent(weather_task)
    raise ValueError(f"unknown agent: {agent}")


def final_answer_text(run: AgentRun) -> str:
    if run.metadata.get("answer_text"):
        return str(run.metadata["answer_text"])
    evidence = "\n".join(f"- {item}" for item in run.final_answer.evidence)
    return (
        f"Recommended repo: {run.final_answer.recommended_repo}\n"
        f"Rationale: {run.final_answer.rationale}\n"
        f"Evidence:\n{evidence}"
    )


def expected_blackbox_answer() -> str:
    return (
        "The answer should choose a library that supports blackbox LLM-as-judge "
        "and golden-path trajectory evaluation, explain trade-offs, and cite evidence."
    )


def expected_blackbox_answer_for(run: AgentRun) -> str:
    if run.metadata.get("agent_type") == "weather_llm":
        return (
            "The answer should provide a concise weather plan grounded in the forecast "
            "returned by tools, mention dates and weather evidence, and include practical advice."
        )
    return expected_blackbox_answer()


def blackbox_rubric_for(run: AgentRun) -> str:
    if run.metadata.get("agent_type") == "weather_llm":
        return WEATHER_BLACKBOX_RUBRIC
    return BLACKBOX_RUBRIC


def expected_tool_names_for(run: AgentRun) -> list[str]:
    if run.metadata.get("agent_type") == "weather_llm":
        return ["geocode_location", "get_weather_forecast"]
    return ["search_repos", "inspect_repo", "inspect_repo", "recommend_repo"]


def trajectory_messages(run: AgentRun) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for index, step in enumerate(run.trace):
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{index}",
                        "type": "function",
                        "function": {
                            "name": step.tool_name,
                            "arguments": json.dumps(
                                step.arguments,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        },
                    }
                ],
            }
        )
    return messages


def reference_trajectory_messages(run: AgentRun) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for index, tool_name in enumerate(expected_tool_names_for(run)):
        arguments = "{}"
        if index < len(run.trace) and run.trace[index].tool_name == tool_name:
            arguments = json.dumps(
                run.trace[index].arguments,
                ensure_ascii=False,
                sort_keys=True,
            )
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"ref_call_{index}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    }
                ],
            }
        )
    return messages


def trajectory_text(run: AgentRun) -> str:
    lines = []
    for index, step in enumerate(run.trace, start=1):
        lines.append(
            f"{index}. {step.tool_name} args={json.dumps(step.arguments, ensure_ascii=False, sort_keys=True)} "
            f"observation={json.dumps(step.observation, ensure_ascii=False, sort_keys=True)}"
        )
    return "\n".join(lines)


def expected_trajectory_text_for(run: AgentRun) -> str:
    names = " -> ".join(expected_tool_names_for(run))
    if run.metadata.get("agent_type") == "weather_llm":
        return (
            f"Expected golden path: {names}. The agent should geocode the requested "
            "location before fetching the weather forecast and should ground the final "
            "answer in forecast observations."
        )
    return (
        f"Expected golden path: {names}. The agent should search candidates, inspect "
        "OpenEvals and DeepEval, then recommend a repository using gathered evidence."
    )


def base_payload(library: str, mode: str, task: str, run: AgentRun) -> dict[str, Any]:
    return {
        "library": library,
        "mode": mode,
        "captured_at": utc_now(),
        "env": env_status(),
        "judge": resolve_judge_config().redacted_dict(),
        "agent_run": agent_run_to_dict(run),
        "results": {},
    }


def skipped_result(reason: str) -> dict[str, Any]:
    return {"status": "skipped", "reason": reason}


def normalize_eval_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {
        "repr": repr(result),
        "score": getattr(result, "score", None),
        "success": getattr(result, "success", None),
        "reason": getattr(result, "reason", None),
    }
