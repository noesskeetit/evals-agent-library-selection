# Eval Agents Library Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or equivalent disciplined step-by-step execution. This R&D plan intentionally separates live research, benchmark code, library runners, and final recommendation.

**Goal:** Produce a local evidence package comparing `openevals` and `DeepEval` for Eval Agents base path selection.

**Architecture:** Build a small deterministic tool-using agent, capture its trajectory, run equivalent blackbox and golden-path evaluations through both candidate libraries where possible, and record friction, gaps, and outputs. Keep live LLM credentials optional: unit tests must run without credentials; live judge runs execute only when compatible credentials are available.

**Tech Stack:** Python, pytest, `openevals`, `deepeval`, structured JSON artifacts, Markdown report.

---

## Files

- Create `pyproject.toml`: package metadata, pytest config, runtime/dev dependencies.
- Create `src/evals_agent/fixtures.py`: local repo fixture data and task cases.
- Create `src/evals_agent/trace_schema.py`: shared trace/result dataclasses and JSON helpers.
- Create `src/evals_agent/agent.py`: deterministic local tool-using agent.
- Create `src/evals_agent/runners/common.py`: artifact writing, env detection, rubric constants.
- Create `src/evals_agent/runners/run_openevals.py`: openevals blackbox and trajectory runner.
- Create `src/evals_agent/runners/run_deepeval.py`: DeepEval blackbox and trajectory/custom runner.
- Create `tests/test_agent_fixture.py`: agent behavior and trace tests.
- Create `tests/test_artifact_schema.py`: artifact serialization tests.
- Create `docs/eval-agents-library-selection-report.md`: final research and recommendation report.
- Write artifacts under `artifacts/openevals/`, `artifacts/deepeval/`, and `artifacts/comparison/`.

## Task 1: Live Research Snapshot

- [ ] **Step 1: Collect current source facts**

Run:

```bash
python3 --version
python3 -m pip --version
```

Expected: local Python and pip versions are visible.

- [ ] **Step 2: Research official docs and repositories**

Use live web sources for:

```text
https://github.com/langchain-ai/openevals
https://github.com/confident-ai/deepeval
https://github.com/langchain-ai/openevals#trajectory-llm-as-judge
https://github.com/langchain-ai/openevals#llm-as-judge
```

Expected: current community and API facts are captured with URLs.

- [ ] **Step 3: Save research notes**

Create `artifacts/comparison/research_snapshot.json` with at least:

```json
{
  "captured_at": "ISO-8601 timestamp",
  "libraries": {
    "openevals": {
      "repo": "https://github.com/langchain-ai/openevals",
      "community": {},
      "capabilities": {},
      "tracing": {}
    },
    "deepeval": {
      "repo": "https://github.com/confident-ai/deepeval",
      "community": {},
      "capabilities": {},
      "tracing": {}
    }
  }
}
```

## Task 2: Minimal Agent and Trace Contract

- [ ] **Step 1: Write failing tests**

Create tests that assert:

```python
from evals_agent.agent import run_agent


def test_agent_returns_recommendation_with_trace():
    result = run_agent("Нужна eval-библиотека для trajectory и blackbox judge")

    assert result.final_answer.recommended_repo == "openevals"
    assert [step.tool_name for step in result.trace] == [
        "search_repos",
        "inspect_repo",
        "inspect_repo",
        "recommend_repo",
    ]
    assert result.final_answer.evidence
```

Run:

```bash
python3 -m pytest tests/test_agent_fixture.py -q
```

Expected: fails because package and `run_agent` do not exist yet.

- [ ] **Step 2: Implement minimal package**

Create `fixtures.py`, `trace_schema.py`, and `agent.py` with deterministic data and the tool sequence above.

- [ ] **Step 3: Verify tests**

Run:

```bash
python3 -m pytest tests/test_agent_fixture.py -q
```

Expected: pass.

## Task 3: Artifact Schema

- [ ] **Step 1: Write failing serialization tests**

