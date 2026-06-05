# Eval Agents: сравнение OpenEvals и DeepEval

Дата среза: 2026-06-05 MSK.

Актуальный wiki-style итог под исходное ТЗ собран отдельно:
`docs/eval-agents-base-path-wiki-draft.md`.

## Executive recommendation

Рекомендация для base path платформы: **DeepEval**.

Причина: по заданному соотношению критериев DeepEval выигрывает у OpenEvals за счет community support, ширины eval-сценариев и более прямой tracing/OTel story. OpenEvals лучше как точечный adapter для нативного `trajectory LLM-as-judge` / `trajectory match`, но как базовая библиотека платформы выглядит уже и сильнее привязана к LangSmith/LangChain ecosystem.

Практичный вариант: взять **DeepEval как основной eval harness**, а **OpenEvals оставить совместимым дополнительным runner-ом** для golden-path trajectory cases, где нужен именно LangChain-style reference trajectory judge.

## Что было сделано

Собран локальный benchmark в `/Users/aogabbasov/evals`:

- deterministic tool-using agent: `src/evals_agent/agent.py`;
- общий trace/result contract: `src/evals_agent/trace_schema.py`;
- OpenEvals runner: `src/evals_agent/runners/run_openevals.py`;
- DeepEval runner: `src/evals_agent/runners/run_deepeval.py`;
- DeepSeek judge calibration runner: `src/evals_agent/runners/run_deepseek_calibration.py`;
- calibration cases: `src/evals_agent/calibration.py`;
- pytest smoke tests: `tests/`;
- research snapshot: `artifacts/comparison/research_snapshot.json`;
- runner artifacts:
  - dry/skipped artifacts: `artifacts/openevals/20260604T234212Z.json`, `artifacts/deepeval/20260604T234212Z.json`;
  - Cloud.ru FM live artifacts: `artifacts/openevals/20260605T001643Z.json`, `artifacts/deepeval/20260605T002045Z.json`;
  - DeepSeek judge calibration: `artifacts/deepseek_calibration/20260605T001910Z.json`.

`.env` не создавался и не изменялся. Runner-ы теперь умеют читать существующий `.env`; значения секретов не печатались, проверялось только `set/missing`.

## Тестовый сценарий

Локальный агент получает задачу:

```text
Need an eval library for trajectory and blackbox judge
```

Дальше он делает trace:

```text
search_repos -> inspect_repo(openevals) -> inspect_repo(deepeval) -> recommend_repo
```

Этот сценарий выбран потому, что он покрывает оба режима платформы:

- golden path: можно оценить tool trajectory;
- blackbox: можно оценить финальную рекомендацию.

Важно: в fixture агент специально выбирает `openevals`, потому что его локальная задача узко взвешивает native trajectory support выше community size. Это не равно финальной рекомендации по платформе.

## Live environment

Проверено локально:

```text
Python 3.12.13
openevals 0.2.0
deepeval 4.0.5
langsmith 0.8.9
opentelemetry-api 1.42.1
```

Cloud.ru FM credentials подхвачены из `.env`:

```text
FM_API_KEY=set
CLOUDRU_FM_API_KEY=missing
CLOUDRU_FM_BASE_URL=missing (использован default)
CLOUDRU_FM_MODEL=missing (использован default deepseek-ai/DeepSeek-V4-Pro)
CLOUDRU_FM_MAX_TOKENS=missing (использован default 50000)
CLOUDRU_FM_REASONING_EFFORT=missing (использован default high)
```

Live LLM-as-judge запускался через Cloud.ru Foundation Models / OpenAI-compatible API.
`foundation-models.api.cloud.ru` автоматически добавляется в process-local `no_proxy`/`NO_PROXY`, чтобы запросы не уходили через корпоративный proxy path.

## Cloud.ru FM judge integration

Runner-ы теперь по умолчанию используют Cloud.ru Foundation Models как OpenAI-compatible judge provider.

Default config:

```text
provider=cloudru_fm
base_url=https://foundation-models.api.cloud.ru/v1
model=deepseek-ai/DeepSeek-V4-Pro
max_tokens=50000
reasoning_effort=high
```

Env contract:

```bash
# Можно положить в .env:
FM_API_KEY="<cloud.ru foundation models key>"
CLOUDRU_FM_MODEL="deepseek-ai/DeepSeek-V4-Pro"
CLOUDRU_FM_MAX_TOKENS=50000
CLOUDRU_FM_REASONING_EFFORT=high
```

`FM_API_KEY` и `CLOUDRU_FM_API_KEY` оба поддержаны. `FM_API_KEY` имеет приоритет, чтобы не переименовывать существующий ключ.

Cloud.ru docs подтверждают:

