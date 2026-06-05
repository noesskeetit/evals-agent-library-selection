from __future__ import annotations

import argparse
import json
from typing import Any

from openai import OpenAI

from evals_agent.calibration import (
    CALIBRATION_CASES,
    build_calibration_prompt,
    score_calibration_results,
)
from evals_agent.runners.common import env_status, missing_live_judge_reason, utc_now, write_artifact
from evals_agent.runners.judge_config import JudgeConfig, resolve_judge_config
from evals_agent.trace_schema import agent_run_to_dict


def parse_judge_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            stripped = stripped[start : end + 1]

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("judge response must be a JSON object")
    return parsed


def _request_kwargs(config: JudgeConfig, prompt: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
    }
    if config.reasoning_effort:
        kwargs["reasoning_effort"] = config.reasoning_effort
    return kwargs


def _evaluate_case(client: OpenAI, config: JudgeConfig, prompt: str) -> dict[str, Any]:
    response = client.chat.completions.create(**_request_kwargs(config, prompt))
    content = response.choices[0].message.content or ""
    parsed = parse_judge_response(content)
    return {
        "raw": content,
        "pass": bool(parsed.get("pass")),
        "score": parsed.get("score"),
        "reason": parsed.get("reason"),
        "evidence": parsed.get("evidence", []),
    }


def run(dry_run: bool) -> dict[str, Any]:
    config = resolve_judge_config()
    payload: dict[str, Any] = {
        "library": "deepseek_judge_calibration",
        "mode": "dry_run" if dry_run else "live_or_skip",
        "captured_at": utc_now(),
        "env": env_status(),
        "judge": config.redacted_dict(),
        "cases": [],
        "summary": {},
    }

    missing_reason = missing_live_judge_reason()
    if dry_run:
        missing_reason = "dry-run mode; live DeepSeek judge calibration intentionally skipped."

    if missing_reason:
        payload["cases"] = [
            {
                "case_id": case.case_id,
                "title": case.title,
                "status": "skipped",
                "reason": missing_reason,
                "expected_pass": case.expected_pass,
                "defect": case.defect,
                "agent_run": agent_run_to_dict(case.agent_run),
            }
            for case in CALIBRATION_CASES
        ]
        payload["summary"] = {"status": "skipped", "reason": missing_reason}
        return payload

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    scored_results: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    for case in CALIBRATION_CASES:
        prompt = build_calibration_prompt(case)
        case_payload: dict[str, Any] = {
            "case_id": case.case_id,
            "title": case.title,
            "status": "evaluated",
            "expected_pass": case.expected_pass,
            "defect": case.defect,
            "agent_run": agent_run_to_dict(case.agent_run),
        }
        try:
            judged = _evaluate_case(client, config, prompt)
        except Exception as exc:  # pragma: no cover - exercised by live runs
            case_payload.update(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            cases.append(case_payload)
            continue

        judge_pass = bool(judged["pass"])
        case_payload["judge"] = judged
        case_payload["judge_pass"] = judge_pass
        cases.append(case_payload)
        scored_results.append(
            {
                "case_id": case.case_id,
                "expected_pass": case.expected_pass,
                "judge_pass": judge_pass,
            }
        )

    payload["cases"] = cases
    if scored_results:
        summary = score_calibration_results(scored_results)
        summary["status"] = "completed" if len(scored_results) == len(CALIBRATION_CASES) else "partial"
        summary["target_accuracy"] = 1.0
        payload["summary"] = summary
    else:
        payload["summary"] = {"status": "error", "reason": "No calibration case was evaluated."}
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepSeek judge calibration.")
    parser.add_argument("--dry-run", action="store_true", help="Skip live DeepSeek judge calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run(dry_run=args.dry_run)
    path = write_artifact("deepseek_calibration", payload)
    print(path)


if __name__ == "__main__":
    main()
