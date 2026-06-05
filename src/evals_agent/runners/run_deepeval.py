from __future__ import annotations

import importlib.metadata as md
import os

from openai import OpenAI

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("CONFIDENT_TRACE_VERBOSE", "0")
os.environ.setdefault("CONFIDENT_TRACE_FLUSH", "0")

from deepeval.metrics import GEval, ToolCorrectnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

from evals_agent.runners.common import (
    base_payload,
    blackbox_rubric_for,
    expected_blackbox_answer_for,
    expected_tool_names_for,
    expected_trajectory_text_for,
    final_answer_text,
    missing_live_judge_reason,
    parse_args,
    run_agent_by_name,
    skipped_result,
    trajectory_text,
    write_artifact,
)
from evals_agent.runners.judge_config import JudgeConfig, resolve_judge_config
from evals_agent.trace_schema import AgentRun


class NoopJudgeModel(DeepEvalBaseLLM):
    def load_model(self):
        return self

    def generate(self, *args, **kwargs) -> str:
        return '{"score": 1, "reason": "Local deterministic dry-run judge."}'

    async def a_generate(self, *args, **kwargs) -> str:
        return self.generate(*args, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:
        return "noop-local-judge"


class CloudRuFMJudgeModel(DeepEvalBaseLLM):
    def __init__(self, config: JudgeConfig):
        self.config = config
        super().__init__(model=config.model)

    def load_model(self):
        return OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)

    def generate(self, prompt: str, schema=None, **kwargs) -> str:
        request_kwargs = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "reasoning_effort": self.config.reasoning_effort,
        }
        if schema is not None:
            request_kwargs["response_format"] = {"type": "json_object"}

        response = self.model.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content
        return content or ""

    async def a_generate(self, *args, **kwargs) -> str:
        return self.generate(*args, **kwargs)

    def get_model_name(self, *args, **kwargs) -> str:
        return f"cloudru-fm:{self.config.model}"


def _tool_calls(run: AgentRun) -> list[ToolCall]:
    return [
        ToolCall(
            name=step.tool_name,
            input_parameters=step.arguments,
            output=step.observation,
        )
        for step in run.trace
    ]


def _expected_tool_calls(run: AgentRun) -> list[ToolCall]:
    expected: list[ToolCall] = []
    for index, tool_name in enumerate(expected_tool_names_for(run)):
        kwargs: dict = {"name": tool_name}
        if index < len(run.trace) and run.trace[index].tool_name == tool_name:
            step = run.trace[index]
            kwargs["input_parameters"] = step.arguments
            kwargs["output"] = step.observation
        expected.append(ToolCall(**kwargs))
    return expected


def _tool_call_payload(tool_call: ToolCall) -> dict:
    return {
        "name": tool_call.name,
        "input_parameters": tool_call.input_parameters,
        "output": tool_call.output,
    }


def _test_case(run: AgentRun) -> LLMTestCase:
    return LLMTestCase(
        input=run.input,
        actual_output=final_answer_text(run),
        expected_output=expected_blackbox_answer_for(run),
        tools_called=_tool_calls(run),
        expected_tools=_expected_tool_calls(run),
        metadata={"fixture": "repo_selection_v1"},
    )


def _eval_inputs(run: AgentRun, test_case: LLMTestCase) -> dict:
    trajectory_case = build_trajectory_test_case(run)
    return {
        "blackbox_g_eval": {
            "input": test_case.input,
            "actual_output": test_case.actual_output,
            "expected_output": test_case.expected_output,
            "criteria": blackbox_rubric_for(run).strip(),
            "evaluation_params": ["INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT"],
        },
        "tool_correctness": {
            "tools_called": [_tool_call_payload(tool) for tool in test_case.tools_called or []],
            "expected_tools": [_tool_call_payload(tool) for tool in test_case.expected_tools or []],
            "threshold": 1.0,
            "should_exact_match": True,
            "should_consider_ordering": True,
        },
        "trajectory_g_eval": {
            "input": trajectory_case.input,
            "actual_output": trajectory_case.actual_output,
            "expected_output": trajectory_case.expected_output,
            "criteria": TRAJECTORY_RUBRIC.strip(),
            "evaluation_params": ["INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT"],
        },
    }


