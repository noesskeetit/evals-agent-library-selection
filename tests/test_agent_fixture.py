from evals_agent.agent import run_agent


def test_agent_returns_recommendation_with_trace():
    result = run_agent("Need an eval library for trajectory and blackbox judge")

    assert result.final_answer.recommended_repo == "openevals"
    assert [step.tool_name for step in result.trace] == [
        "search_repos",
        "inspect_repo",
        "inspect_repo",
        "recommend_repo",
    ]
    assert result.final_answer.evidence
    assert "trajectory" in result.final_answer.rationale.lower()
