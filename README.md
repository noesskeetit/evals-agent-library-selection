# Eval Agents Library Selection

R&D repo for choosing the base eval library for agent evaluation.

## Decision

**Base path: DeepEval-only.**

OpenEvals is not required as a platform dependency. It has a more native Golden Path trajectory API, but DeepEval covers the same required scenarios through `ToolCorrectnessMetric` and `GEval` over serialized traces.

## Documents

| Document | Purpose |
|---|---|
| `docs/eval-agents-base-path-teamlead.md` | Short wiki-ready summary for review/decision. |
| `docs/eval-agents-base-path-teamlead-confluence.md` | Same short article in Confluence-friendly Markdown. |
| `docs/eval-agents-base-path-wiki-draft.md` | Full technical research note with details and evidence. |

## Key Artifacts

| Artifact | Purpose |
|---|---|
| `artifacts/comparison/eval_agents_weather_matrix_20260610T072414Z.json` | Main 2x2 live eval matrix. |
| `artifacts/negative/20260610T072334Z.json` | Negative cases for broken Golden Path. |
| `artifacts/openevals/20260610T071859Z.json` | Fresh OpenEvals live run. |
| `artifacts/deepeval/20260610T071951Z.json` | Fresh DeepEval live run. |
| `artifacts/comparison/research_snapshot.json` | GitHub/PyPI/community snapshot. |

## Code Map

| Path | Purpose |
|---|---|
| `src/evals_agent/llm_weather_agent.py` | LLM-powered weather agent on Kimi K2.6. |
| `src/evals_agent/weather_tools.py` | Open-Meteo tools. |
| `src/evals_agent/runners/run_deepeval.py` | DeepEval runner. |
| `src/evals_agent/runners/run_openevals.py` | OpenEvals runner used for comparison. |
| `src/evals_agent/runners/run_negative_cases.py` | Negative case runner. |
| `src/evals_agent/runners/build_comparison.py` | Builds the 2x2 comparison matrix. |

## Reproduce

Live LLM runs require a local `.env` with `FM_API_KEY`. Secrets are ignored and not committed.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,eval]"
.venv/bin/python -m pytest -q
.venv/bin/python -m evals_agent.runners.run_openevals --agent weather
.venv/bin/python -m evals_agent.runners.run_deepeval --agent weather
.venv/bin/python -m evals_agent.runners.run_negative_cases
.venv/bin/python -m evals_agent.runners.collect_research_snapshot
.venv/bin/python -m evals_agent.runners.build_comparison
```

## Verification

```bash
.venv/bin/python -m pytest -q
```
