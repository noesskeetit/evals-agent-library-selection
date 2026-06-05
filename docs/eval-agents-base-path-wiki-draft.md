# [Eval Agents] Оценка решений для base path Eval

Дата среза: 2026-06-05.

Статус: wiki-ready draft. Страницу в wiki пока не создавал; документ можно переносить как дочернюю страницу.

## Краткий вывод

Рекомендация: **DeepEval как base path платформы**, **OpenEvals как companion runner для native Golden Path / reference trajectory**.

Почему так:

- DeepEval выигрывает по community support: сильно больше stars/forks, активнее релизы, больше contributor surface.
- DeepEval шире как eval platform: `GEval`, DAG/custom metrics, RAG, agentic metrics, multi-turn, MCP, tracing, component-level evals.
- DeepEval ближе к tracing/eval harness: есть собственный tracing layer и Confident AI path; OTEL path есть через Confident AI/интеграции. В этом R&D это **doc-based assessment**, live OTEL export отдельно не прогонялся.
- OpenEvals удобнее именно для Golden Path trajectory: `create_trajectory_match_evaluator` и `create_trajectory_llm_as_judge` принимают agent trajectory как first-class input.

Практический выбор:

```text
Base path: DeepEval
Companion runner: OpenEvals для native trajectory/reference checks
Default judge в тестах: deepseek-ai/DeepSeek-V4-Pro через Cloud.ru FM API
Agent-under-test в live-прогоне: moonshotai/Kimi-K2.6
```

Важно: это не значит, что OpenEvals плохой. Наоборот, для Golden Path он оказался самым прямым и понятным. Но как основа платформы DeepEval сильнее по сумме критериев из ТЗ.

## Что требовалось по ТЗ

На платформе должно быть два варианта оценки:

1. **Golden Path with LLM as Judge**  
   Оценка того, шел ли агент правильным путем: вызывал ли нужные tools, в правильном ли порядке, собрал ли evidence до ответа, не пропустил ли обязательный шаг. Целевой пример из ТЗ: OpenEvals `trajectory-llm-as-judge`.

2. **Blackbox LLM as Judge**  
   Оценка только финального ответа: пользовательский input, actual answer, expected/reference expectation и rubric. Целевой пример из ТЗ: OpenEvals `llm-as-judge`.

Нужно было оценить:

- `langchain-ai/openevals`
- `confident-ai/deepeval`
- опциональные альтернативы, если они меняют вывод

Критерии выбора:

- поддержка сообществом;
- гибкость eval-сценариев;
- интеграция с OpenTelemetry/tracing из коробки.

Ожидаемый тест: прогон любого агента этими библиотеками, оценка результата и комментарий.

## Что именно было протестировано

Для теста сделан не полностью моковый fixture, а простой LLM-powered погодный агент с интернет-инструментами.

```text
Agent brain: moonshotai/Kimi-K2.6
Judge: deepseek-ai/DeepSeek-V4-Pro
Provider: Cloud.ru FM API, OpenAI-compatible endpoint
Reasoning: high
Max judge tokens: 50000
Internet tools: Open-Meteo Geocoding API, Open-Meteo Forecast API
```

Задача агенту:

```text
Give me a short weather plan for Moscow, Russia for the next 3 days.
```

Фактический путь агента:

```text
geocode_location -> get_weather_forecast -> final answer
```

То есть агент сначала геокодит `Moscow, Russia`, потом по координатам получает прогноз на 3 дня, потом пишет короткий план по погоде.

Код:

- `src/evals_agent/llm_weather_agent.py` - агент на Kimi K2.6;
- `src/evals_agent/weather_tools.py` - реальные Open-Meteo tools;
- `src/evals_agent/runners/run_openevals.py` - OpenEvals runner;
- `src/evals_agent/runners/run_deepeval.py` - DeepEval runner;
- `src/evals_agent/runners/collect_research_snapshot.py` - сбор свежего GitHub/PyPI snapshot;
- `src/evals_agent/runners/build_comparison.py` - сбор единой 2x2 matrix из свежих artifacts;
- `src/evals_agent/runners/common.py` - общий adapter: final answer, expected answer, trajectory messages, serialized trace.

