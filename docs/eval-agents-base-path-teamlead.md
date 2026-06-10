# [Eval Agents] Короткая версия для тимлида

Дата среза: 2026-06-10.
Полная версия с деталями: `docs/eval-agents-base-path-wiki-draft.md`.

## Решение

**Рекомендация: выбираем DeepEval как единственный обязательный base path платформы.**
**OpenEvals не нужен как обязательная зависимость; его можно держать в виду как optional adapter для более нативного Golden Path API.**

Почему так:

- DeepEval выигрывает как платформа: community, набор метрик, tracing/eval harness, multi-turn/RAG/agentic/MCP сценарии.
- OpenEvals выигрывает в одном узком месте: Golden Path trajectory API у него проще и нативнее, но это не критично.
- Blackbox и Golden Path нужны оба: negative case показал, что красивый выдуманный ответ проходит blackbox, но падает на Golden Path.

Практическая схема:

```text
Внутренний контракт: EvalCase
Base engine: DeepEval
Optional: OpenEvals только если DeepEval adapter для trajectory станет дорогим в поддержке
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

Здесь три разных слоя:

```text
Blackbox / Golden Path = что оцениваем
G-Eval = как DeepEval делает LLM-as-judge
Диалог / trajectory / trace / full trace = какой формат данных подаём
```

### Форматы

| Формат | Что содержит | Пример | Для чего хватает |
|---|---|---|---|
| `input + output` | задача + финальный ответ | `дай погоду` -> `завтра дождь` | Blackbox |
| Диалог | user/assistant messages, иногда multi-turn | `user -> assistant -> user -> assistant` | Blackbox по диалогу |
| Trajectory | последовательность действий | `geocode -> forecast` | Golden Path по порядку |
| Trace | trajectory + args + observations + final answer | tool call + tool result + answer | Golden Path + grounding |
| Full trace | trace + spans/timing/errors/metadata/costs | OTEL trace tree | observability/debug |

Для weather agent различие такое:

```text
Input:
Give me a short weather plan for Moscow for 3 days.

Blackbox sees:
input + final answer

Golden Path sees:
geocode_location -> get_weather_forecast

Trace:
1. geocode_location({"location": "Moscow"})
   observation: {"lat": 55.75, "lon": 37.61}

2. get_weather_forecast({"lat": 55.75, "lon": 37.61})
   observation: {"forecast": [...]}

3. final answer: "June 10..."

Full trace:
trace_id=abc123
  span: agent.run
    span: llm.call
    span: tool.geocode_location
    span: tool.get_weather_forecast
    span: llm.final_answer
    span: eval.blackbox
    span: eval.golden_path
```

### Blackbox

Blackbox отвечает на вопрос: **хороший ли финальный ответ для пользователя?**

Типичный вход:

```python
{
    "input": "Give me a short weather plan for Moscow for 3 days.",
    "actual_output": "June 10: partly cloudy, 18-25 C, no rain...",
    "expected_output": "Answer should mention dates, temperatures, precipitation and practical advice.",
    "rubric": "Judge whether the final answer is useful, grounded-looking and complete.",
}
```

С чем имеем дело: `input + final answer` или `dialogue + final answer`. Не trace, не tool calls, не observations.

Типичный выход:

```json
{
  "score": 1.0,
  "success": true,
  "reason": "The answer includes dates, temperatures, precipitation and useful advice."
}
```

Blackbox хорошо ловит нерелевантный, пустой или плохой ответ. Но он плохо ловит ситуацию, когда агент **не сделал работу, но красиво ответил**. В нашем negative case blackbox поставил pass фейковому прогнозу, потому что видел только хороший текст.

### Golden Path

Golden Path отвечает на вопрос: **агент решал задачу правильным способом?**

Типичный вход:

```python
{
    "actual_trace": [
        {
            "tool_name": "geocode_location",
            "arguments": {"location": "Moscow, Russia"},
            "observation": {"latitude": 55.75, "longitude": 37.61},
        },
        {
            "tool_name": "get_weather_forecast",
            "arguments": {"latitude": 55.75, "longitude": 37.61},
            "observation": {"forecast": [...]},
        },
    ],
    "expected_trace": [
        {"tool_name": "geocode_location"},
        {"tool_name": "get_weather_forecast"},
    ],
    "rubric": "Check missing tools, extra tools, order and grounding.",
}
```

С чем имеем дело: trajectory/trace, tool calls, порядок, args, observations, иногда final answer.

Типичный выход:

```json
{
  "score": 0.0,
  "success": false,
  "reason": "The agent called geocode_location but skipped get_weather_forecast. Final weather claims are unsupported."
}
```

Golden Path ловит пропущенные tools, неправильный порядок, лишние tools, неверные аргументы и ответ без evidence. Но сам по себе может не оценить UX/качество текста, поэтому не заменяет Blackbox.

### G-Eval

G-Eval - это **не третий сценарий рядом с Blackbox и Golden Path**. Это способ LLM-as-judge оценки в DeepEval.

Он отвечает на вопрос: **как DeepEval просит LLM-судью выставить score по критериям?**

Для Blackbox:

```python
test_case = LLMTestCase(
    input="Give me weather plan for Moscow",
    actual_output="June 10: partly cloudy...",
    expected_output="Answer should mention dates, weather evidence and advice.",
)

