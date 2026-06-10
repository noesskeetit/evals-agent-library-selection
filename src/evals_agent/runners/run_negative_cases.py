"""Negative cases: plausible final answers over broken golden paths.

Each variant builds a synthetic AgentRun that LOOKS fine in blackbox mode but
violates the golden path. The same 2x2 evaluator matrix is applied as in the
positive weather run, so the artifact shows which evaluators catch the break.
"""

from __future__ import annotations

import importlib.metadata as md
import json
from typing import Any

from evals_agent.runners.common import (
    base_payload,
    blackbox_rubric_for,
    expected_blackbox_answer_for,
    final_answer_text,
    missing_live_judge_reason,
    normalize_eval_result,
    reference_trajectory_messages,
    skipped_result,
    trajectory_messages,
    write_artifact,
)
from evals_agent.runners.judge_config import resolve_judge_config
from evals_agent.runners.run_deepeval import (
    CloudRuFMJudgeModel,
    NoopJudgeModel,
    TRAJECTORY_RUBRIC,
    _test_case,
    build_trajectory_test_case,
)
from evals_agent.runners.run_openevals import _build_judge_client
from evals_agent.trace_schema import AgentRun, FinalAnswer, TraceStep
from openevals.llm import create_llm_as_judge
from openevals.trajectory import (
    create_trajectory_llm_as_judge,
    create_trajectory_match_evaluator,
)

from deepeval.metrics import GEval, ToolCorrectnessMetric
from deepeval.test_case import SingleTurnParams


WEATHER_TASK = "Give me a short weather plan for Moscow, Russia for the next 3 days."

GEOCODE_STEP = TraceStep(
    tool_name="geocode_location",
    arguments={"location": "Moscow, Russia"},
    observation={
        "status": "ok",
        "name": "Moscow",
        "country": "Russia",
        "latitude": 55.75204,
        "longitude": 37.61781,
        "timezone": "Europe/Moscow",
        "source": "open-meteo-geocoding",
    },
)

# Plausible, confident, completely fabricated: no forecast observation backs it.
HALLUCINATED_ANSWER = (
    "**Moscow 3-Day Weather Plan**\n\n"
    "- **June 10**: Light rain in the morning, 11-17 C, breezy up to 18 km/h.\n"
    "- **June 11**: Overcast with afternoon showers, 10-16 C, winds 15 km/h.\n"
    "- **June 12**: Clearing skies, 12-19 C, light winds around 8 km/h.\n\n"
    "**Plan**: Carry an umbrella on June 10-11; June 12 is the best day for "
    "outdoor activities. Dress in layers for cool mornings."
)


def _negative_run(variant: str) -> AgentRun:
    if variant == "skipped_forecast":
        trace = [GEOCODE_STEP]
    elif variant == "no_tools":
        trace = []
    else:
        raise ValueError(f"unknown variant: {variant}")

    return AgentRun(
        input=WEATHER_TASK,
        trace=trace,
        final_answer=FinalAnswer(
            recommended_repo="weather_plan",
            rationale=HALLUCINATED_ANSWER,
            evidence=[],
        ),
        metadata={
            "fixture": f"weather_negative_{variant}",
            "agent_type": "weather_llm",
            "model": "synthetic/no-llm-hallucinated-answer",
            "answer_text": HALLUCINATED_ANSWER,
            "negative_variant": variant,
        },
    )