Артефакты live-прогонов:

- `artifacts/openevals/20260605T124343Z.json`
- `artifacts/deepeval/20260605T124504Z.json`
- `artifacts/comparison/eval_agents_weather_matrix_20260605T124508Z.json`
- `artifacts/comparison/research_snapshot.json`

Предыдущие JSON-прогоны удалены. Source of truth для этой статьи - только artifacts из списка выше.

Важно про сравнение live-runs: OpenEvals и DeepEval запускались как два независимых прогона одного weather agent. Tool trace и weather observations совпали, но формулировка финального ответа может слегка отличаться из-за LLM nondeterminism. Для Golden Path source of truth - trace/tool calls, а не дословный текст ответа.

JSON-артефакты теперь самодостаточны для аудита: кроме `agent_run`, `judge` и `results`, в них есть `eval_inputs` с sanitized input/output/reference/rubric/criteria и trajectory payload. Секреты и `.env` значения туда не пишутся.

Команды воспроизведения:

```bash
python -m evals_agent.runners.run_openevals --agent weather
python -m evals_agent.runners.run_deepeval --agent weather
```

## Результат 2x2

| Variant ID | Вариант | Библиотека | Что проверяли | Результат | Комментарий |
|---|---|---|---|---:|---|
| `openevals_golden_path_llm_as_judge` | Golden Path LLM-as-Judge | OpenEvals | trajectory относительно reference trajectory | pass | Самый native вариант: trajectory передается как messages/tool_calls. |
| `openevals_blackbox_llm_as_judge` | Blackbox LLM-as-Judge | OpenEvals | качество финального weather answer | pass | Удобный evaluator, потребовался небольшой adapter под Cloud.ru JSON response. |
| `deepeval_golden_path_llm_as_judge` | Golden Path LLM-as-Judge | DeepEval | `ToolCorrectnessMetric` + `GEval` над serialized trace | pass | Работает, но Golden Path надо собрать композицией метрик и adapter-кодом. |
| `deepeval_blackbox_llm_as_judge` | Blackbox LLM-as-Judge | DeepEval | `GEval` над `LLMTestCase` | pass | Ложится естественно: input, actual_output, expected_output, criteria. |

Сводный JSON:

```text
artifacts/comparison/eval_agents_weather_matrix_20260605T124508Z.json
```

Итог по тесту: обе библиотеки умеют закрыть оба сценария. Разница не в том, "можно или нельзя", а в том, насколько это native, расширяемо и удобно поддерживать на платформе.

## Главный вопрос: Golden Path, Blackbox и G-Eval

Коротко:

```text
Blackbox = сценарий оценки финального ответа
Golden Path = сценарий оценки пути/trace агента
G-Eval = метод LLM-as-judge в DeepEval
```

`G-Eval` не является третьим типом платформенного сценария на одном уровне с Blackbox и Golden Path. Это способ судить через LLM по критериям. Его можно использовать:

- для Blackbox, если в `LLMTestCase` положить input, actual output и expected output;
- для Golden Path, если в `LLMTestCase.actual_output` положить serialized trace, а в `expected_output` - expected path;
- для component-level eval, если запускать его внутри trace/span.

## Диалог, trajectory, trace и full trace

Эти термины лучше разделять, иначе легко перепутать форматы.

| Термин | Что содержит | Типичный пример | Достаточно для Blackbox | Достаточно для Golden Path |
|---|---|---|---:|---:|
| Диалог | user/assistant messages | `user: погода?`, `assistant: вот прогноз` | да | обычно нет |
| Trajectory | последовательность действий агента | `assistant tool_call: geocode`, `assistant tool_call: forecast` | нет | да, если проверяем путь |
| Trace | trajectory + observations + final answer | tool args, tool outputs, answer | да | да |
| Full trace | trace + spans/timings/errors/metadata/thread | OTEL spans, latency, costs, errors, nested components | да | да, плюс observability |

