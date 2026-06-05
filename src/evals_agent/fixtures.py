from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoFixture:
    name: str
    url: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    community_score: int
    trajectory_score: int
    blackbox_score: int
    tracing_score: int


REPO_FIXTURES: tuple[RepoFixture, ...] = (
    RepoFixture(
        name="openevals",
        url="https://github.com/langchain-ai/openevals",
        strengths=(
            "native trajectory evaluators",
            "LLM-as-judge prompt customization",
            "LangSmith ecosystem fit",
        ),
        weaknesses=(
            "younger project",
            "smaller community than DeepEval",
            "OpenTelemetry path is via LangSmith, not the evaluator package itself",
        ),
        community_score=6,
        trajectory_score=10,
        blackbox_score=8,
        tracing_score=7,
    ),
    RepoFixture(
        name="deepeval",
        url="https://github.com/confident-ai/deepeval",
        strengths=(
            "large community",
            "many ready-made metrics",
            "agent tracing integrations",
        ),
        weaknesses=(
            "trajectory parity may require metric composition",
            "Confident AI platform is the most complete trace UI path",
            "heavier dependency surface",
        ),
        community_score=10,
        trajectory_score=8,
        blackbox_score=9,
        tracing_score=9,
    ),
)

DEFAULT_TASK = "Need an eval library for trajectory and blackbox judge"
