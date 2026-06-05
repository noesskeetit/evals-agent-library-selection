import json
import os
import subprocess
import sys

from evals_agent.calibration import CALIBRATION_CASES
from evals_agent.runners.run_deepseek_calibration import parse_judge_response, run


def test_parse_judge_response_accepts_plain_json_and_markdown_fence():
    plain = '{"pass": false, "score": 0.2, "reason": "bad trace", "evidence": ["missing step"]}'
    fenced = "```json\n{\"pass\": true, \"score\": 0.9, \"reason\": \"ok\", \"evidence\": []}\n```"

    assert parse_judge_response(plain)["pass"] is False
    assert parse_judge_response(fenced)["pass"] is True


def test_deepseek_calibration_dry_run_returns_skipped_summary():
    payload = run(dry_run=True)

    assert payload["library"] == "deepseek_judge_calibration"
    assert payload["mode"] == "dry_run"
    assert len(payload["cases"]) == len(CALIBRATION_CASES)
    assert payload["summary"]["status"] == "skipped"
    assert all(case["status"] == "skipped" for case in payload["cases"])


def test_deepseek_calibration_dry_run_writes_artifact(tmp_path):
    env = os.environ.copy()
    env["EVALS_ARTIFACT_DIR"] = str(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "evals_agent.runners.run_deepseek_calibration", "--dry-run"],
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    artifact_path = completed.stdout.strip().splitlines()[-1]
    with open(artifact_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["library"] == "deepseek_judge_calibration"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["status"] == "skipped"