В нашем тесте:

- **Blackbox** видел только пользовательскую задачу, финальный ответ, expected expectation и rubric.
- **OpenEvals Golden Path** получил trajectory в виде OpenAI-style chat messages с `tool_calls`.
- **DeepEval ToolCorrectness** получил нормализованные `ToolCall[]`.
- **DeepEval Golden Path через GEval** получил serialized trace как текст, включая tool args, observations и final answer.

## Blackbox: что на вход и выход

Blackbox оценивает внешний контракт:

```text
user input -> final answer
```

Он отвечает на вопрос:

```text
Хороший ли финальный ответ для пользователя?
```

Он не отвечает надежно на вопросы:

```text
Агент точно вызвал нужный tool?
Агент не пропустил обязательный шаг?
Финальный ответ реально основан на tool observation?
Порядок действий был правильным?
```

Пример для погодного агента:

```text
input:
Give me a short weather plan for Moscow, Russia for the next 3 days.

actual_output:
June 5: partly cloudy, high 23.9 C / low 12.4 C, no rain...
June 6: partly cloudy, high 24.1 C / low 12.0 C, no rain...
June 7: partly cloudy, high 25.9 C / low 13.2 C, no rain...

expected_output / reference expectation:
The answer should provide a concise weather plan grounded in the forecast returned by tools,
mention dates and weather evidence, and include practical advice.

rubric:
Judge only the user input, final answer, and reference expectation.
Check dates, temperature, precipitation/wind evidence and practical recommendations.
```

Выход Blackbox обычно компактный:

```json
{
  "score": true,
  "comment": "The final answer provides a concise 3-day weather plan..."
}
```

или в DeepEval:

```json
{
  "score": 1.0,
  "success": true,
  "reason": "The response directly addresses the weather plan request...",
  "threshold": 0.5
}
```

## Golden Path: что на вход и выход

Golden Path оценивает не только результат, а путь:

```text
actual trace / trajectory -> compare with expected trace / trajectory
```

Он отвечает на вопрос:

```text
Агент решал задачу правильным способом?
```

Для погодного агента expected path:

```text
geocode_location -> get_weather_forecast
```

Пример ошибки, которую Golden Path поймает, а Blackbox может пропустить:

```text
Агент написал правдоподобный прогноз, но не вызвал get_weather_forecast.
Blackbox может поставить pass, потому что текст выглядит полезным.
Golden Path должен поставить fail, потому что required tool call отсутствует.
```

Выход Golden Path зависит от библиотеки:

- deterministic match обычно возвращает boolean / score;
- LLM-as-judge возвращает score + comment/reason;
- trace-aware вариант может дополнительно объяснить missing/extra tools, неправильный порядок, unsupported claims.

## OpenEvals Blackbox: формат входа и выхода

Использованный primitive:

```python
from openevals.llm import create_llm_as_judge

blackbox_evaluator = create_llm_as_judge(
    prompt=blackbox_rubric + "\nInputs:\n{inputs}\nOutputs:\n{outputs}\nReference:\n{reference_outputs}",
    judge=judge,
    model=judge_config.model,
    feedback_key="blackbox_quality",
)

result = blackbox_evaluator(
    inputs=eval_input,
    outputs=final_answer_text(agent_run),
    reference_outputs=expected_blackbox_answer_for(agent_run),
)
```

Вход:

| Поле | Тип | Что содержит |
|---|---|---|
| `inputs` | `str` или structured object | задача пользователя |
| `outputs` | `str` или structured object | финальный ответ агента |
| `reference_outputs` | optional `str` или object | ожидаемый ответ / expectation |
| `prompt` | `str` / prompt template / callable | rubric, куда подставляются `inputs`, `outputs`, `reference_outputs` |
| `judge` / `model` | LLM client/model | модель-судья |

