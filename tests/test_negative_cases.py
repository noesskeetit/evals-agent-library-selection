from evals_agent.runners.run_negative_cases import _negative_run, run


def test_negative_runs_have_broken_traces_but_plausible_answers():
    skipped = _negative_run("skipped_forecast")
    assert [step.tool_name for step in skipped.trace] == ["geocode_location"]
    assert "Weather Plan" in skipped.metadata["answer_text"]

    no_tools = _negative_run("no_tools")
    assert no_tools.trace == []


def test_negative_dry_run_fails_deterministic_golden_checks():
    payload = run(dry_run=True)

    for variant in ("skipped_forecast", "no_tools"):
        results = payload["variants"][variant]
        assert results["openevals"]["trajectory_match"]["score"] is False
        tool_correctness = results["deepeval"]["tool_correctness"]
        assert tool_correctness["score"] < 1.0
        assert tool_correctness["success"] is False
        assert results["openevals"]["blackbox_llm_as_judge"]["status"] == "skipped"
        assert results["deepeval"]["trajectory_g_eval"]["status"] == "skipped"