- публичный API endpoint: `https://foundation-models.api.cloud.ru/v1/`;
- OpenAI SDK usage через `OpenAI(api_key=..., base_url=...)`;
- `max_tokens` как параметр chat completion;
- новые модели в каталоге: `zai-org/GLM-5.1`, `moonshotai/Kimi-K2.6`, `deepseek-ai/DeepSeek-V4-Pro`.

Live config в свежих artifacts:

```text
provider=cloudru_fm
api_key=set
base_url=https://foundation-models.api.cloud.ru/v1
model=deepseek-ai/DeepSeek-V4-Pro
max_tokens=50000
reasoning_effort=high
cloudru_host_in_no_proxy=true
```

## OpenEvals results

Команда:

```bash
.venv/bin/python -m evals_agent.runners.run_openevals
```

Артефакт: `artifacts/openevals/20260605T001643Z.json`.

Результат:

```text
trajectory_match: score=true
blackbox_llm_as_judge: score=true
trajectory_llm_as_judge: score=true
```

Live friction: OpenEvals через `ChatOpenAI.with_structured_output()` сначала получил от DeepSeek текстовый verdict вместо JSON. Root cause - Cloud.ru/DeepSeek не отработал в этом LangChain structured-output path так, как ожидал parser. Runner переведен на OpenEvals `ModelClient` path через OpenAI-compatible client adapter: adapter прокидывает `max_tokens=50000`, `reasoning_effort=high`, переводит `json_schema` в `json_object` и добавляет явную JSON-инструкцию в prompt.

Что понравилось:

- Нативный API для trajectory: `create_trajectory_match_evaluator`, `create_trajectory_llm_as_judge`.
- Хорошо ложится на reference trajectory: strict/unordered/subset/superset, tool args match modes.
- Blackbox judge простой: `create_llm_as_judge(prompt=..., model=...)`.
- API компактный и понятный для wrapper-а.

Что плохо для base path:

- Community меньше: 1,068 stars / 97 forks на срезе GitHub API.
- Проект моложе: создан 2025-02-08, latest PyPI `0.2.0`.
- OTel не выглядит функцией самого `openevals`; рабочий tracing path идет через LangSmith. У LangSmith есть отдельная OpenTelemetry evaluation story, но это уже соседняя платформа/SDK, а не evaluator package itself.

## DeepEval results

Команда:

```bash
.venv/bin/python -m evals_agent.runners.run_deepeval
```

Артефакт: `artifacts/deepeval/20260605T002045Z.json`.

Результат:

```text
ToolCorrectnessMetric: score=1.0, success=true
blackbox_g_eval: score=0.6, success=true
trajectory_like_llm_metrics: not_run
```

Комментарий по `blackbox_g_eval`: DeepSeek поставил проходной score, но справедливо снизил оценку за слабую доказательность финального ответа fixture-агента. Это полезный сигнал: judge не просто rubber-stamp-ит зеленый ответ, а штрафует за evidence quality.

Что понравилось:

- Существенно больше community: 15,920 stars / 1,491 forks.
- Более широкая матрица метрик: G-Eval, DAG, agentic metrics, RAG, multi-turn, MCP, multimodal, JSON correctness, prompt alignment.
- Есть agentic metrics: Task Completion, Tool Correctness, Goal Accuracy, Step Efficiency, Plan Adherence, Plan Quality, Tool Use, Argument Correctness.
- В пакете есть tracing layer и OTel-mode integrations: AgentCore, Strands, Google ADK через OpenInference, Pydantic AI; также native wrappers/callbacks для OpenAI, OpenAI Agents, LangChain/LangGraph, CrewAI, Anthropic и др.
- Практический smoke показал `ToolCorrectnessMetric` как близкий deterministic golden-path check для tool sequence.

Что плохо:

- Даже deterministic `ToolCorrectnessMetric` по умолчанию инициализирует judge model; без `OPENAI_API_KEY` пришлось передать custom `DeepEvalBaseLLM` no-op model. Это friction для offline unit tests.
- Нет такого же прямого "reference trajectory LLM-as-judge" one-liner, как в OpenEvals. Аналог собирается через agent metrics или custom metric composition.
- Самая полная trace UI / persistence story завязана на Confident AI platform.

## Criteria table

