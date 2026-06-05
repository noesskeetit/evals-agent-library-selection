from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from evals_agent.agent import run_agent
from evals_agent.fixtures import DEFAULT_TASK
from evals_agent.trace_schema import (
    AgentRun,
    FinalAnswer,
    TraceStep,
    agent_run_to_dict,
)


EXPECTED_POLICY = (
    "Pass only if the agent run has a coherent golden-path trajectory, uses the "
    "expected tools in a defensible order, and the final answer is grounded in "
    "trace evidence. Fail runs with missing tool steps, wrong tool order, "
    "hallucinated evidence, unsupported recommendations, or empty evidence."
)


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    title: str
    expected_pass: bool
    expected_policy: str
    agent_run: AgentRun
    defect: str | None = None


def _base_run() -> AgentRun:
    return run_agent(DEFAULT_TASK)


def _with_trace(run: AgentRun, trace: list[TraceStep]) -> AgentRun:
    return AgentRun(
        input=run.input,
        trace=trace,
        final_answer=run.final_answer,
        metadata={**run.metadata, "calibration_mutation": "trace"},
    )


def _with_answer(run: AgentRun, answer: FinalAnswer, mutation: str) -> AgentRun:
    return AgentRun(
        input=run.input,
        trace=run.trace,
        final_answer=answer,
        metadata={**run.metadata, "calibration_mutation": mutation},
    )


def _build_cases() -> tuple[CalibrationCase, ...]:
    run = _base_run()

    missing_recommend_step = _with_trace(run, run.trace[:-1])
    wrong_tool_order = _with_trace(run, [run.trace[1], run.trace[0], *run.trace[2:]])
    hallucinated_evidence = _with_answer(
        run,
        FinalAnswer(
            recommended_repo=run.final_answer.recommended_repo,
            rationale=run.final_answer.rationale,
            evidence=[
                *run.final_answer.evidence,
                "native OpenTelemetry tracing is provided by the evaluator package itself",
            ],
        ),
        "hallucinated_evidence",
    )
    wrong_recommendation = _with_answer(
        run,
        FinalAnswer(
            recommended_repo="deepeval",
            rationale=(
                "DeepEval is recommended because it has native trajectory evaluators, "
                "even though that is not supported by the trace evidence."
            ),
            evidence=run.final_answer.evidence,
        ),
        "wrong_recommendation",
    )
    empty_evidence = _with_answer(
        run,
        FinalAnswer(
            recommended_repo=run.final_answer.recommended_repo,
            rationale=run.final_answer.rationale,
            evidence=[],
        ),
        "empty_evidence",
    )

    return (
        CalibrationCase(
            case_id="golden_path_passes",
            title="Golden path trace and grounded final answer",
            expected_pass=True,
            expected_policy=EXPECTED_POLICY,
            agent_run=run,
        ),
        CalibrationCase(
            case_id="missing_recommend_step_fails",
            title="Trajectory is missing final recommendation tool step",
            expected_pass=False,
            expected_policy=EXPECTED_POLICY,
            agent_run=missing_recommend_step,
            defect="Missing recommend_repo tool call in the trajectory.",
        ),
        CalibrationCase(
            case_id="wrong_tool_order_fails",
            title="Trajectory starts with inspect before search",
            expected_pass=False,
            expected_policy=EXPECTED_POLICY,
            agent_run=wrong_tool_order,
            defect="Tool calls are in an incoherent order.",
        ),
        CalibrationCase(
            case_id="hallucinated_evidence_fails",
            title="Final answer adds evidence not present in trace",
            expected_pass=False,
            expected_policy=EXPECTED_POLICY,
            agent_run=hallucinated_evidence,
            defect="Final answer cites unsupported OpenTelemetry evidence.",
        ),
        CalibrationCase(
            case_id="wrong_recommendation_fails",
            title="Final answer recommends the wrong library for stated rationale",
            expected_pass=False,
            expected_policy=EXPECTED_POLICY,
            agent_run=wrong_recommendation,
            defect="Recommendation contradicts trace evidence.",
        ),
        CalibrationCase(
            case_id="empty_evidence_fails",
            title="Final answer contains no evidence",
            expected_pass=False,
            expected_policy=EXPECTED_POLICY,
            agent_run=empty_evidence,
            defect="Final answer has no supporting evidence.",
        ),
    )


CALIBRATION_CASES = _build_cases()


def build_calibration_prompt(case: CalibrationCase) -> str:
    payload = {
        "case_id": case.case_id,
        "title": case.title,
        "expected_policy": case.expected_policy,
        "defect_hint_for_calibration": case.defect,
        "agent_run": agent_run_to_dict(case.agent_run),
    }
    return (
        "You are calibrating an LLM-as-judge for agent evaluation.\n"
        "Return only valid JSON with this schema:\n"
        '{"pass": boolean, "score": number, "reason": string, "evidence": [string]}\n'
        "Apply the expected policy strictly. Do not reward plausible but unsupported claims.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def score_calibration_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = [
        {
            "case_id": str(result["case_id"]),
            "expected_pass": bool(result["expected_pass"]),
            "judge_pass": bool(result["judge_pass"]),
        }
        for result in results
        if bool(result["expected_pass"]) != bool(result["judge_pass"])
    ]
    total = len(results)
    correct = total - len(mismatches)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "mismatches": mismatches,
    }