С чем имеем дело:

```text
final answer only
не dialogue transcript
не full trace
не tool observations
```

Выход:

```json
{
  "key": "blackbox_quality",
  "score": true,
  "comment": "The final answer provides a concise 3-day weather plan...",
  "metadata": null
}
```

Оценка удобства: **хорошо**. API компактный, prompt customization нормальный, выход простой. Единственный практический нюанс в нашем тесте: для Cloud.ru DeepSeek пришлось адаптировать structured JSON response, потому OpenEvals ожидает OpenAI/structured-output поведение.

## OpenEvals Golden Path: формат входа и выхода

Использованные primitives:

```python
from openevals.trajectory import (
    create_trajectory_match_evaluator,
    create_trajectory_llm_as_judge,
)

outputs = trajectory_messages(agent_run)
reference_outputs = reference_trajectory_messages(agent_run)

match_evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict",
    tool_args_match_mode="ignore",
)

trajectory_evaluator = create_trajectory_llm_as_judge(
    judge=judge,
    model=judge_config.model,
)

match_result = match_evaluator(
    outputs=outputs,
    reference_outputs=reference_outputs,
)

judge_result = trajectory_evaluator(
    outputs=outputs,
    reference_outputs=reference_outputs,
)
```

Вход:

| Поле | Тип | Что содержит |
|---|---|---|
| `outputs` | `list[ChatCompletionMessage]` | фактическая trajectory агента |
| `reference_outputs` | optional `list[ChatCompletionMessage]` | golden/reference trajectory |
| `trajectory_match_mode` | `strict`, `unordered`, `subset`, `superset` | как сравнивать последовательность tools |
| `tool_args_match_mode` | `exact`, `ignore`, `subset`, `superset` | как сравнивать аргументы tool calls |
| `judge` / `model` | LLM client/model | модель-судья для LLM-as-judge варианта |

Пример фактического `outputs` в нашем runner:

```json
[
  {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "id": "call_0",
        "type": "function",
        "function": {
          "name": "geocode_location",
          "arguments": "{\"location\": \"Moscow, Russia\"}"
        }
      }
    ]
  },
  {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "id": "call_1",
        "type": "function",
        "function": {
          "name": "get_weather_forecast",
          "arguments": "{\"forecast_days\": 3, \"latitude\": 55.75204, \"longitude\": 37.61781}"
        }
      }
    ]
  }
]
```

`reference_outputs` имеет тот же message format, но описывает expected path.

С чем имеем дело:

```text
trajectory как chat messages
tool_calls являются first-class данными
это может быть диалог + tool calls + tool observations + final answer,
если adapter передаст полный transcript
```

Важная оговорка по нашему тесту: текущий OpenEvals adapter передает только assistant messages с `tool_calls`, без `tool` messages с observations. Поэтому OpenEvals Golden Path в этом прогоне отлично проверяет выбор и порядок tools, но grounding финального ответа по observation лучше проверять отдельным eval или расширить adapter до full transcript.

Выход deterministic match:

```json
{
  "key": "trajectory_strict_match",
  "score": true,
  "comment": null,
  "metadata": null
}
```

Выход LLM-as-judge:

```json
{
  "key": "trajectory_accuracy",
  "score": true,
  "comment": "The actual trajectory is identical to the reference trajectory...",
  "metadata": null
}
```

Оценка удобства: **отлично для Golden Path**. Это самый прямой API среди двух библиотек для reference trajectory. Если платформе важен именно Golden Path как first-class сценарий, OpenEvals стоит держать рядом даже при выборе DeepEval как base path.

## DeepEval Blackbox: формат входа и выхода

Использованный primitive:

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

test_case = LLMTestCase(
    input=run.input,
    actual_output=final_answer_text(run),
    expected_output=expected_blackbox_answer_for(run),
)

blackbox_metric = GEval(
    name="Blackbox Quality",
    criteria=blackbox_rubric_for(agent_run),
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
    threshold=0.5,
    async_mode=False,
)

