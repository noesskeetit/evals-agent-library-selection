from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals_agent.runners.common import ROOT


def _latest_artifact(directory: Path) -> Path:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no JSON artifacts in {directory}")
    return files[-1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _tools_called(payload: dict[str, Any]) -> list[str]:
    return [step["tool_name"] for step in payload["agent_run"]["trace"]]


def _result(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload["results"][key]
    return {
        "score": value.get("score"),
        "success": value.get("success"),
        "comment": value.get("comment") or value.get("reason"),
        "threshold": value.get("threshold"),
        "raw_key": value.get("key"),
    }


def build_matrix(
    *,
    openevals_path: Path | None = None,
    deepeval_path: Path | None = None,
) -> dict[str, Any]:
    openevals_path = openevals_path or _latest_artifact(ROOT / "artifacts" / "openevals")
    deepeval_path = deepeval_path or _latest_artifact(ROOT / "artifacts" / "deepeval")

    openevals = _load(openevals_path)
    deepeval = _load(deepeval_path)
    agent_run = openevals["agent_run"]

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "task": "Eval Agents base path library selection; four-way test matrix on a live LLM weather agent.",
        "agent_under_test": {
            "type": agent_run["metadata"].get("agent_type"),
            "model": agent_run["metadata"].get("model"),
            "input": agent_run["input"],
            "tools_called": _tools_called(openevals),
            "internet_tools": [
                "Open-Meteo geocoding API",
                "Open-Meteo forecast API",
            ],
        },
        "judge": openevals["judge"],
        "commands": {
            "openevals": ".venv/bin/python -m evals_agent.runners.run_openevals --agent weather",
            "deepeval": ".venv/bin/python -m evals_agent.runners.run_deepeval --agent weather",
        },
        "artifacts": {
            "openevals": _rel(openevals_path),
            "deepeval": _rel(deepeval_path),
        },
        "variants": [
            {
                "variant": "openevals_golden_path_llm_as_judge",
                "library": "openevals",
                "result_key": "trajectory_llm_as_judge",
                **_result(openevals, "trajectory_llm_as_judge"),
                "supporting_check": _result(openevals, "trajectory_match"),
                "assessment": "Best native fit for reference trajectory checks; direct trajectory APIs are ergonomic.",
            },
            {
                "variant": "openevals_blackbox_llm_as_judge",
                "library": "openevals",
                "result_key": "blackbox_llm_as_judge",
                **_result(openevals, "blackbox_llm_as_judge"),
                "assessment": "Works after Cloud.ru JSON adapter; compact API for custom rubrics.",
            },
            {
                "variant": "deepeval_golden_path_llm_as_judge",
                "library": "deepeval",
                "result_key": "trajectory_g_eval",
                **_result(deepeval, "trajectory_g_eval"),
                "supporting_check": _result(deepeval, "tool_correctness"),
                "assessment": "Works, but requires composing GEval over serialized trajectory plus ToolCorrectness support.",
            },
            {
                "variant": "deepeval_blackbox_llm_as_judge",
                "library": "deepeval",
                "result_key": "blackbox_g_eval",
                **_result(deepeval, "blackbox_g_eval"),
                "assessment": "Works cleanly through GEval and custom Cloud.ru judge model.",
            },
        ],
        "selection": {
            "recommended_base_path": "DeepEval",
            "recommended_companion": "OpenEvals for native golden/reference trajectory cases",
            "tracing_assessment_mode": "doc_based_not_live_otel_export",
            "reason": (
                "DeepEval wins community, scenario breadth, and the documented tracing/OTel story; "
                "OpenEvals wins native golden-path trajectory ergonomics. Live OTEL export was not "
                "tested in this R&D pass."
            ),
        },
    }


def write_matrix(payload: dict[str, Any]) -> Path:
    directory = ROOT / "artifacts" / "comparison"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"eval_agents_weather_matrix_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a comparison matrix from fresh eval artifacts.")
    parser.add_argument("--openevals-artifact", type=Path)
    parser.add_argument("--deepeval-artifact", type=Path)
    args = parser.parse_args()

    payload = build_matrix(
        openevals_path=args.openevals_artifact,
        deepeval_path=args.deepeval_artifact,
    )
    print(write_matrix(payload))


if __name__ == "__main__":
    main()
