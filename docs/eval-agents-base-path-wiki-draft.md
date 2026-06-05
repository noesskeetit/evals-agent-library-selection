# Eval Agents: выбор base path для eval-библиотеки

Дата среза: 2026-06-05.

## Краткий вывод

Рекомендация: **DeepEval как base path платформы**.

Причина: DeepEval выигрывает по соотношению критериев из ТЗ:

- заметно сильнее community support;
- шире набор eval-сценариев;
- лучше выглядит история с tracing / OpenTelemetry / agent integrations.

При этом **OpenEvals стоит оставить как дополнительный runner** для golden-path trajectory кейсов, потому что у него самый прямой API для reference trajectory:

```python
create_trajectory_match_evaluator(...)
create_trajectory_llm_as_judge(...)
```

Итоговая practical-схема:

```text
Base path: DeepEval
Companion runner: OpenEvals для golden/reference trajectory
Agent under test: Kimi K2.6 weather agent
Judge model: DeepSeek V4 Pro через Cloud.ru FM API
```

## Что оценивали

Библиотеки:

| Библиотека | Репозиторий |
|---|---|
| OpenEvals | https://github.com/langchain-ai/openevals |
| DeepEval | https://github.com/confident-ai/deepeval |

Оценивали 4 варианта из ТЗ:

| Вариант | Библиотека | Что проверяет |
|---|---|---|
| Golden Path with LLM as Judge | OpenEvals | Trace агента относительно expected trajectory |
| Blackbox LLM as Judge | OpenEvals | Финальный ответ агента |
| Golden Path with LLM as Judge | DeepEval | Trace агента через GEval + ToolCorrectness |
| Blackbox LLM as Judge | DeepEval | Финальный ответ агента через GEval |

## Агент для тестирования

Чтобы тест был ближе к реальному агенту, был сделан LLM-powered погодный агент:

```text
Мозг агента: moonshotai/Kimi-K2.6
Интернет tool: Open-Meteo Geocoding API
Интернет tool: Open-Meteo Forecast API
Judge: deepseek-ai/DeepSeek-V4-Pro
```

Задача агенту:

```text
Give me a short weather plan for Moscow, Russia for the next 3 days.
```

Фактический trace:

```text
geocode_location
get_weather_forecast
```

Код агента:

- `src/evals_agent/llm_weather_agent.py`
- `src/evals_agent/weather_tools.py`

Почему такой агент подходит:

- внутри реально есть LLM decision loop;
- агент сам вызывает tools;
- tools ходят в интернет;
- trace короткий и понятный;
- blackbox output легко оценить;
- golden path очевиден: сначала geocoding, потом forecast.

## Артефакты тестирования

Единый summary:

```text
artifacts/comparison/eval_agents_weather_matrix_20260605T020938Z.json
```

Live artifacts:

```text
artifacts/openevals/20260605T020838Z.json
artifacts/deepeval/20260605T020938Z.json
```

Проверка тестов:

```text
24 passed
```

## Результаты 4 вариантов

| Вариант | Библиотека | Результат | Комментарий |
|---|---|---:|---|
| Golden Path with LLM as Judge | OpenEvals | pass | Нативно и удобно: direct trajectory evaluator, expected path `geocode_location -> get_weather_forecast`, judge подтвердил корректность trajectory. |
| Blackbox LLM as Judge | OpenEvals | pass | Работает через `create_llm_as_judge`; для Cloud.ru DeepSeek потребовался небольшой adapter для JSON output. |
| Golden Path with LLM as Judge | DeepEval | pass | Работает, но не как one-liner: golden path пришлось собрать через serialized trajectory + `GEval`, а `ToolCorrectnessMetric` использовать как supporting deterministic check. |
| Blackbox LLM as Judge | DeepEval | pass | Работает чисто через `GEval`; хороший fit для rubric-based answer quality checks. |

## OpenEvals: оценка

Что хорошо:

- лучший fit для golden/reference trajectory;
- есть готовый `create_trajectory_llm_as_judge`;
- есть deterministic trajectory match modes;
- компактный API, мало glue-code для trajectory cases.

Что плохо:

- community сильно меньше DeepEval;
- tracing/OpenTelemetry story идет через LangSmith ecosystem, а не выглядит core-функцией самого package;
- для Cloud.ru DeepSeek потребовался adapter structured JSON output.