score = blackbox_metric.measure(test_case)
```

Вход:

| Поле | Тип | Что содержит |
|---|---|---|
| `LLMTestCase.input` | `str` | задача пользователя |
| `LLMTestCase.actual_output` | `str` | финальный ответ агента |
| `LLMTestCase.expected_output` | optional `str` | expected/reference answer |
| `criteria` | `str` | rubric |
| `evaluation_params` | `list[SingleTurnParams]` | какие поля test case попадут в judge prompt |
| `model` | `DeepEvalBaseLLM` или model string | LLM-судья |
| `threshold` | `float` | pass/fail граница |

С чем имеем дело:

```text
single-turn test case
final answer only
не full trace
```

Выход:

```json
{
  "score": 1.0,
  "success": true,
  "reason": "The response directly addresses the weather plan request...",
  "threshold": 0.5
}
```

Оценка удобства: **хорошо**. Для blackbox DeepEval ложится естественно. `LLMTestCase` хорошо подходит как общий объект платформы, если дальше нужны разные metrics.

## DeepEval Golden Path через ToolCorrectness: формат входа и выхода

Использованный primitive:

```python
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall

tools = [
    ToolCall(
        name=step.tool_name,
        input_parameters=step.arguments,
        output=step.observation,
    )
    for step in run.trace
]

expected_tools = []
for index, tool_name in enumerate(expected_tool_names_for(run)):
    kwargs = {"name": tool_name}
    if index < len(run.trace) and run.trace[index].tool_name == tool_name:
        step = run.trace[index]
        kwargs["input_parameters"] = step.arguments
        kwargs["output"] = step.observation
    expected_tools.append(ToolCall(**kwargs))

test_case = LLMTestCase(
    input=run.input,
    actual_output=final_answer_text(run),
    expected_output=expected_blackbox_answer_for(run),
    tools_called=tools,
    expected_tools=expected_tools,
)

tool_metric = ToolCorrectnessMetric(
    threshold=1.0,
    should_exact_match=True,
    should_consider_ordering=True,
)
```

Вход:

| Поле | Тип | Что содержит |
|---|---|---|
| `tools_called` | `list[ToolCall]` | фактические tool calls агента |
| `expected_tools` | `list[ToolCall]` | expected/golden tool calls |
| `ToolCall.name` | `str` | имя tool |
| `ToolCall.input_parameters` | `dict` | аргументы tool |
| `ToolCall.output` | any | observation / output tool |
| `should_exact_match` | `bool` | требовать точное совпадение |
| `should_consider_ordering` | `bool` | учитывать порядок вызовов |

Пример `ToolCall`:

```python
ToolCall(
    name="get_weather_forecast",
    input_parameters={
        "latitude": 55.75204,
        "longitude": 37.61781,
        "forecast_days": 3,
    },
    output={
        "status": "ok",
        "forecast": [
            {"date": "2026-06-05", "temperature_max_c": 23.9}
        ],
    },
)
```

С чем имеем дело:

```text
нормализованные tool calls
не OpenAI messages
не полный диалог
это structured slice trace, достаточный для tool correctness
```

Выход:

```json
{
  "score": 1.0,
  "success": true,
  "reason": "Exact match: expected ['geocode_location', 'get_weather_forecast'], called ['geocode_location', 'get_weather_forecast'].",
  "threshold": 1.0
}
```

Оценка удобства: **нормально для deterministic tool correctness**, но это еще не полноценный Golden Path LLM-as-Judge. Это проверка tool correctness, а не LLM-судейство по full trajectory.

## DeepEval Golden Path через G-Eval: формат входа и выхода

Чтобы получить именно LLM-as-judge по trajectory в DeepEval, trace пришлось сериализовать в `actual_output`.

Использованный primitive:

```python
trajectory_test_case = LLMTestCase(
    input=run.input,
    actual_output=(
        "Actual trajectory:\n"
        f"{trajectory_text(run)}\n\n"
        "Final answer:\n"
        f"{final_answer_text(run)}"
    ),
    expected_output=expected_trajectory_text_for(run),
)

