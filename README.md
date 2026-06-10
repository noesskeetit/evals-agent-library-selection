# Eval Agents Library Selection

Local R&D package for choosing an eval base path for agent evaluation.

Final wiki-style draft:

```text
docs/eval-agents-base-path-wiki-draft.md
```

Short teamlead version:

```text
docs/eval-agents-base-path-teamlead.md
```

Main live matrix artifact:

```text
artifacts/comparison/eval_agents_weather_matrix_20260610T072414Z.json
```

Negative cases (plausible hallucinated answer over a broken golden path):

```text
artifacts/negative/20260610T072334Z.json
```

Reproduce:

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

Live LLM runs require a local `.env` with `FM_API_KEY`. Secrets are not committed.
