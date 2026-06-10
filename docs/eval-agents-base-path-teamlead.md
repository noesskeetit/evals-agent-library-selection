# [Eval Agents] Короткая версия для тимлида

Дата среза: 2026-06-10.  
Полная версия с деталями: `docs/eval-agents-base-path-wiki-draft.md`.

## Решение

**Рекомендация: DeepEval как base path платформы.**  
**OpenEvals оставить как companion adapter для Golden Path / reference trajectory.**

Почему так:

- DeepEval выигрывает как платформа: community, набор метрик, tracing/eval harness, multi-turn/RAG/agentic/MCP сценарии.
- OpenEvals выигрывает в одном узком месте: Golden Path trajectory API у него проще и нативнее.
- Blackbox и Golden Path нужны оба: negative case показал, что красивый выдуманный ответ проходит blackbox, но падает на Golden Path.

Практическая схема:

```text
Внутренний контракт: EvalCase
Base engine: DeepEval
Companion: OpenEvals для native trajectory/reference checks
Judge в тестах: deepseek-ai/DeepSeek-V4-Pro через Cloud.ru FM API
Agent under test: weather agent на moonshotai/Kimi-K2.6
```

## Что тестировали

Агент: LLM-powered погодный агент с Open-Meteo tools.

```text
Task:
Give me a short weather plan for Moscow, Russia for the next 3 days.

Actual path:
geocode_location -> get_weather_forecast -> final answer
```

Матрица 2x2:

| Variant | Library | Сценарий | Результат |
|---|---|---|---:|
| `openevals_golden_path_llm_as_judge` | OpenEvals | Golden Path по trajectory | pass |
| `openevals_blackbox_llm_as_judge` | OpenEvals | Blackbox по final answer | pass |
| `deepeval_golden_path_llm_as_judge` | DeepEval | `ToolCorrectnessMetric` + `GEval` по trace | pass |
| `deepeval_blackbox_llm_as_judge` | DeepEval | `GEval` по `LLMTestCase` | pass |

Negative case: агент написал правдоподобный прогноз, но не вызвал `get_weather_forecast`.

| Проверка | skipped forecast | no tools |
|---|---:|---:|
| OpenEvals Blackbox | pass | pass |
| DeepEval Blackbox | pass | pass |
| OpenEvals Golden Path | fail | fail |
| DeepEval Golden Path | fail | fail |

Вывод: **Blackbox проверяет качество ответа, Golden Path проверяет, что агент реально сделал обязательные шаги.**

Артефакты:

- `artifacts/comparison/eval_agents_weather_matrix_20260610T072414Z.json`
- `artifacts/negative/20260610T072334Z.json`
- `artifacts/openevals/20260610T071859Z.json`
- `artifacts/deepeval/20260610T071951Z.json`

## Сравнение по критериям ТЗ

Snapshot 2026-06-10:

| Критерий | OpenEvals | DeepEval | Вывод |
|---|---:|---:|---|
| GitHub stars | 1,070 | 16,063 | DeepEval сильно популярнее |
| Forks | 98 | 1,514 | DeepEval сильнее community |
| PyPI version | 0.2.0 | 4.0.5 | DeepEval зрелее |
| PyPI releases | 60 | 502 | DeepEval активнее релизится |
| Golden Path ergonomics | native trajectory API | через composition | OpenEvals удобнее |
| Blackbox | `create_llm_as_judge` | `GEval` + `LLMTestCase` | паритет |
| Гибкость сценариев | evaluator package | eval platform: RAG, agentic, DAG/custom, multi-turn, MCP, tracing | DeepEval шире |
| OTEL/tracing | через LangSmith ecosystem | свой `deepeval.tracing`, OTEL/Confident AI path | DeepEval сильнее |

Оговорка: live OTEL export end-to-end не поднимался. Но по коду пакетов `deepeval==4.0.5` содержит OTEL/tracing слой, а `openevals==0.2.0` сам OTEL не содержит: его путь идёт через LangSmith.

## Golden Path, Blackbox и G-Eval

| Термин | Что это | Вход | Выход | Формат |
|---|---|---|---|---|
| Blackbox | Оценка финального ответа | `input`, `actual_output`, `expected_output`, rubric | score/pass + reason | финальный текст, не trace |
| Golden Path | Оценка пути агента | actual trajectory/trace + expected trajectory/trace | match/score + reason | tool calls, порядок, args, observations |
| G-Eval | Метод LLM-as-judge в DeepEval | поля `LLMTestCase`, указанные в `evaluation_params` | `score`, `success`, `reason` | текст, который мы сами положили в test case |

G-Eval не третий сценарий рядом с Blackbox и Golden Path. Blackbox/Golden Path отвечают **что оцениваем**, G-Eval отвечает **как LLM-судья ставит оценку**.

Форматы:

| Формат | Что содержит | Для чего хватает |
|---|---|---|
| Диалог | user/assistant messages | обычно Blackbox |
| Trajectory | последовательность tool calls | Golden Path по порядку действий |
| Trace | tool calls + args + observations + final answer | Golden Path + grounding |
| Full trace | trace + spans/timing/errors/cost/thread metadata | observability/OTEL/debug |