trajectory_metric = GEval(
    name="Golden Path Trajectory",
    criteria=TRAJECTORY_RUBRIC,
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=judge_model,
    threshold=0.5,
)
```

Вход:

| Поле | Тип | Что содержит |
|---|---|---|
| `LLMTestCase.input` | `str` | задача пользователя |
| `LLMTestCase.actual_output` | `str` | serialized trace + final answer |
| `LLMTestCase.expected_output` | `str` | expected golden path |
| `criteria` | `str` | rubric для trajectory judge |
| `evaluation_params` | `list[SingleTurnParams]` | поля, которые получит judge |

Пример `actual_output`:

```text
Actual trajectory:
1. geocode_location args={"location": "Moscow, Russia"}
   observation={"status": "ok", "latitude": 55.75204, "longitude": 37.61781, ...}
2. get_weather_forecast args={"forecast_days": 3, "latitude": 55.75204, "longitude": 37.61781}
   observation={"status": "ok", "forecast": [...]}

Final answer:
June 5: partly cloudy, high 23.9 C / low 12.4 C...
```

Пример `expected_output`:

```text
Expected golden path: geocode_location -> get_weather_forecast.
The agent should geocode the requested location before fetching the weather forecast
and should ground the final answer in forecast observations.
```

С чем имеем дело:

```text
full-ish trace as text
tool args included
tool observations included
final answer included
но trace не является native object для GEval
```

Выход:

```json
{
  "score": 1.0,
  "success": true,
  "reason": "The actual output follows the expected golden path exactly...",
  "threshold": 0.5
}
```

Оценка удобства: **рабоче, но менее удобно, чем OpenEvals Golden Path**. DeepEval может судить trajectory, но для этого нужен adapter: либо `ToolCall[]`, либо serialized trace, либо собственная metric/template. Зато после adapter мы остаемся внутри единой DeepEval модели test cases, metrics, tracing и reports.

## Сравнение форматов входа/выхода

| Сценарий | OpenEvals input | OpenEvals output | DeepEval input | DeepEval output |
|---|---|---|---|---|
| Blackbox LLM-as-Judge | `inputs`, `outputs`, `reference_outputs`, prompt | `{key, score, comment, metadata}` | `LLMTestCase(input, actual_output, expected_output)` + `GEval` | `{score, success, reason, threshold}` |
| Golden deterministic | `outputs`, `reference_outputs` как chat messages/tool_calls | `{key, score, comment, metadata}` | `LLMTestCase(tools_called, expected_tools)` + `ToolCorrectnessMetric` | `{score, success, reason, threshold}` |
| Golden LLM-as-Judge | `outputs`, `reference_outputs` как chat messages/tool_calls, optional full transcript | `{key, score, comment, metadata}` | `LLMTestCase(actual_output=serialized_trace, expected_output=expected_path)` + `GEval` | `{score, success, reason, threshold}` |
| Full trace / observability | Через LangSmith/OpenTelemetry path, не сам `openevals` package | LangSmith experiment feedback | `deepeval.tracing` / Confident AI / OTEL integrations | trace tree + metric scores/reasons |

Самое важное различие:

```text
OpenEvals Golden Path:
  trace/trajectory - это входной формат evaluator-а.

DeepEval Golden Path:
  trace/trajectory надо адаптировать в ToolCall[] или serialized text,
  зато дальше это живет внутри более широкой metric/test-case платформы.