| Критерий | OpenEvals | DeepEval | Победитель |
|---|---:|---:|---|
| Community | 1,068 stars, 97 forks, PyPI 0.2.0, 60 releases | 15,920 stars, 1,491 forks, PyPI 4.0.5, 502 releases, PyPI recent downloads доступен | DeepEval |
| Гибкость сценариев | Силен в LLM-as-judge, code evals, trajectory match/judge, simulators | Шире: agentic, RAG, multi-turn, MCP, multimodal, custom metrics, prompt optimization | DeepEval |
| Golden path trajectory | Нативный trajectory match и trajectory LLM-as-judge | Есть tool/plan/task metrics, но parity требует композиции | OpenEvals |
| Blackbox LLM-as-judge | `create_llm_as_judge` | `GEval` / DAG / custom metrics | Ничья |
| OpenTelemetry/tracing | Через LangSmith path; не основной surface пакета | Tracing layer + OTel-mode integrations в пакете/экосистеме | DeepEval |
| Platform wrapper friction | Меньше кода для trajectory runner | Больше surface, больше зависимостей, но богаче платформа | Зависит от MVP |

## OpenTelemetry conclusion

Если требование формулируется строго как "интеграция с OpenTelemetry tracing из коробки", DeepEval выглядит сильнее.

Evidence:

- DeepEval README перечисляет tracing/evaluation integrations для OpenAI, OpenAI Agents, LangChain, LangGraph, Pydantic AI, CrewAI, Anthropic и др.
- Installed DeepEval package содержит OTel integration notes: `deepeval/integrations/README.md` описывает OTel-mode integrations и routing через OTLP/REST.
- LangSmith умеет evaluation over OpenTelemetry traces, но для OpenEvals это внешний LangSmith workflow. Сам `openevals` в installed package выглядит как evaluator function library, а не OTel tracing harness.

## DeepSeek judge calibration

Команда:

```bash
.venv/bin/python -m evals_agent.runners.run_deepseek_calibration
```

Артефакт: `artifacts/deepseek_calibration/20260605T001910Z.json`.

Calibration set:

```text
golden_path_passes: expected=true, judge=true
missing_recommend_step_fails: expected=false, judge=false
wrong_tool_order_fails: expected=false, judge=false
hallucinated_evidence_fails: expected=false, judge=false
wrong_recommendation_fails: expected=false, judge=false
empty_evidence_fails: expected=false, judge=false
```

Summary:

```text
total=6
correct=6
accuracy=1.0
mismatches=[]
```

Вывод: `deepseek-ai/DeepSeek-V4-Pro` в текущей Cloud.ru FM конфигурации годится как default judge для этого MVP: он ловит missing tool step, неправильный порядок tool calls, hallucinated evidence, unsupported recommendation и отсутствие evidence. Следующий шаг перед production - расширить calibration set до 20-30 кейсов и прогнать variance: минимум 3 повтора на кейс.

## Риски и ограничения

- Live LLM-as-judge подтвержден через Cloud.ru FM API, но только на MVP fixture и calibration set из 6 кейсов.
- Итог по community основан на GitHub/PyPI snapshot на 2026-06-05; эти цифры быстро меняются.
- OpenEvals может быть лучшим выбором, если platform MVP на 80% состоит из reference trajectory judge и уже сидит на LangSmith/LangGraph.
- DeepEval потребует adapter policy: какие agent metrics считаем golden-path, как маппить platform trace в `LLMTestCase`, `ToolCall`, trace spans и expected tools.
- Для offline CI с DeepEval нужно явно передавать custom local model или отделять deterministic metrics от LLM metrics.
- OpenEvals + Cloud.ru DeepSeek потребовал adapter для structured JSON output. Это не блокер, но это обязательный glue-code для платформенного wrapper-а.

## Reproducible commands

```bash
cd /Users/aogabbasov/evals
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,eval]"
export FM_API_KEY="<cloud.ru foundation models key>"
.venv/bin/python -m pytest -q
.venv/bin/python -m evals_agent.runners.run_openevals
.venv/bin/python -m evals_agent.runners.run_deepeval
.venv/bin/python -m evals_agent.runners.run_deepseek_calibration
```

## Source links

- OpenEvals GitHub: https://github.com/langchain-ai/openevals
- OpenEvals README raw: https://raw.githubusercontent.com/langchain-ai/openevals/main/README.md
- DeepEval GitHub: https://github.com/confident-ai/deepeval
- DeepEval README raw: https://raw.githubusercontent.com/confident-ai/deepeval/main/README.md
- LangSmith OpenTelemetry evaluation docs: https://docs.langchain.com/langsmith/evaluate-with-opentelemetry
- DeepEval tracing docs: https://deepeval.com/docs/evaluation-llm-tracing
- Cloud.ru Foundation Models API reference: https://cloud.ru/docs/foundation-models/ug/topics/api-ref
- Cloud.ru Foundation Models quickstart: https://cloud.ru/docs/foundation-models/ug/topics/quickstart
- Cloud.ru Foundation Models catalog: https://cloud.ru/products/evolution-ai-factory/catalog-foundation-models