## Как выглядят evals в коде

### OpenEvals Blackbox

```python
evaluator = create_llm_as_judge(
    prompt=rubric + "\nInputs:\n{inputs}\nOutputs:\n{outputs}\nReference:\n{reference_outputs}",
    judge=judge,
    model=judge_model,
    feedback_key="blackbox_quality",
)

result = evaluator(
    inputs=case.input,
    outputs=case.actual_output,
    reference_outputs=case.expected_output,
)
```

Вход: задача, финальный ответ, reference/rubric.  
Выход: `{key, score, comment, metadata}`.

### OpenEvals Golden Path

```python
outputs = to_openai_tool_call_messages(case.actual_tools)
reference_outputs = to_openai_tool_call_messages(case.expected_tools)

match = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="ignore",
)

judge_eval = create_trajectory_llm_as_judge(judge=judge, model=judge_model)

deterministic_result = match(outputs=outputs, reference_outputs=reference_outputs)
llm_result = judge_eval(outputs=outputs, reference_outputs=reference_outputs)
```

Вход: OpenAI-style messages с `tool_calls`.  
Выход: deterministic match + LLM comment по trajectory.

### DeepEval Blackbox

```python
test_case = LLMTestCase(
    input=case.input,
    actual_output=case.actual_output,
    expected_output=case.expected_output,
)

metric = GEval(
    name="Blackbox Quality",
    criteria=case.rubric,
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
    threshold=0.5,
)

score = metric.measure(test_case)
```

Вход: `LLMTestCase`.  
Выход: `{score, success, reason, threshold}`.

### DeepEval Golden Path

```python
test_case = LLMTestCase(
    input=case.input,
    actual_output=case.actual_output,
    expected_output=case.expected_output,
    tools_called=[ToolCall(name=t.name, input_parameters=t.arguments) for t in case.actual_tools],
    expected_tools=[ToolCall(name=t.name, input_parameters=t.arguments) for t in case.expected_tools],
)

tool_metric = ToolCorrectnessMetric(
    threshold=1.0,
    should_exact_match=True,
    should_consider_ordering=True,
)

tool_result = tool_metric.measure(test_case)
```

Для LLM-as-judge по trajectory:

```python
trajectory_case = LLMTestCase(
    input=case.input,
    actual_output=serialize_trace_with_observations(case),
    expected_output="Expected path: geocode_location -> get_weather_forecast",
)

trajectory_metric = GEval(
    name="Golden Path Trajectory",
    criteria="Check tool order, missing tools, extra tools and grounding.",
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
    threshold=0.5,
)
```

Вход: `ToolCall[]` или serialized trace.  
Выход: `{score, success, reason, threshold}`.

## Ответы на спорные вопросы

### Можно ли сесть только на одну библиотеку?

Да. Если нужно минимизировать dependencies, можно выбрать **только DeepEval**. Он закрывает Blackbox, Golden Path через `ToolCorrectnessMetric`, Golden Path LLM-as-Judge через `GEval` над serialized trace и даёт более широкий tracing/eval harness.

Минус: Golden Path будет менее native, понадобится свой adapter для trace serialization, expected path и unified output.

### Что предлагается в гибридном варианте?

Не две платформы, а один контракт и два adapter-а:

```text
EvalCase
  -> DeepEval adapter: default/base path
  -> OpenEvals adapter: native trajectory checks
```

DeepEval отвечает за platform lifecycle и большинство сценариев. OpenEvals используется точечно там, где он проще: reference trajectory и trajectory LLM-as-judge.

### Можно ли отказаться от OpenEvals Golden Path?

Да. Сложность **умеренная**, не фундаментальная.

В DeepEval надо:

1. привести trace к `ToolCall[]`;
2. описать `expected_tools`;
3. сериализовать trace для LLM-судьи;
4. зафиксировать rubric/evaluation steps;
5. нормализовать output к формату платформы.

Если это легко, зачем тогда OpenEvals Golden Path? Потому что OpenEvals уже даёт native trajectory API: меньше glue-кода, проще тесты, быстрее старт. Но если dependency budget жёсткий, OpenEvals можно убрать и жить на DeepEval-only.

## Итог

Более подходящая библиотека как base path: **DeepEval**.

Причина: DeepEval выигрывает по сумме критериев ТЗ: community, ширина eval-сценариев, tracing/OTEL story. OpenEvals выигрывает в узком, но важном месте: ergonomics Golden Path trajectory.

Итоговая рекомендация:

```text
Production base path: DeepEval
Companion: OpenEvals для Golden Path, пока платформа стабилизирует свой EvalCase
Long-term: оставить OpenEvals только если native trajectory API реально экономит поддержку
```

Минимальный platform contract:

```python
EvalCase(
    input=user_task,
    actual_output=agent_final_answer,
    expected_output=reference_expectation,
    actual_tools=actual_trace.tool_calls,
    expected_tools=golden_path.tool_calls,
    rubric=evaluation_rubric,
)
```
