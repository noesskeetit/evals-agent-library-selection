import json

from evals_agent.agent import run_agent
from evals_agent.trace_schema import agent_run_to_dict


def test_agent_run_serializes_to_json_compatible_artifact():
    result = run_agent("Need an eval library for trajectory and blackbox judge")

    payload = agent_run_to_dict(result)

    assert set(payload) == {"input", "trace", "final_answer", "metadata"}
    assert payload["trace"][0]["tool_name"] == "search_repos"
    assert payload["final_answer"]["recommended_repo"] == "openevals"
    json.dumps(payload)