metric = GEval(
    name="Blackbox Quality",
    criteria="Check whether the answer is useful and complete.",
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
)
```

Здесь G-Eval видит только `input`, `actual_output`, `expected_output`. Он не видит trace.

Для Golden Path через G-Eval надо самому положить trace в текст:

```python
trajectory_case = LLMTestCase(
    input=case.input,
    actual_output="""
Actual trajectory:
1. geocode_location args={"location": "Moscow"}
   observation={"latitude": 55.75, "longitude": 37.61}

2. get_weather_forecast args={"latitude": 55.75}
   observation={"forecast": [...]}

Final answer:
June 10: partly cloudy...
""",
    expected_output="Expected path: geocode_location -> get_weather_forecast",
)

metric = GEval(
    name="Golden Path Trajectory",
    criteria="Check tool order, missing tools, extra tools and grounding.",
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
)
```

То есть G-Eval работает с тем, что мы сами положили в `LLMTestCase`.

| Вопрос | Blackbox | Golden Path | G-Eval |
|---|---|---|---|
| Это что? | Сценарий eval | Сценарий eval | Метод LLM-судейства в DeepEval |
| Что оценивает? | Финальный ответ | Путь агента | То, что положили в `LLMTestCase` |
| Видит tools? | Нет | Да | Только если сериализовали trace |
| Видит observations? | Нет | Может видеть | Только если положили в текст |
| Работает с dialogue? | Да | Обычно нет | Да, если dialogue положили в test case |
| Работает с full trace? | Обычно нет | Да, если adapter поддерживает | Да, если full trace сериализован |
| Ловит красивую галлюцинацию без tool calls? | Обычно нет | Да | Да, если это Golden Path G-Eval; нет, если Blackbox G-Eval |
| Типичный output | score + reason | match/score + reason | score + success + reason |

Короткая формула: **Blackbox работает с ответом. Golden Path работает с trace/trajectory. G-Eval работает с тем текстом, который положили в `LLMTestCase`.**

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

Минус небольшой: Golden Path будет менее native, понадобится свой adapter для trace serialization, expected path и unified output. По нашим тестам это не blocker.

### Что предлагается в гибридном варианте?

Гибридный вариант теперь не рекомендация по умолчанию, а fallback. Базово делаем один контракт и один обязательный adapter:

```text
EvalCase
  -> DeepEval adapter: default/base path
  -> OpenEvals adapter: optional, только если понадобится native trajectory API
```

DeepEval отвечает за platform lifecycle и все обязательные сценарии. OpenEvals можно добавить точечно, если на практике окажется, что его native reference trajectory API экономит поддержку.

### Можно ли отказаться от OpenEvals Golden Path?

Да. Сложность **умеренная**, не фундаментальная.

В DeepEval надо:

1. привести trace к `ToolCall[]`;
2. описать `expected_tools`;
3. сериализовать trace для LLM-судьи;
4. зафиксировать rubric/evaluation steps;
5. нормализовать output к формату платформы.

Если это легко, зачем тогда OpenEvals Golden Path? Только ради ergonomics: у OpenEvals native trajectory API, меньше glue-кода и чуть проще тесты. Но функционально это не критично: DeepEval уже поймал те же positive/negative кейсы, поэтому OpenEvals можно убрать и жить на DeepEval-only.

## Итог

Более подходящая библиотека как base path: **DeepEval**.

Причина: DeepEval выигрывает по сумме критериев ТЗ: community, ширина eval-сценариев, tracing/OTEL story. OpenEvals выигрывает в узком, но важном месте: ergonomics Golden Path trajectory.

Итоговая рекомендация:

```text
Production base path: DeepEval-only
OpenEvals: optional, не обязательная зависимость
Long-term: добавить OpenEvals только если native trajectory API реально экономит поддержку
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
