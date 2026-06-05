from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceStep:
    tool_name: str
    arguments: dict[str, Any]
    observation: dict[str, Any]


@dataclass(frozen=True)
class FinalAnswer:
    recommended_repo: str
    rationale: str
    evidence: list[str]


@dataclass(frozen=True)
class AgentRun:
    input: str
    trace: list[TraceStep]
    final_answer: FinalAnswer
    metadata: dict[str, Any] = field(default_factory=dict)


def trace_step_to_dict(step: TraceStep) -> dict[str, Any]:
    return {
        "tool_name": step.tool_name,
        "arguments": step.arguments,
        "observation": step.observation,
    }


def final_answer_to_dict(answer: FinalAnswer) -> dict[str, Any]:
    return {
        "recommended_repo": answer.recommended_repo,
        "rationale": answer.rationale,
        "evidence": answer.evidence,
    }


def agent_run_to_dict(run: AgentRun) -> dict[str, Any]:
    return {
        "input": run.input,
        "trace": [trace_step_to_dict(step) for step in run.trace],
        "final_answer": final_answer_to_dict(run.final_answer),
        "metadata": run.metadata,
    }