def _metric_payload(metric, score: float) -> dict:
    return {
        "score": score,
        "success": bool(metric.success),
        "reason": getattr(metric, "reason", None),
        "threshold": getattr(metric, "threshold", None),
    }


TRAJECTORY_RUBRIC = """
Score whether the actual agent trajectory follows the expected golden path.
The judge should consider tool order, missing or extra tool calls, whether the
agent gathered evidence before answering, and whether the final answer is grounded
in tool observations. Return a low score for skipped required tools or unsupported
claims even if the final answer sounds plausible.
"""


def build_trajectory_test_case(run: AgentRun) -> LLMTestCase:
    return LLMTestCase(
        input=run.input,
        actual_output=(
            "Actual trajectory:\n"
            f"{trajectory_text(run)}\n\n"
            "Final answer:\n"
            f"{final_answer_text(run)}"
        ),
        expected_output=expected_trajectory_text_for(run),
        metadata={"fixture": run.metadata.get("fixture", "unknown")},
    )


def run(dry_run: bool, task: str, agent: str = "fixture") -> dict:
    agent_run = run_agent_by_name(agent, task)
    payload = base_payload("deepeval", "dry_run" if dry_run else "live_or_skip", agent_run.input, agent_run)
    payload["package_version"] = md.version("deepeval")

    test_case = _test_case(agent_run)
    payload["eval_inputs"] = _eval_inputs(agent_run, test_case)
    tool_metric = ToolCorrectnessMetric(
        threshold=1.0,
        model=NoopJudgeModel(),
        async_mode=False,
        include_reason=True,
        should_exact_match=True,
        should_consider_ordering=True,
    )
    tool_score = tool_metric.measure(
        test_case,
        _show_indicator=False,
        _log_metric_to_confident=False,
    )
    payload["results"]["tool_correctness"] = _metric_payload(tool_metric, tool_score)

    missing_reason = missing_live_judge_reason()
    if dry_run:
        missing_reason = "dry-run mode; live LLM-as-judge intentionally skipped."

    if missing_reason:
        payload["results"]["blackbox_g_eval"] = skipped_result(missing_reason)
        payload["results"]["trajectory_g_eval"] = skipped_result(missing_reason)
        return payload

    judge_config = resolve_judge_config()
    judge_model = CloudRuFMJudgeModel(judge_config)
    blackbox_metric = GEval(
        name="Blackbox Quality",
        criteria=blackbox_rubric_for(agent_run),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge_model,
        threshold=0.5,
        async_mode=False,
    )
    blackbox_score = blackbox_metric.measure(
        test_case,
        _show_indicator=False,
        _log_metric_to_confident=False,
    )
    payload["results"]["blackbox_g_eval"] = _metric_payload(blackbox_metric, blackbox_score)
    trajectory_metric = GEval(
        name="Golden Path Trajectory",
        criteria=TRAJECTORY_RUBRIC,
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge_model,
        threshold=0.5,
        async_mode=False,
    )
    trajectory_score = trajectory_metric.measure(
        build_trajectory_test_case(agent_run),
        _show_indicator=False,
        _log_metric_to_confident=False,
    )
    payload["results"]["trajectory_g_eval"] = _metric_payload(
        trajectory_metric,
        trajectory_score,
    )
    return payload


def main() -> None:
    args = parse_args("Run DeepEval benchmark.")
    payload = run(dry_run=args.dry_run, task=args.task, agent=args.agent)
    path = write_artifact("deepeval", payload)
    print(path)


if __name__ == "__main__":
    main()
