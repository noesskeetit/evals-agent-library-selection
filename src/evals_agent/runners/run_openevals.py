from __future__ import annotations

import importlib.metadata as md
import json
from typing import Any

from openai import OpenAI
from openevals.llm import create_llm_as_judge
from openevals.trajectory import (
    create_trajectory_llm_as_judge,
    create_trajectory_match_evaluator,
)

from evals_agent.runners.common import (
    base_payload,
    blackbox_rubric_for,
    expected_blackbox_answer_for,
    final_answer_text,
    missing_live_judge_reason,
    normalize_eval_result,
    parse_args,
    run_agent_by_name,
    skipped_result,
    reference_trajectory_messages,
    trajectory_messages,
    write_artifact,
)
from evals_agent.runners.judge_config import JudgeConfig, resolve_judge_config


class OpenEvalsJudgeClient:
    def __init__(self, client: OpenAI, config: JudgeConfig):
        self.chat = _OpenEvalsChat(client.chat, config)


class _OpenEvalsChat:
    def __init__(self, chat: Any, config: JudgeConfig):
        self.completions = _OpenEvalsCompletions(chat.completions, config)


class _OpenEvalsCompletions:
    def __init__(self, completions: Any, config: JudgeConfig):
        self._completions = completions
        self._config = config

    def create(self, **kwargs: Any) -> Any:
        kwargs.setdefault("temperature", 0)
        kwargs.setdefault("max_tokens", self._config.max_tokens)
        if self._config.reasoning_effort:
            kwargs.setdefault("reasoning_effort", self._config.reasoning_effort)
        self._normalize_response_format(kwargs)
        return self._completions.create(**kwargs)

    def _normalize_response_format(self, kwargs: dict[str, Any]) -> None:
        response_format = kwargs.get("response_format")
        if not isinstance(response_format, dict):
            return
        if response_format.get("type") != "json_schema":
            return

        schema = response_format.get("json_schema", {})
        kwargs["response_format"] = {"type": "json_object"}
        instruction = (
            "\n\nReturn only valid JSON matching this schema. Do not include markdown "
            f"or prose outside the JSON object:\n{json.dumps(schema, ensure_ascii=False)}"
        )
        messages = list(kwargs.get("messages") or [])
        if messages:
            last = dict(messages[-1])
            last["content"] = f"{last.get('content', '')}{instruction}"
            messages[-1] = last
            kwargs["messages"] = messages


def _build_judge_client(config: JudgeConfig) -> OpenEvalsJudgeClient:
    return OpenEvalsJudgeClient(
        OpenAI(api_key=config.api_key, base_url=config.base_url),
        config,
    )


def run(dry_run: bool, task: str, agent: str = "fixture") -> dict:
    agent_run = run_agent_by_name(agent, task)
    eval_input = agent_run.input
    payload = base_payload("openevals", "dry_run" if dry_run else "live_or_skip", eval_input, agent_run)
    payload["package_version"] = md.version("openevals")

    outputs = trajectory_messages(agent_run)
    reference_outputs = reference_trajectory_messages(agent_run)
    tool_args_match_mode = (
        "ignore" if agent_run.metadata.get("agent_type") == "weather_llm" else "exact"
    )
    match_evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="strict",
        tool_args_match_mode=tool_args_match_mode,
    )
    payload["results"]["trajectory_match"] = normalize_eval_result(
        match_evaluator(outputs=outputs, reference_outputs=reference_outputs)
    )

    missing_reason = missing_live_judge_reason()
    if dry_run:
        missing_reason = "dry-run mode; live LLM-as-judge intentionally skipped."

    if missing_reason:
        payload["results"]["blackbox_llm_as_judge"] = skipped_result(missing_reason)
        payload["results"]["trajectory_llm_as_judge"] = skipped_result(missing_reason)
        return payload

    judge_config = resolve_judge_config()
    judge = _build_judge_client(judge_config)
    blackbox_evaluator = create_llm_as_judge(
        prompt=blackbox_rubric_for(agent_run) + "\nInputs:\n{inputs}\nOutputs:\n{outputs}\nReference:\n{reference_outputs}",
        judge=judge,
        model=judge_config.model,
        feedback_key="blackbox_quality",
    )
    payload["results"]["blackbox_llm_as_judge"] = normalize_eval_result(
        blackbox_evaluator(
            inputs=eval_input,
            outputs=final_answer_text(agent_run),
            reference_outputs=expected_blackbox_answer_for(agent_run),
        )
    )

    trajectory_evaluator = create_trajectory_llm_as_judge(
        judge=judge,
        model=judge_config.model,
    )
    payload["results"]["trajectory_llm_as_judge"] = normalize_eval_result(
        trajectory_evaluator(outputs=outputs, reference_outputs=reference_outputs)
    )
    return payload


def main() -> None:
    args = parse_args("Run OpenEvals benchmark.")
    payload = run(dry_run=args.dry_run, task=args.task, agent=args.agent)
    path = write_artifact("openevals", payload)
    print(path)


if __name__ == "__main__":
    main()