```

## Community support

Snapshot из GitHub/PyPI на 2026-06-05T12:26:28Z:

| Библиотека | Stars | Forks | Последний push | PyPI version | PyPI releases |
|---|---:|---:|---|---|---:|
| OpenEvals | 1,068 | 97 | 2026-06-03 | 0.2.0 | 60 |
| DeepEval | 15,931 | 1,492 | 2026-06-05 | 4.0.5 | 502 |

Вывод: **DeepEval выигрывает community support с большим отрывом**.

OpenEvals моложе и активно развивается, но по зрелости сообщества DeepEval сейчас сильнее.

## Гибкость eval-сценариев

OpenEvals хорошо закрывает:

- blackbox LLM-as-judge;
- custom prompts;
- structured output evals;
- RAG-style prompts;
- code evals;
- exact/string/embedding metrics;
- agent trajectory match;
- agent trajectory LLM-as-judge;
- conversation prompts.

DeepEval закрывает:

- `GEval`;
- DAG/custom metrics;
- RAG metrics;
- agentic metrics;
- tool correctness;
- task completion / goal accuracy / plan adherence patterns;
- multi-turn evaluation;
- conversational metrics;
- MCP evaluation;
- synthetic data / goldens;
- tracing;
- component-level evals;
- CLI reports / inspect flow;
- Confident AI online evaluation path.

Вывод: **DeepEval гибче как base path**. OpenEvals очень хорош как evaluator package, но DeepEval больше похож на полноценный eval harness.

## OpenTelemetry / tracing

По ТЗ важен именно "OpenTelemetry tracing из коробки". Здесь нужно аккуратно:

### OpenEvals

OpenEvals сам по себе - это в первую очередь библиотека evaluator-функций. У него есть LangSmith integration story. LangSmith отдельно поддерживает OpenTelemetry tracing и evaluation over OpenTelemetry traces.

Практический смысл:

```text
OpenEvals -> удобно считать evaluator result
LangSmith -> хранить/смотреть/оценивать traces, включая OTEL ingestion
```

То есть OpenTelemetry path есть в экосистеме LangChain/LangSmith, но не как "openevals package сам собрал trace".

### DeepEval

DeepEval имеет собственный tracing API:

```python
from deepeval.tracing import observe, update_current_trace, update_current_span
```

В tracing docs есть модель trace/span, component-level evals и отправка в Confident AI. В Confident AI docs отдельно описан путь через OpenTelemetry для инструментирования без decorator changes.

Практический смысл:

```text
DeepEval -> metric engine + tracing primitives
Confident AI -> trace UI / online evals / OTEL integrations
```

Вывод: **по документации DeepEval сильнее для base path, если платформа хочет держать eval и trace ближе друг к другу**. Но это не live OTEL benchmark: экспорт OpenTelemetry span-ов в этом R&D не поднимался. Перед production-решением нужен отдельный spike: instrument sample agent, export OTEL traces, проверить linking trace/span/eval result и поведение при nested tool calls. Если компания уже выбирает LangSmith как trace backend, OpenEvals становится естественным companion.

## Итоговая оценка по критериям ТЗ

| Критерий | Победитель | Почему |
|---|---|---|
| Поддержка сообществом | DeepEval | Больше stars/forks, старше проект, активнее релизная история. |
| Гибкость eval-сценариев | DeepEval | Больше готовых метрик и сценариев за пределами single evaluator functions. |
| OpenTelemetry/tracing story | DeepEval, doc-based | Ближе к integrated tracing/eval harness по документации; OpenEvals полагается на LangSmith ecosystem. Live OTEL export не тестировался. |
| Golden Path ergonomics | OpenEvals | Native trajectory APIs, меньше adapter-кода. |
| Blackbox ergonomics | Ничья / легкий плюс DeepEval для platform base | Оба удобны; DeepEval лучше ложится в единый `LLMTestCase` контракт. |

Финальный выбор:

```text
DeepEval wins as base path.
OpenEvals should remain supported for native golden/reference trajectory evals.
```

## Рекомендованный platform contract

Не стоит завязывать внутренний контракт платформы напрямую на формат одной библиотеки. Лучше сделать нейтральный `EvalCase`, а библиотеки подключать adapters.

```yaml
EvalCase:
  id: string
  input: string | object
  actual_output: string | object
  expected_output: string | object | null
  actual_trace:
    messages: list[message] | null
    tool_calls: list[tool_call] | null
    spans: list[span] | null
  expected_trace:
    messages: list[message] | null
    tool_calls: list[tool_call] | null
  rubric: string
  metadata:
    agent_name: string
    model: string
    dataset: string
    run_id: string