Оценка: **очень хорошо для golden path, не лучший base path для всей платформы**.

## DeepEval: оценка

Что хорошо:

- популярнее и взрослее;
- шире матрица сценариев: G-Eval, DAG, RAG, agentic metrics, multi-turn, MCP, multimodal, custom metrics;
- лучше выглядит tracing / agent integrations story;
- blackbox eval через `GEval` лег простой;
- golden path можно выразить через composition.

Что плохо:

- reference trajectory LLM-as-judge не такой прямой, как в OpenEvals;
- для golden path нужен glue-code: сериализация trace, custom GEval rubric, supporting ToolCorrectness;
- больше dependency/platform surface.

Оценка: **лучший base path, но golden path wrapper надо написать самим**.

## Community support

GitHub API snapshot на 2026-06-05:

| Библиотека | Stars | Forks | Последний push |
|---|---:|---:|---|
| OpenEvals | 1,068 | 97 | 2026-06-03 |
| DeepEval | 15,920 | 1,491 | 2026-06-04 |

Вывод: **DeepEval выигрывает community support с большим отрывом**.

## Гибкость eval-сценариев

OpenEvals:

- LLM-as-judge;
- trajectory match;
- trajectory LLM-as-judge;
- code evals;
- compact custom evaluators.

DeepEval:

- G-Eval;
- DAG metrics;
- RAG metrics;
- agentic metrics;
- multi-turn;
- MCP;
- multimodal;
- prompt / answer quality;
- custom metrics;
- tracing integrations.

Вывод: **DeepEval гибче как platform base**.

## OpenTelemetry / tracing

OpenEvals:

- сам package выглядит как evaluator function library;
- tracing/evaluation story в основном через LangSmith;
- LangSmith умеет OpenTelemetry ingestion/evaluation, но это соседняя платформа.

DeepEval:

- имеет tracing layer и agent integrations;
- в документации и package surface видны OpenTelemetry / OpenInference-style integrations;
- лучше подходит как base для платформы, где eval и traces должны жить рядом.

Вывод: **DeepEval сильнее по tracing / OTel story**.

## Итоговая рекомендация

Выбрать:

```text
DeepEval как base path
OpenEvals как companion runner для golden path trajectory
DeepSeek V4 Pro как default judge
Kimi K2.6 можно использовать как модель агента в тестах
```

Почему не OpenEvals как base:

```text
OpenEvals лучше по одному важному сценарию: native golden trajectory.
Но DeepEval выигрывает по сумме критериев: community + flexibility + tracing.
```

Что нужно сделать в платформе:

1. Ввести общий platform eval contract:

```text
input
actual_output
actual_trace
expected_output
expected_trace
rubric
metadata
```

2. Реализовать DeepEval adapter:

```text
Blackbox -> GEval
Golden path -> ToolCorrectness + custom GEval over serialized trace
```

3. Оставить OpenEvals adapter:

```text
Golden path -> create_trajectory_llm_as_judge
Trajectory match -> create_trajectory_match_evaluator
```

4. Хранить artifacts в едином формате, как в:

```text
artifacts/comparison/eval_agents_weather_matrix_20260605T020938Z.json
```

## Команды воспроизведения

```bash
cd /Users/aogabbasov/evals
.venv/bin/python -m pytest -q
.venv/bin/python -m evals_agent.runners.run_openevals --agent weather
.venv/bin/python -m evals_agent.runners.run_deepeval --agent weather
```

Для live-режима нужен `.env`:

```text
FM_API_KEY=<cloud.ru foundation models key>
```

Секреты в отчет и artifacts не печатаются; в artifacts только `api_key=set/missing`.

## Source links

- OpenEvals: https://github.com/langchain-ai/openevals
- OpenEvals LLM-as-judge: https://github.com/langchain-ai/openevals#llm-as-judge
- OpenEvals trajectory LLM-as-judge: https://github.com/langchain-ai/openevals#trajectory-llm-as-judge
- DeepEval: https://github.com/confident-ai/deepeval
- DeepEval docs: https://deepeval.com/docs
- DeepEval tracing docs: https://deepeval.com/docs/evaluation-llm-tracing
- LangSmith OpenTelemetry evaluation: https://docs.langchain.com/langsmith/evaluate-with-opentelemetry
- Open-Meteo docs: https://open-meteo.com/en/docs