Create tests that assert agent results serialize to JSON-compatible dicts containing:

```text
input
trace
final_answer
metadata
```

Run:

```bash
python3 -m pytest tests/test_artifact_schema.py -q
```

Expected: fails until JSON helpers exist.

- [ ] **Step 2: Implement JSON helpers**

Add `to_dict` helpers in `trace_schema.py` and artifact writing helpers in `runners/common.py`.

- [ ] **Step 3: Verify tests**

Run:

```bash
python3 -m pytest tests/test_artifact_schema.py -q
```

Expected: pass.

## Task 4: Install and Inspect Candidate Libraries

- [ ] **Step 1: Create isolated environment**

Run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

Expected: `.venv` exists and pip upgrades successfully.

- [ ] **Step 2: Install dependencies**

Run:

```bash
.venv/bin/python -m pip install -e ".[dev,eval]"
```

Expected: `openevals`, `deepeval`, and pytest install into `.venv`.

- [ ] **Step 3: Inspect installed APIs**

Run:

```bash
.venv/bin/python - <<'PY'
import importlib.metadata as md
for package in ["openevals", "deepeval"]:
    print(package, md.version(package))
PY
```

Expected: package versions are printed.

## Task 5: OpenEvals Runner

- [ ] **Step 1: Write runner smoke test**

Create a test or direct command that verifies `src/evals_agent/runners/run_openevals.py --dry-run` writes a JSON artifact without external LLM credentials.

Run:

```bash
.venv/bin/python -m evals_agent.runners.run_openevals --dry-run
```

Expected: artifact appears in `artifacts/openevals/`.

- [ ] **Step 2: Implement OpenEvals runner**

The runner should:

```text
1. run the deterministic agent;
2. write raw trace artifact;
3. attempt blackbox LLM-as-judge when credentials are available;
4. attempt trajectory LLM-as-judge when credentials are available;
5. otherwise write a skipped_live_judge artifact with exact missing env reason.
```

- [ ] **Step 3: Run OpenEvals**

Run:

```bash
.venv/bin/python -m evals_agent.runners.run_openevals
```

Expected: successful artifact or explicit skipped-live artifact.

## Task 6: DeepEval Runner

- [ ] **Step 1: Write runner smoke test**

Create a test or direct command that verifies `src/evals_agent/runners/run_deepeval.py --dry-run` writes a JSON artifact without external LLM credentials.

Run:

```bash
.venv/bin/python -m evals_agent.runners.run_deepeval --dry-run
```

Expected: artifact appears in `artifacts/deepeval/`.

- [ ] **Step 2: Implement DeepEval runner**

The runner should:

```text
1. run the deterministic agent;
2. write raw trace artifact;
3. attempt blackbox metric when credentials are available;
4. attempt trajectory-like evaluation through the closest native or custom metric path;
5. otherwise write a skipped_live_judge artifact with exact missing env reason.
```

- [ ] **Step 3: Run DeepEval**

Run:

```bash
.venv/bin/python -m evals_agent.runners.run_deepeval
```

Expected: successful artifact or explicit skipped-live artifact.

## Task 7: Final Comparison Report

- [ ] **Step 1: Collect final evidence**

Run:

```bash
find artifacts -type f -maxdepth 3 | sort
.venv/bin/python -m pytest -q
```

Expected: artifacts exist and local tests pass.

- [ ] **Step 2: Write report**

Create `docs/eval-agents-library-selection-report.md` with:

```text
1. Executive recommendation.
2. Test setup.
3. OpenEvals results.
4. DeepEval results.
5. Criteria table.
6. OpenTelemetry/tracing conclusion.
7. Risks and required platform glue-code.
8. Reproducible commands.
9. .env and credentials note.
```

- [ ] **Step 3: Verify report has no unsupported claims**

Run:

```bash
rg -n "TBD|TODO|probably|should be|I think|не провер" docs/eval-agents-library-selection-report.md
```

Expected: no unsupported placeholder language except deliberate "не проверено live" notes if credentials are missing.