```

Adapters:

```text
OpenEvals blackbox:
  EvalCase.input/output/expected/rubric
  -> create_llm_as_judge(...)

OpenEvals golden:
  EvalCase.actual_trace.messages / expected_trace.messages
  -> create_trajectory_match_evaluator(...)
  -> create_trajectory_llm_as_judge(...)

DeepEval blackbox:
  EvalCase.input/output/expected/rubric
  -> LLMTestCase(...)
  -> GEval(...)

DeepEval golden:
  EvalCase.actual_trace.tool_calls / expected_trace.tool_calls
  -> ToolCorrectnessMetric(...)

DeepEval golden LLM-as-judge:
  EvalCase.actual_trace serialized with observations + final answer
  -> LLMTestCase(actual_output=serialized_trace, expected_output=expected_path)
  -> GEval(...)
```

Такой контракт позволяет:

- хранить raw trace один раз;
- запускать несколько eval-библиотек поверх одного case;
- не терять tool observations;
- сравнивать deterministic и LLM-as-judge результаты;
- не переписывать платформу, если later поменяется preferred eval engine.

## Что улучшить дальше

1. Расширить OpenEvals adapter до full transcript: добавить `user`, `tool` messages с observations и финальный `assistant` answer, а не только assistant `tool_calls`.
2. Добавить negative test cases:
   - агент не вызвал `get_weather_forecast`;
   - агент вызвал tools в неправильном порядке;
   - агент дал хороший текст, но не grounded в observation;
   - агент вызвал лишний tool.
3. Прогнать multi-turn scenario, потому DeepEval и OpenEvals оба имеют conversation/multi-turn capabilities.
4. Если платформа реально будет на OTEL, сделать отдельный spike:
   - export trace через OTEL;
   - завести один eval run в LangSmith;
   - завести один eval run в Confident AI;
   - сравнить, где меньше glue-кода для production path.

## Команды воспроизведения

```bash
cd /Users/aogabbasov/evals
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,eval]"
.venv/bin/python -m pytest -q
.venv/bin/python -m evals_agent.runners.run_openevals --agent weather
.venv/bin/python -m evals_agent.runners.run_deepeval --agent weather
.venv/bin/python -m evals_agent.runners.collect_research_snapshot
.venv/bin/python -m evals_agent.runners.build_comparison
```

Live LLM runs требуют локальный `.env`:

```text
FM_API_KEY=<cloud.ru foundation models key>
```

Секреты в artifacts не пишутся.

## Источники

- OpenEvals repo: https://github.com/langchain-ai/openevals
- OpenEvals LLM-as-judge: https://github.com/langchain-ai/openevals#llm-as-judge
- OpenEvals trajectory LLM-as-judge: https://github.com/langchain-ai/openevals#trajectory-llm-as-judge
- DeepEval repo: https://github.com/confident-ai/deepeval
- DeepEval test cases: https://deepeval.com/docs/evaluation-test-cases
- DeepEval G-Eval: https://deepeval.com/docs/metrics-llm-evals
- DeepEval Tool Correctness: https://deepeval.com/docs/metrics-tool-correctness
- DeepEval tracing: https://deepeval.com/docs/evaluation-llm-tracing
- Confident AI tracing quickstart / OTEL note: https://www.confident-ai.com/docs/llm-tracing/quickstart
- LangSmith OpenTelemetry evaluation: https://docs.langchain.com/langsmith/evaluate-with-opentelemetry
- LangSmith OpenTelemetry tracing: https://docs.langchain.com/langsmith/trace-with-opentelemetry
- Open-Meteo docs: https://open-meteo.com/en/docs
