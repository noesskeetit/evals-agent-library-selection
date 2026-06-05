from evals_agent.calibration import (
    CALIBRATION_CASES,
    build_calibration_prompt,
    score_calibration_results,
)


def test_calibration_cases_cover_success_and_failure_modes():
    case_ids = {case.case_id for case in CALIBRATION_CASES}

    assert len(CALIBRATION_CASES) >= 6
    assert "golden_path_passes" in case_ids
    assert "missing_recommend_step_fails" in case_ids
    assert "wrong_tool_order_fails" in case_ids
    assert "hallucinated_evidence_fails" in case_ids
    assert "wrong_recommendation_fails" in case_ids
    assert "empty_evidence_fails" in case_ids
    assert any(case.expected_pass for case in CALIBRATION_CASES)
    assert any(not case.expected_pass for case in CALIBRATION_CASES)


def test_calibration_prompt_requires_json_and_includes_expected_policy():
    case = CALIBRATION_CASES[0]

    prompt = build_calibration_prompt(case)

    assert "Return only valid JSON" in prompt
    assert '"pass": boolean' in prompt
    assert case.case_id in prompt
    assert case.expected_policy in prompt
    assert "agent_run" in prompt


def test_score_calibration_results_reports_accuracy_and_mismatches():
    results = [
        {"case_id": "a", "expected_pass": True, "judge_pass": True},
        {"case_id": "b", "expected_pass": False, "judge_pass": True},
        {"case_id": "c", "expected_pass": False, "judge_pass": False},
    ]

    summary = score_calibration_results(results)

    assert summary["total"] == 3
    assert summary["correct"] == 2
    assert summary["accuracy"] == 2 / 3
    assert summary["mismatches"] == [
        {"case_id": "b", "expected_pass": False, "judge_pass": True}
    ]
