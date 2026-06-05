from __future__ import annotations

from .fixtures import REPO_FIXTURES
from .trace_schema import AgentRun, FinalAnswer, TraceStep


def _search_repos(query: str) -> dict[str, object]:
    matches = [
        {"name": repo.name, "url": repo.url}
        for repo in REPO_FIXTURES
        if "eval" in query.lower() or "judge" in query.lower()
    ]
    return {"matches": matches}


def _inspect_repo(name: str) -> dict[str, object]:
    for repo in REPO_FIXTURES:
        if repo.name == name:
            return {
                "name": repo.name,
                "strengths": list(repo.strengths),
                "weaknesses": list(repo.weaknesses),
                "scores": {
                    "community": repo.community_score,
                    "trajectory": repo.trajectory_score,
                    "blackbox": repo.blackbox_score,
                    "tracing": repo.tracing_score,
                },
            }
    raise ValueError(f"unknown repo: {name}")


def _recommend_repo(inspections: list[dict[str, object]]) -> dict[str, object]:
    def weighted_score(item: dict[str, object]) -> int:
        scores = item["scores"]
        assert isinstance(scores, dict)
        return int(scores["trajectory"]) * 4 + int(scores["blackbox"]) + int(scores["tracing"]) + int(scores["community"])

    selected = max(inspections, key=weighted_score)
    strengths = selected["strengths"]
    assert isinstance(strengths, list)
    return {
        "recommended_repo": selected["name"],
        "rationale": (
            "OpenEvals is the narrow fit when trajectory and blackbox judge support "
            "are weighted above community size because it has native trajectory evaluators."
        ),
        "evidence": [str(item) for item in strengths],
    }


def run_agent(task: str) -> AgentRun:
    trace: list[TraceStep] = []

    search_observation = _search_repos(task)
    trace.append(
        TraceStep(
            tool_name="search_repos",
            arguments={"query": task},
            observation=search_observation,
        )
    )

    inspections: list[dict[str, object]] = []
    for repo_name in ("openevals", "deepeval"):
        observation = _inspect_repo(repo_name)
        inspections.append(observation)
        trace.append(
            TraceStep(
                tool_name="inspect_repo",
                arguments={"name": repo_name},
                observation=observation,
            )
        )

    recommendation = _recommend_repo(inspections)
    trace.append(
        TraceStep(
            tool_name="recommend_repo",
            arguments={"candidates": [item["name"] for item in inspections]},
            observation=recommendation,
        )
    )

    return AgentRun(
        input=task,
        trace=trace,
        final_answer=FinalAnswer(
            recommended_repo=str(recommendation["recommended_repo"]),
            rationale=str(recommendation["rationale"]),
            evidence=list(recommendation["evidence"]),
        ),
        metadata={"fixture": "repo_selection_v1"},
    )