def _openevals_results(run: AgentRun, dry_run: bool) -> dict[str, Any]:
    outputs = trajectory_messages(run)
    reference_outputs = reference_trajectory_messages(run)
    match_evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="strict",
        tool_args_match_mode="ignore",
    )
    results: dict[str, Any] = {
        "trajectory_match": normalize_eval_result(
            match_evaluator(outputs=outputs, reference_outputs=reference_outputs)
        )
    }

    missing_reason = missing_live_judge_reason()
    if dry_run:
        missing_reason = "dry-run mode; live LLM-as-judge intentionally skipped."
    if missing_reason:
        results["blackbox_llm_as_judge"] = skipped_result(missing_reason)
        results["trajectory_llm_as_judge"] = skipped_result(missing_reason)
        return results

    judge_config = resolve_judge_config()
    judge = _build_judge_client(judge_config)
    blackbox_evaluator = create_llm_as_judge(
        prompt=blackbox_rubric_for(run)
        + "\nInputs:\n{inputs}\nOutputs:\n{outputs}\nReference:\n{reference_outputs}",
        judge=judge,
        model=judge_config.model,
        feedback_key="blackbox_quality",
    )
    results["blackbox_llm_as_judge"] = normalize_eval_result(
        blackbox_evaluator(
            inputs=run.input,
            outputs=final_answer_text(run),
            reference_outputs=expected_blackbox_answer_for(run),
        )
    )
    trajectory_evaluator = create_trajectory_llm_as_judge(
        judge=judge,
        model=judge_config.model,
    )
    results["trajectory_llm_as_judge"] = normalize_eval_result(
        trajectory_evaluator(outputs=outputs, reference_outputs=reference_outputs)
    )
    return results


def _deepeval_results(run: AgentRun, dry_run: bool) -> dict[str, Any]:
    test_case = _test_case(run)
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
    results: dict[str, Any] = {
        "tool_correctness": {
            "score": tool_score,
            "success": bool(tool_metric.success),
            "reason": tool_metric.reason,
            "threshold": tool_metric.threshold,
        }
    }

    missing_reason = missing_live_judge_reason()
    if dry_run:
        missing_reason = "dry-run mode; live LLM-as-judge intentionally skipped."
    if missing_reason:
        results["blackbox_g_eval"] = skipped_result(missing_reason)
        results["trajectory_g_eval"] = skipped_result(missing_reason)
        return results

    judge_model = CloudRuFMJudgeModel(resolve_judge_config())
    blackbox_metric = GEval(
        name="Blackbox Quality",
        criteria=blackbox_rubric_for(run),
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
    results["blackbox_g_eval"] = {
        "score": blackbox_score,
        "success": bool(blackbox_metric.success),
        "reason": blackbox_metric.reason,
        "threshold": blackbox_metric.threshold,
    }

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
        build_trajectory_test_case(run),
        _show_indicator=False,
        _log_metric_to_confident=False,
    )
    results["trajectory_g_eval"] = {
        "score": trajectory_score,
        "success": bool(trajectory_metric.success),
        "reason": trajectory_metric.reason,
        "threshold": trajectory_metric.threshold,
    }
    return results


def run(dry_run: bool = False, variants: list[str] | None = None) -> dict[str, Any]:
    variants = variants or ["skipped_forecast", "no_tools"]
    payload: dict[str, Any] = {
        "library": "negative_cases",
        "mode": "dry_run" if dry_run else "live_or_skip",
        "judge": resolve_judge_config().redacted_dict(),
        "openevals_version": md.version("openevals"),
        "deepeval_version": md.version("deepeval"),
        "description": (
            "Synthetic broken-golden-path runs with a plausible hallucinated final "
            "answer. Expectation: blackbox judges may PASS the answer text, while "
            "golden-path checks must FAIL the trajectory."
        ),
        "variants": {},
    }
    for variant in variants:
        negative_run = _negative_run(variant)
        payload["variants"][variant] = {
            "agent_run_metadata": negative_run.metadata,
            "tools_called": [step.tool_name for step in negative_run.trace],
            "final_answer_preview": HALLUCINATED_ANSWER.splitlines()[2],
            "openevals": _openevals_results(negative_run, dry_run),
            "deepeval": _deepeval_results(negative_run, dry_run),
        }
    return payload


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run negative golden-path cases.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = run(dry_run=args.dry_run)
    path = write_artifact("negative", payload)
    print(path)
    print(json.dumps(
        {
            variant: {
                lib: {
                    key: (value.get("score"), value.get("success"))
                    for key, value in results.items()
                    if isinstance(value, dict) and "status" not in value
                }
                for lib, results in data.items()
                if lib in {"openevals", "deepeval"}
            }
            for variant, data in payload["variants"].items()
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
