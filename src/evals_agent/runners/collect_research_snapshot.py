from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals_agent.runners.common import ROOT


GITHUB_API = "https://api.github.com"
PYPI_API = "https://pypi.org/pypi"


def _fetch_json(url: str) -> dict[str, Any] | list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "evals-agent-library-selection/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _github_repo(owner_repo: str) -> dict[str, Any]:
    repo = _fetch_json(f"{GITHUB_API}/repos/{owner_repo}")
    releases = _fetch_json(f"{GITHUB_API}/repos/{owner_repo}/releases?per_page=5")
    commits = _fetch_json(f"{GITHUB_API}/repos/{owner_repo}/commits?per_page=5")
    contributors = _fetch_json(f"{GITHUB_API}/repos/{owner_repo}/contributors?per_page=5")
    assert isinstance(repo, dict)
    assert isinstance(releases, list)
    assert isinstance(commits, list)
    assert isinstance(contributors, list)
    return {
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "watchers": repo.get("subscribers_count"),
        "open_issues_and_prs": repo.get("open_issues_count"),
        "default_branch": repo.get("default_branch"),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "latest_releases": [
            {
                "tag_name": release.get("tag_name"),
                "name": release.get("name"),
                "published_at": release.get("published_at"),
                "prerelease": release.get("prerelease"),
            }
            for release in releases
        ],
        "latest_commits": [
            {
                "sha": commit.get("sha", "")[:12],
                "date": (commit.get("commit") or {}).get("author", {}).get("date"),
                "message": (commit.get("commit") or {}).get("message"),
                "author_login": (commit.get("author") or {}).get("login"),
            }
            for commit in commits
        ],
        "top_contributors_sample": [
            {
                "login": contributor.get("login"),
                "contributions": contributor.get("contributions"),
            }
            for contributor in contributors
        ],
    }


def _pypi(project: str) -> dict[str, Any]:
    payload = _fetch_json(f"{PYPI_API}/{project}/json")
    assert isinstance(payload, dict)
    info = payload.get("info") or {}
    releases = payload.get("releases") or {}
    latest_files = releases.get(info.get("version"), [])
    latest_upload_time = None
    if latest_files:
        latest_upload_time = latest_files[-1].get("upload_time_iso_8601")
    return {
        "version": info.get("version"),
        "summary": info.get("summary"),
        "requires_python": info.get("requires_python"),
        "project_urls": info.get("project_urls"),
        "latest_upload_time": latest_upload_time,
        "release_count": len(releases),
    }


def collect_snapshot() -> dict[str, Any]:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "openevals_repo": "https://github.com/langchain-ai/openevals",
            "openevals_readme_raw": "https://raw.githubusercontent.com/langchain-ai/openevals/main/README.md",
            "deepeval_repo": "https://github.com/confident-ai/deepeval",
            "deepeval_readme_raw": "https://raw.githubusercontent.com/confident-ai/deepeval/main/README.md",
            "deepeval_tracing_docs": "https://deepeval.com/docs/evaluation-llm-tracing",
            "deepeval_agent_tracing_docs": "https://deepeval.com/guides/guides-tracing-ai-agents",
            "langsmith_otel_docs": "https://docs.langchain.com/langsmith/trace-with-opentelemetry",
            "langsmith_evaluate_otel_docs": "https://docs.langchain.com/langsmith/evaluate-with-opentelemetry",
        },
        "libraries": {
            "openevals": {
                "github": _github_repo("langchain-ai/openevals"),
                "pypi": _pypi("openevals"),
                "capability_notes": {
                    "blackbox_llm_as_judge": "README documents create_llm_as_judge with custom prompts, scoring, models, and structured output.",
                    "trajectory_eval": "README documents trajectory match modes, tool args match modes, and trajectory LLM-as-judge.",
                    "tracing": "OpenEvals is primarily evaluator functions; LangSmith provides the OpenTelemetry trace ingestion/evaluation path in the same ecosystem.",
                },
            },
            "deepeval": {
                "github": _github_repo("confident-ai/deepeval"),
                "pypi": _pypi("deepeval"),
                "capability_notes": {
                    "blackbox_llm_as_judge": "GEval over LLMTestCase is the natural blackbox route.",
                    "trajectory_eval": "Agent trajectory support is available through agentic metrics and composition such as ToolCorrectness plus GEval over serialized traces.",
                    "tracing": "Docs include deepeval.tracing observe/update_current_trace/update_current_span and Confident AI tracing/OTEL routes.",
                },
            },
        },
    }


def write_snapshot(payload: dict[str, Any]) -> Path:
    directory = ROOT / "artifacts" / "comparison"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "research_snapshot.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    print(write_snapshot(collect_snapshot()))


if __name__ == "__main__":
    main()
