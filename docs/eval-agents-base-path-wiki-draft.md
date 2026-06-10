# [Eval Agents] Оценка решений для base path Eval

Дата среза: 2026-06-05. Независимая перепроверка: 2026-06-10.

Статус: wiki-ready draft. Страницу в wiki пока не создавал; документ можно переносить как дочернюю страницу.

Что сделано при перепроверке 2026-06-10 (вторым агентом, с нуля):

- Перечитан весь код раннеров/адаптеров, прогнаны все unit-тесты (28 passed).
- Заново выполнены оба live-прогона 2x2 — результаты воспроизвелись: тот же tool path, все 4 варианта pass. Свежие артефакты: `artifacts/openevals/20260610T071859Z.json`, `artifacts/deepeval/20260610T071951Z.json`.
- Community-статистика собрана заново и независимо сверена прямыми запросами к GitHub API.
- OTEL-выводы переведены из doc-based в code-based: проверены исходники установленных пакетов `deepeval==4.0.5` и `openevals==0.2.0` (детали в разделе про OpenTelemetry).
- Добавлен и прогнан negative case — «агент-симулянт» с правдоподобным выдуманным прогнозом: Blackbox-судьи обеих библиотек поставили pass, все Golden Path-проверки поймали подлог. Это главный пробел первой версии — теперь закрыт live-прогоном.
- Добавлен разбор G-Eval «с нуля» по исходникам DeepEval, включая нюанс с logprob-взвешиванием, который не работает с кастомными judge-моделями.

## Краткий вывод

Рекомендация: **DeepEval как единственный обязательный base path платформы**.

OpenEvals не нужен как обязательная зависимость. Его стоит подсветить как библиотеку с более нативной ergonomics для Golden Path / reference trajectory, но функционально этот сценарий закрывается в DeepEval через `ToolCorrectnessMetric` и `GEval` над serialized trace.

Почему так:

- DeepEval выигрывает по community support: сильно больше stars/forks, активнее релизы, больше contributor surface.
- DeepEval шире как eval platform: `GEval`, DAG/custom metrics, RAG, agentic metrics, multi-turn, MCP, tracing, component-level evals.
- DeepEval ближе к tracing/eval harness: есть собственный tracing layer и Confident AI path. Перепроверка 2026-06-10 подтвердила это на уровне кода: в пакете `deepeval` физически лежит OTEL-слой (`deepeval/tracing/otel/` с `ConfidentSpanExporter`, понимающим `gen_ai.*` semconv-атрибуты) и готовые инструментаторы для langchain, llama_index, pydantic_ai, crewai, google_adk, strands, agentcore, openinference. В `openevals` упоминаний opentelemetry ноль — его OTEL-путь живёт целиком в LangSmith. Live OTEL export end-to-end по-прежнему не прогонялся (нужен отдельный spike).
- OpenEvals удобнее именно для Golden Path trajectory: `create_trajectory_match_evaluator` и `create_trajectory_llm_as_judge` принимают agent trajectory как first-class input. Это плюс по ergonomics, но не blocker для DeepEval-only выбора.

Практический выбор:

```text
Base path: DeepEval
OpenEvals: optional, не обязательная зависимость
Default judge в тестах: deepseek-ai/DeepSeek-V4-Pro через Cloud.ru FM API
Agent-under-test в live-прогоне: moonshotai/Kimi-K2.6
```

Важно: это не значит, что OpenEvals плохой. Для Golden Path он оказался самым прямым и понятным. Но в production-решении его ценность не перевешивает дополнительную обязательную зависимость: DeepEval закрывает те же positive/negative кейсы.

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

- `artifacts/openevals/20260605T124343Z.json` - оригинальный прогон 2026-06-05
- `artifacts/deepeval/20260605T124504Z.json` - оригинальный прогон 2026-06-05
- `artifacts/openevals/20260610T071859Z.json` - независимое воспроизведение 2026-06-10
- `artifacts/deepeval/20260610T071951Z.json` - независимое воспроизведение 2026-06-10
- `artifacts/negative/20260610T072334Z.json` - negative cases (агент-симулянт), 2026-06-10
- `artifacts/comparison/eval_agents_weather_matrix_20260610T072414Z.json` - актуальная сводная матрица
- `artifacts/comparison/research_snapshot.json` - community snapshot 2026-06-10

Оба полных прогона (5 и 10 июня) сохранены сознательно: воспроизведение спустя 5 дней дало тот же tool path (`geocode_location -> get_weather_forecast`) и те же вердикты 4/4 pass. Воспроизводимость результата - сама по себе результат проверки.

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
artifacts/comparison/eval_agents_weather_matrix_20260610T072414Z.json
```

Итог по тесту: обе библиотеки умеют закрыть оба сценария. Разница не в том, "можно или нельзя", а в том, насколько это native, расширяемо и удобно поддерживать на платформе.

## Negative case: агент-симулянт, или зачем вообще нужен Golden Path

Положительный прогон выше доказывает только "хороший агент проходит eval". Этого мало:
главный риск agentic-систем - агент, который **не сделал работу, но красиво ответил**.
Поэтому 2026-06-10 добавлен прогон с подложными run-ами (`run_negative_cases.py`):
финальный ответ - правдоподобный, уверенный и полностью выдуманный план погоды
("June 10: light rain, 11-17 C, breezy..."), при этом обязательный
`get_weather_forecast` не вызывался вообще.

Два варианта:

- `skipped_forecast` - агент вызвал только `geocode_location`, прогноз сочинил;
- `no_tools` - агент не вызвал ни одного tool, всё сочинил.

Результат (артефакт `artifacts/negative/20260610T072334Z.json`):

| Проверка | Тип | skipped_forecast | no_tools |
|---|---|---:|---:|
| OpenEvals `trajectory_match` (strict) | Golden, deterministic | **fail** | **fail** |
| OpenEvals `trajectory_llm_as_judge` | Golden, LLM | **fail** | **fail** |
| OpenEvals `llm_as_judge` (blackbox) | Blackbox, LLM | pass (!) | pass (!) |
| DeepEval `ToolCorrectnessMetric` | Golden, deterministic | **fail** (0.0) | **fail** (0.0) |
| DeepEval `GEval` trajectory | Golden, LLM | **fail** (0.0) | **fail** (0.0) |
| DeepEval `GEval` blackbox | Blackbox, LLM | pass (!) (1.0) | pass (!) (1.0) |

Оба Blackbox-судьи честно "купились" - и это **корректное поведение**, а не баг:
blackbox видит только input, финальный ответ и expectation, выдуманные 11-17 C для
него неотличимы от настоящих. Комментарий DeepEval blackbox-судьи на фейковый ответ:

```text
The response directly addresses the request with a concise 3-day weather plan,
includes specific dates, temperatures, precipitation, and wind details...
It is consistent, not vague, and meets all evaluation criteria.
```

А вот Golden Path-судья (DeepEval GEval над сериализованным trace) тот же самый ответ
зарубил с правильной формулировкой:

```text
The actual output only calls geocode_location and omits the required
get_weather_forecast tool. The final weather plan contains specific temperature,
wind, and condition details that are not supported by any forecast observations,
violating the expected golden path and evidence-gathering steps.
```

OpenEvals trajectory judge - аналогично:

```text
The actual trajectory only performs the geocoding step and stops, missing the
weather forecast call entirely. This is not semantically equivalent to the reference.
```

Выводы для платформы:

1. Blackbox и Golden Path - не "два варианта одного и того же", а два разных
   детектора с непересекающимися слепыми зонами. Платформе нужны оба, и именно
   поэтому в ТЗ они зафиксированы как два отдельных сценария.
2. Обе библиотеки одинаково надёжно поймали оба negative-варианта на golden-уровне -
   и детерминированно (match/ToolCorrectness), и через LLM-судью. По способности
   ловить симулянта победителя нет.
3. Дешёвый детерминированный matcher (`trajectory_match` / `ToolCorrectnessMetric`)
   поймал всё то же, что и LLM-судья, бесплатно и без рисков нестабильности. Практика
   для платформы: сначала deterministic gate, LLM-судью - вторым эшелоном для
   нюансов (порядок обоснован? ответ grounded?).

Воспроизведение:

```bash
.venv/bin/python -m evals_agent.runners.run_negative_cases
```

## Главный вопрос: Golden Path, Blackbox и G-Eval

Коротко:

```text
Blackbox = сценарий оценки финального ответа
Golden Path = сценарий оценки пути/trace агента
G-Eval = метод LLM-as-judge в DeepEval (движок судейства, не сценарий)
```

Это понятия **разного уровня**, и в этом главная путаница. Blackbox и Golden Path
отвечают на вопрос "ЧТО мы оцениваем" (ответ или путь). G-Eval отвечает на вопрос
"КАК LLM-судья выставляет оценку". Поэтому G-Eval может обслуживать оба сценария:

- для Blackbox - в `LLMTestCase` кладём input, actual output и expected output;
- для Golden Path - в `LLMTestCase.actual_output` кладём serialized trace, в `expected_output` - expected path;
- для component-level eval - запускаем его внутри trace/span.

Полная таблица различий (по результатам live-прогонов, включая negative cases):

| | Blackbox LLM-as-Judge | Golden Path | G-Eval |
|---|---|---|---|
| Что это | Сценарий: судим финальный ответ | Сценарий: судим путь агента | Метод судейства в DeepEval: criteria -> чек-лист -> score |
| Что на вход | `input` + `actual_output` + expected/rubric | actual trajectory + reference trajectory | Любые текстовые поля `LLMTestCase`, разрешённые в `evaluation_params` |
| Что на выход | pass/fail или score + комментарий судьи | match bool / score + комментарий про tools и порядок | `score` 0..1 + `reason` + `success` (порог `threshold`) |
| С чем имеем дело | Только финальный текст. Не диалог, не trace | Trajectory/trace: tool calls, аргументы, порядок, observations | С тем текстом, который сам сериализовал в test case |
| Что ловит | Нерелевантный, пустой, вредный, не отвечающий на вопрос ответ | Пропущенный/лишний tool, неправильный порядок, ответ без evidence | Всё, что выразимо текстовым критерием над переданными полями |
| Слепая зона | Выдуманные "факты" и несделанные вызовы - наш negative case прошёл blackbox с score 1.0 | Качество финального текста (если судим только путь) | Не видит ничего, что не положили в поля test case |
| Цена | 1 LLM-вызов | 0 (deterministic match) или 1 LLM-вызов | 2 LLM-вызова (генерация шагов + вердикт), 1 - если шаги заданы руками |

## Что такое G-Eval: объяснение с нуля

### Идея на пальцах

Начнём с проблемы. Хочется оценивать ответы LLM/агента не строковым сравнением, а
"по смыслу". Очевидное решение - попросить другую LLM: "вот ответ, поставь оценку
от 0 до 10". Это и есть LLM-as-judge. Но в лоб это работает плохо:

- судья ставит оценки "на глазок" - сегодня 7, завтра за то же самое 9;
- критерий "ответ должен быть полезным" каждый раз интерпретируется по-новому;
- оценки кучкуются: модель почти всегда ставит 7-8, различить "хорошо" и "отлично" нельзя.

G-Eval - это рецепт (из статьи Liu et al., 2023, arXiv:2303.16634, EMNLP 2023), как
сделать LLM-судью дисциплинированным. Аналогия: ты - завкафедрой, нанимаешь
экзаменатора (LLM-судью) и даёшь ему ТЗ одной фразой: "оцени, насколько ответ
студента полный и обоснованный". Дальше два варианта:

- Плохой экзаменатор читает ответ и ставит оценку по настроению.
- Хороший - сначала превращает твою фразу в чек-лист ("1. все даты упомянуты,
  2. есть цифры температуры, 3. есть практический совет"), потом проходит по
  чек-листу пункт за пунктом и только потом ставит балл.

G-Eval заставляет любую LLM быть вторым типом экзаменатора. Плюс один трюк со
статистикой, чтобы оценка была дробной и стабильной (про него ниже).

### Как это реально работает в DeepEval (проверено по исходникам 4.0.5)

Когда вызываешь `metric.measure(test_case)`, под капотом происходит следующее:

**Шаг 1. Критерий превращается в чек-лист (auto chain-of-thought).**
Если ты передал только `criteria` (одну фразу), G-Eval делает отдельный LLM-вызов:
"вот критерий, сгенерируй 3-4 evaluation steps". Получается JSON со списком шагов.
Если передать `evaluation_steps` руками - этот вызов пропускается (и судья
становится детерминированнее: чек-лист зафиксирован тобой, а не генерируется заново).

**Шаг 2. Сборка промпта судьи.**
В промпт попадают: нумерованный чек-лист + те и только те поля test case, которые
ты разрешил в `evaluation_params` (например INPUT, ACTUAL_OUTPUT, EXPECTED_OUTPUT).
Судью просят вернуть строгий JSON: `{"score": целое 0-10, "reason": "..."}`.

**Шаг 3. Трюк с вероятностями токенов (probability-weighted score).**
Проблема: LLM выдаёт целые числа, и они кучкуются. Решение из статьи: смотрим не
только на то, какой score-токен модель выдала, а на **вероятности всех числовых
токенов-кандидатов** (top-20 logprobs, отсекая всё с вероятностью < 1%). Если модель
колебалась "8 с вероятностью 0.6 или 9 с вероятностью 0.4", итоговый score будет
не 8, а 0.6*8 + 0.4*9 = 8.4. Получаем непрерывную шкалу и меньше дребезга.

**Шаг 4. Нормализация и порог.**
Сырой score из диапазона 0-10 нормализуется в 0..1: `(score - min) / (max - min)`.
Дальше `success = score >= threshold` (default 0.5).

Важный нюанс, найденный при перепроверке: **шаг 3 работает только с нативными
моделями DeepEval** (OpenAI и совместимые, у которых движок может запросить
`top_logprobs`). Для кастомной judge-модели (наш `CloudRuFMJudgeModel` поверх
Cloud.ru FM API) ветка с logprobs недоступна - DeepEval тихо откатывается на сырой
целочисленный score. Поэтому в наших артефактах score всегда ровно 1.0 или 0.0, а
не 0.87. Для платформы это значит: с self-hosted/FM-судьёй G-Eval становится грубее
(11 дискретных значений вместо непрерывной шкалы) - это надо учитывать при выборе
threshold.

Дополнительные режимы:

- `strict_mode=True` - бинарный судья: только 0 или 1, без шкалы;
- `rubric=[...]` - явная таблица "диапазон score -> что он значит" вместо свободной шкалы;
- `evaluation_steps=[...]` - зафиксировать чек-лист руками (рекомендую для production: воспроизводимее и на 1 LLM-вызов дешевле).

### Минимальный код

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

test_case = LLMTestCase(
    input="Give me a short weather plan for Moscow for 3 days.",
    actual_output="June 10: partly cloudy, 12-24 C, no rain...",
    expected_output="A concise plan grounded in forecast data with dates and advice.",
)

metric = GEval(
    name="Blackbox Quality",
    # вариант 1: одна фраза - шаги сгенерирует LLM (+1 вызов)
    criteria="Answer must mention dates, temperatures and practical advice.",
    # вариант 2 (production): зафиксировать чек-лист руками, вызова не будет
    # evaluation_steps=[
    #     "Check that every forecast day has a date.",
    #     "Check that temperatures and precipitation are mentioned.",
    #     "Check that the answer gives practical recommendations.",
    # ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model="gpt-4.1",   # или свой DeepEvalBaseLLM
    threshold=0.5,
)

metric.measure(test_case)
print(metric.score)    # 0..1, например 0.84
print(metric.reason)   # текстовое объяснение судьи
print(metric.success)  # score >= threshold
```

Что произойдёт под капотом для варианта 1:

```text
LLM call #1: "criteria -> сгенерируй 3-4 evaluation steps"   (auto-CoT)
LLM call #2: "вот steps + поля test case -> JSON {score: 0-10, reason}"
score 8 -> (опционально logprob-взвешивание -> 8.4) -> нормализация -> 0.84
0.84 >= 0.5 -> success = True
```

### Чем G-Eval НЕ является

- Это не отдельный сценарий оценки уровня платформы. Сценарии - Blackbox и Golden
  Path. G-Eval - движок, которым можно реализовать судейство в обоих.
- Это не "умный анализатор агента". G-Eval не знает, что такое tool call, trace или
  диалог. Он видит ровно те текстовые поля, которые ты положил в `LLMTestCase` и
  разрешил в `evaluation_params`. Хочешь судить путь агента - сам сериализуй trace
  в текст (что мы и делаем в `trajectory_g_eval`).
- Это не гарантия объективности. Это способ снизить дисперсию и привязать оценку к
  чек-листу. Судья всё ещё LLM: на negative case наш blackbox G-Eval честно поставил
  1.0 выдуманному прогнозу, потому что по переданным ему полям ответ был безупречен.

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

## Как это выглядит кодом: общий слой платформы

Чтобы не привязать платформу к формату одной библиотеки, полезно мыслить так:

```text
agent run
  -> neutral EvalCase
  -> openevals adapter
  -> deepeval adapter
  -> normalized result JSON
```

То есть агент один раз выполняет задачу, а дальше его результат раскладывается в разные eval-форматы.

### 1. Что возвращает агент

В нашем тесте агент возвращает не только текст, а run с trace:

```python
@dataclass(frozen=True)
class TraceStep:
    tool_name: str
    arguments: dict[str, Any]
    observation: dict[str, Any]


@dataclass(frozen=True)
class AgentRun:
    input: str
    trace: list[TraceStep]
    final_answer: FinalAnswer
    metadata: dict[str, Any]
```

Для weather agent это примерно такой объект:

```python
agent_run = AgentRun(
    input="Give me a short weather plan for Moscow, Russia for the next 3 days.",
    trace=[
        TraceStep(
            tool_name="geocode_location",
            arguments={"location": "Moscow, Russia"},
            observation={
                "status": "ok",
                "name": "Moscow",
                "country": "Russia",
                "latitude": 55.75204,
                "longitude": 37.61781,
                "timezone": "Europe/Moscow",
            },
        ),
        TraceStep(
            tool_name="get_weather_forecast",
            arguments={
                "latitude": 55.75204,
                "longitude": 37.61781,
                "forecast_days": 3,
            },
            observation={
                "status": "ok",
                "forecast": [
                    {
                        "date": "2026-06-05",
                        "condition": "partly_cloudy",
                        "temperature_max_c": 23.9,
                        "temperature_min_c": 12.4,
                        "precipitation_mm": 0.0,
                    }
                ],
            },
        ),
    ],
    final_answer=FinalAnswer(
        recommended_repo="weather_plan",
        rationale="Weather answer generated from Open-Meteo observations.",
        evidence=[],
    ),
    metadata={
        "agent_type": "weather_llm",
        "model": "moonshotai/Kimi-K2.6",
        "answer_text": "June 5: partly cloudy, 12-24 C, no rain...",
    },
)
```

Главная идея: **eval не должен парсить stdout агента**. Агент должен отдавать структурированный run: input, final answer, trace, metadata.

### 2. Нейтральный EvalCase

Внутри платформы я бы не хранил отдельно "OpenEvals case" и "DeepEval case". Лучше иметь один нейтральный объект:

```python
@dataclass(frozen=True)
class EvalToolCall:
    name: str
    arguments: dict[str, Any]
    observation: dict[str, Any] | None = None


@dataclass(frozen=True)
class EvalCase:
    input: str
    actual_output: str
    expected_output: str
    rubric: str
    actual_tools: list[EvalToolCall]
    expected_tools: list[EvalToolCall]
    metadata: dict[str, Any]
```

Для weather agent сборка выглядит так:

```python
def build_weather_eval_case(run: AgentRun) -> EvalCase:
    actual_tools = [
        EvalToolCall(
            name=step.tool_name,
            arguments=step.arguments,
            observation=step.observation,
        )
        for step in run.trace
    ]

    expected_tools = [
        EvalToolCall(name="geocode_location", arguments={"location": "Moscow, Russia"}),
        EvalToolCall(
            name="get_weather_forecast",
            arguments={
                "latitude": 55.75204,
                "longitude": 37.61781,
                "forecast_days": 3,
            },
        ),
    ]

    return EvalCase(
        input=run.input,
        actual_output=final_answer_text(run),
        expected_output=(
            "The answer should provide a concise weather plan grounded in the "
            "forecast returned by tools, mention dates and weather evidence, "
            "and include practical advice."
        ),
        rubric=(
            "Judge only the user input, final answer, and reference expectation. "
            "The answer should mention forecast dates, temperature, precipitation "
            "or wind evidence, and practical recommendations."
        ),
        actual_tools=actual_tools,
        expected_tools=expected_tools,
        metadata={
            "agent": "weather",
            "model": run.metadata["model"],
            "scenario": "weather_3_day_plan",
        },
    )
```

На этом уровне еще нет ни OpenEvals, ни DeepEval. Это просто внутренний контракт платформы.

### 3. OpenEvals Blackbox adapter

Blackbox для OpenEvals получает только input/output/reference/rubric:

```python
def run_openevals_blackbox(case: EvalCase, judge, model: str) -> dict:
    evaluator = create_llm_as_judge(
        prompt=(
            case.rubric
            + "\nInputs:\n{inputs}"
            + "\nOutputs:\n{outputs}"
            + "\nReference:\n{reference_outputs}"
        ),
        judge=judge,
        model=model,
        feedback_key="blackbox_quality",
    )

    raw_result = evaluator(
        inputs=case.input,
        outputs=case.actual_output,
        reference_outputs=case.expected_output,
    )

    return normalize_eval_result(raw_result)
```

Что реально уходит в evaluator:

```python
{
    "inputs": "Give me a short weather plan for Moscow...",
    "outputs": "June 5: partly cloudy, 12-24 C, no rain...",
    "reference_outputs": "The answer should provide a concise weather plan...",
}
```

Что возвращается в JSON-артефакт:

```json
{
  "key": "blackbox_quality",
  "score": true,
  "comment": "The final answer provides a concise 3-day weather plan...",
  "metadata": null
}
```

### 4. OpenEvals Golden Path adapter

OpenEvals trajectory evaluator хочет OpenAI-style messages с `tool_calls`.

Adapter из `EvalCase.actual_tools`:

```python
def to_openevals_tool_messages(tools: list[EvalToolCall], call_id_prefix: str) -> list[dict]:
    messages = []
    for index, tool in enumerate(tools):
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"{call_id_prefix}_{index}",
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "arguments": json.dumps(
                                tool.arguments,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        },
                    }
                ],
            }
        )
    return messages
```

Сам eval:

```python
def run_openevals_golden(case: EvalCase, judge, model: str) -> dict:
    outputs = to_openevals_tool_messages(case.actual_tools, "call")
    reference_outputs = to_openevals_tool_messages(case.expected_tools, "ref_call")

    deterministic_match = create_trajectory_match_evaluator(
        trajectory_match_mode="strict",
        tool_args_match_mode="ignore",
    )

    llm_judge = create_trajectory_llm_as_judge(
        judge=judge,
        model=model,
    )

    return {
        "trajectory_match": normalize_eval_result(
            deterministic_match(
                outputs=outputs,
                reference_outputs=reference_outputs,
            )
        ),
        "trajectory_llm_as_judge": normalize_eval_result(
            llm_judge(
                outputs=outputs,
                reference_outputs=reference_outputs,
            )
        ),
    }
```

Что реально сравнивается:

```python
actual = [
    {"tool": "geocode_location", "arguments": {"location": "Moscow, Russia"}},
    {"tool": "get_weather_forecast", "arguments": {"latitude": 55.75204, "longitude": 37.61781}},
]

expected = [
    {"tool": "geocode_location", "arguments": {"location": "Moscow, Russia"}},
    {"tool": "get_weather_forecast", "arguments": {"latitude": 55.75204, "longitude": 37.61781}},
]
```

Выход:

```json
{
  "trajectory_match": {
    "key": "trajectory_strict_match",
    "score": true,
    "comment": null
  },
  "trajectory_llm_as_judge": {
    "key": "trajectory_accuracy",
    "score": true,
    "comment": "The actual trajectory is identical to the reference trajectory..."
  }
}
```

### 5. DeepEval Blackbox adapter

DeepEval blackbox превращает тот же `EvalCase` в `LLMTestCase`:

```python
def run_deepeval_blackbox(case: EvalCase, judge_model) -> dict:
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
        async_mode=False,
    )

    score = metric.measure(
        test_case,
        _show_indicator=False,
        _log_metric_to_confident=False,
    )

    return {
        "score": score,
        "success": bool(metric.success),
        "reason": metric.reason,
        "threshold": metric.threshold,
    }
```

Что уходит в DeepEval:

```python
LLMTestCase(
    input="Give me a short weather plan for Moscow...",
    actual_output="June 5: partly cloudy, 12-24 C, no rain...",
    expected_output="The answer should provide a concise weather plan...",
)
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

### 6. DeepEval Golden Path adapter

Для deterministic tool correctness нужен `ToolCall[]`:

```python
def to_deepeval_tool_call(tool: EvalToolCall) -> ToolCall:
    return ToolCall(
        name=tool.name,
        input_parameters=tool.arguments,
        output=tool.observation,
    )


def run_deepeval_tool_correctness(case: EvalCase) -> dict:
    test_case = LLMTestCase(
        input=case.input,
        actual_output=case.actual_output,
        expected_output=case.expected_output,
        tools_called=[to_deepeval_tool_call(tool) for tool in case.actual_tools],
        expected_tools=[to_deepeval_tool_call(tool) for tool in case.expected_tools],
    )

    metric = ToolCorrectnessMetric(
        threshold=1.0,
        model=NoopJudgeModel(),
        async_mode=False,
        include_reason=True,
        should_exact_match=True,
        should_consider_ordering=True,
    )

    score = metric.measure(
        test_case,
        _show_indicator=False,
        _log_metric_to_confident=False,
    )

    return {
        "score": score,
        "success": bool(metric.success),
        "reason": metric.reason,
        "threshold": metric.threshold,
    }
```

Для LLM-as-judge по Golden Path в DeepEval trace надо сериализовать:

```python
def serialize_trace(case: EvalCase) -> str:
    lines = []
    for index, tool in enumerate(case.actual_tools, start=1):
        lines.append(
            f"{index}. {tool.name} "
            f"args={json.dumps(tool.arguments, ensure_ascii=False, sort_keys=True)} "
            f"observation={json.dumps(tool.observation, ensure_ascii=False, sort_keys=True)}"
        )
    return "\n".join(lines)


def run_deepeval_golden_llm(case: EvalCase, judge_model) -> dict:
    trajectory_case = LLMTestCase(
        input=case.input,
        actual_output=(
            "Actual trajectory:\n"
            f"{serialize_trace(case)}\n\n"
            "Final answer:\n"
            f"{case.actual_output}"
        ),
        expected_output=(
            "Expected golden path: geocode_location -> get_weather_forecast. "
            "The agent should geocode the requested location before fetching "
            "the weather forecast and should ground the final answer in forecast observations."
        ),
    )

    metric = GEval(
        name="Golden Path Trajectory",
        criteria=(
            "Score whether the actual agent trajectory follows the expected golden path. "
            "Consider tool order, missing or extra tool calls, evidence gathering, "
            "and whether the final answer is grounded in tool observations."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge_model,
        threshold=0.5,
        async_mode=False,
    )

    score = metric.measure(
        trajectory_case,
        _show_indicator=False,
        _log_metric_to_confident=False,
    )

    return {
        "score": score,
        "success": bool(metric.success),
        "reason": metric.reason,
        "threshold": metric.threshold,
    }
```

### 7. Единый запуск 2x2

В итоге вся обвязка выглядит так:

```python
def run_eval_matrix(task: str) -> dict:
    agent_run = run_weather_agent(task)
    case = build_weather_eval_case(agent_run)

    judge_config = resolve_judge_config()
    openevals_judge = build_openevals_judge(judge_config)
    deepeval_judge = CloudRuFMJudgeModel(judge_config)

    return {
        "openevals_golden_path_llm_as_judge": run_openevals_golden(
            case=case,
            judge=openevals_judge,
            model=judge_config.model,
        ),
        "openevals_blackbox_llm_as_judge": run_openevals_blackbox(
            case=case,
            judge=openevals_judge,
            model=judge_config.model,
        ),
        "deepeval_golden_path_llm_as_judge": {
            "tool_correctness": run_deepeval_tool_correctness(case),
            "trajectory_g_eval": run_deepeval_golden_llm(
                case=case,
                judge_model=deepeval_judge,
            ),
        },
        "deepeval_blackbox_llm_as_judge": run_deepeval_blackbox(
            case=case,
            judge_model=deepeval_judge,
        ),
    }
```

Ключевой практический вывод из кода:

```text
Blackbox adapter = берет input + final answer + expected answer + rubric.
Golden adapter = берет actual trace + expected trace.
OpenEvals Golden = trace уже native input.
DeepEval Golden = trace надо превратить в ToolCall[] или serialized text.
```

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

Оценка удобства: **отлично для Golden Path**. Это самый прямой API среди двух библиотек для reference trajectory. Но это аргумент про ergonomics, а не про обязательную зависимость: DeepEval закрывает тот же функциональный сценарий через `ToolCorrectnessMetric` и `GEval`, поэтому OpenEvals можно добавить позже только при явной выгоде по поддержке.

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

Snapshot из GitHub/PyPI на 2026-06-10T07:19:51Z (собран раннером и независимо сверен
прямыми запросами к GitHub API - цифры совпали):

| Библиотека | Stars | Forks | Последний push | PyPI version | PyPI releases | Последний релиз |
|---|---:|---:|---|---|---:|---|
| OpenEvals | 1,070 | 98 | 2026-06-07 | 0.2.0 | 60 | 2026-04-07 |
| DeepEval | 16,063 | 1,514 | 2026-06-09 | 4.0.5 | 502 | 2026-05-28 |

Динамика между двумя срезами (5 дней): DeepEval +132 stars, OpenEvals +2. Темп
релизов тоже разный: у DeepEval три релиза только за май (4.0.2 -> 4.0.3 -> 4.0.5),
у OpenEvals последний релиз 0.2.0 - 7 апреля.

Вывод: **DeepEval выигрывает community support с большим отрывом**, и разрыв растёт.

OpenEvals моложе (создан 2025-02) и развивается, но по зрелости сообщества DeepEval
(создан 2023-08) сейчас сильнее. Нюанс для честности: у DeepEval 284 открытых
issues+PRs против 9 у OpenEvals - это следствие масштаба, но и сигнал, что
поверхность библиотеки большая и не всё в ней одинаково вылизано.

## Гибкость eval-сценариев

При перепроверке оба пакета проинспектированы по факту установленного кода, а не
только по README. Точные цифры по `deepeval==4.0.5`: **51 класс метрик** в
`deepeval.metrics`. У `openevals==0.2.0` модули: `llm`, `trajectory`, `exact`,
`json`, `string`, `code`, `simulators` - компактный набор фабрик evaluator-функций
(у каждой есть sync и async вариант).

OpenEvals хорошо закрывает:

- blackbox LLM-as-judge (`create_llm_as_judge` + custom prompts);
- structured output evals;
- RAG-style prompts;
- code evals (`openevals.code`: LLM-судья по коду, статика pyright/mypy, sandbox-исполнение через E2B);
- exact match / Levenshtein / embedding similarity;
- agent trajectory match (4 режима: strict/unordered/subset/superset + режимы сравнения аргументов);
- agent trajectory LLM-as-judge;
- **multiturn-симуляция пользователя** (`run_multiturn_simulation`, `create_llm_simulated_user`) - в первой версии статьи это было пропущено: OpenEvals умеет не только судить диалог, но и генерировать его симулированным пользователем;
- async-варианты всех evaluator-ов;
- рядом живёт sister-пакет `agentevals` с graph trajectory evaluator-ами для LangGraph.

DeepEval закрывает:

- `GEval` / `ConversationalGEval` / `ArenaGEval` (попарное сравнение кандидатов);
- DAG/custom metrics (`DAGMetric`, `ConversationalDAGMetric` - деревья решений из узлов-судей);
- RAG metrics (AnswerRelevancy, Faithfulness, Contextual Precision/Recall/Relevancy);
- **выделенные agentic-метрики** - в первой версии статьи они были упомянуты одной строкой, по факту это отдельный пласт: `TaskCompletionMetric`, `PlanAdherenceMetric`, `PlanQualityMetric`, `StepEfficiencyMetric`, `GoalAccuracyMetric`, `ArgumentCorrectnessMetric`, `ToolUseMetric`, `ToolCorrectnessMetric`;
- MCP evaluation (`MCPTaskCompletionMetric`, `MCPUseMetric`, `MultiTurnMCPUseMetric`);
- multi-turn / conversational metrics (RoleAdherence, KnowledgeRetention, ConversationCompleteness, TopicAdherence...);
- safety-метрики (Bias, Toxicity, PIILeakage, Misuse, NonAdvice, RoleViolation);
- synthetic data / goldens (Synthesizer);
- tracing + component-level evals (метрики на уровне span);
- CLI reports / inspect flow;
- Confident AI online evaluation path.

Важная оговорка про agentic-метрики DeepEval: самые интересные из них
(например `TaskCompletionMetric`) имеют `requires_trace = True` - они считаются не
над плоским `LLMTestCase`, а над trace, собранным через `@observe`-инструментацию
DeepEval. То есть глубокая agentic-история DeepEval тянет за собой его tracing-слой.
Это одновременно и сила (full trace доступен метрикам автоматически), и связывание
с экосистемой DeepEval/Confident AI. В нашем тесте мы сознательно шли через плоский
`LLMTestCase` + сериализованный trace, чтобы не инструментировать агента.

Вывод прежний и усилившийся: **DeepEval гибче как base path**. OpenEvals очень хорош
как evaluator package (и единственный из двух умеет симулировать пользователя в
multiturn из коробки), но DeepEval - полноценный eval harness.

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

При перепроверке 2026-06-10 это проверено не по докам, а по исходникам установленного
пакета `deepeval==4.0.5`:

- В пакете физически есть OTEL-слой: `deepeval/tracing/otel/` с классом
  `ConfidentSpanExporter(SpanExporter)` - это полноценный OpenTelemetry
  span exporter, который маппит OTel-спаны (включая стандартные `gen_ai.*`
  semantic conventions: модель, tool name, input/output) в типизированные
  deepeval-спаны (`AgentSpan`, `LlmSpan`, `ToolSpan`, `RetrieverSpan`).
- Рядом лежат готовые инструментаторы интеграций: `langchain`, `llama_index`,
  `pydantic_ai`, `crewai`, `google_adk`, `strands`, `agentcore`, `hugging_face`,
  `openinference` (`deepeval/integrations/`).
- В `openevals==0.2.0` grep по `opentelemetry` даёт **ноль вхождений** - OTEL-путь
  экосистемы LangChain живёт целиком на стороне LangSmith, сам пакет evaluator-ов
  к трейсингу не прикасается.

Практический смысл:

```text
DeepEval -> metric engine + tracing primitives + OTel SpanExporter в самом пакете
Confident AI -> trace UI / online evals / OTEL ingestion
OpenEvals -> только evaluator-функции; trace-инфраструктура = LangSmith
```

Важная честная оговорка: `ConfidentSpanExporter` экспортирует спаны в **Confident AI**
(SaaS-платформу авторов DeepEval), а не в произвольный OTLP-backend. Если платформа
хочет складывать трейсы в свой Jaeger/Tempo/ClickHouse и судить их там - из коробки
этого не даёт ни одна из двух библиотек; понадобится свой OTLP-pipeline, а DeepEval
использовать как metric engine поверх него. Вывод по критерию остаётся прежним:
**DeepEval сильнее по tracing/OTEL-стори, теперь это подтверждено на уровне кода**,
но live end-to-end OTEL export в этом R&D по-прежнему не прогонялся. Перед
production-решением нужен отдельный spike: instrument sample agent, export OTEL
traces, проверить linking trace/span/eval result и поведение при nested tool calls.
Если компания уже выбирает LangSmith как trace backend, OpenEvals можно рассмотреть
как optional adapter, но это не меняет выбора base path.

## Итоговая оценка по критериям ТЗ

| Критерий | Победитель | Почему |
|---|---|---|
| Поддержка сообществом | DeepEval | 16k vs 1k stars, старше проект, 3 релиза за последний месяц против релиза 2 месяца назад; разрыв растёт (+132 vs +2 stars за 5 дней). |
| Гибкость eval-сценариев | DeepEval | 51 класс метрик, включая agentic/MCP/conversational/safety пласты; у OpenEvals компактный набор evaluator-фабрик (но есть уникальная multiturn-симуляция пользователя). |
| OpenTelemetry/tracing story | DeepEval, подтверждено кодом | В пакете есть `ConfidentSpanExporter` (OTel SpanExporter с поддержкой `gen_ai.*` semconv) и 9 готовых инструментаторов; в openevals OTEL отсутствует полностью, его путь - LangSmith. Live e2e export не прогонялся. |
| Golden Path ergonomics | OpenEvals | Native trajectory APIs, меньше adapter-кода. |
| Blackbox ergonomics | Ничья / легкий плюс DeepEval для platform base | Оба удобны; DeepEval лучше ложится в единый `LLMTestCase` контракт. |
| Устойчивость к агенту-симулянту (negative case) | Ничья | Обе библиотеки поймали оба negative-варианта и deterministic-проверкой, и LLM-судьёй; оба blackbox-судьи одинаково "купились" (так и должно быть). |

Финальный выбор:

```text
DeepEval-only as required base path.
OpenEvals is optional for native golden/reference trajectory ergonomics.
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

Required adapter:

```text
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

Optional adapter, если ergonomics Golden Path станет важнее dependency budget:

```text
OpenEvals golden:
  EvalCase.actual_trace.messages / expected_trace.messages
  -> create_trajectory_match_evaluator(...)
  -> create_trajectory_llm_as_judge(...)
```

Такой контракт позволяет:

- хранить raw trace один раз;
- запускать DeepEval как основной eval engine поверх одного case;
- добавить OpenEvals позже без миграции внутреннего контракта, если это реально понадобится;
- не терять tool observations;
- сравнивать deterministic и LLM-as-judge результаты;
- не переписывать платформу, если позже появится причина добавить или заменить eval engine.

## Что улучшить дальше

1. Довести DeepEval-only adapter до production-формата: единый `EvalCase`, `ToolCall[]` для deterministic gate, serialized trace для `GEval`, нормализованный output.
2. ~~Добавить negative test cases~~ - **сделано 2026-06-10** для двух главных вариантов (`skipped_forecast`, `no_tools`), см. раздел "Negative case: агент-симулянт". Остались непрогнанными варианты "неправильный порядок tools" и "лишний tool" - детерминированные matchers поймают их по построению (strict mode сравнивает последовательность), но live-подтверждение с LLM-судьёй не делалось.
3. Прогнать multi-turn scenario на DeepEval conversational metrics; OpenEvals simulation можно проверить отдельно, но она не влияет на base-path выбор.
4. Если платформа реально будет на OTEL, сделать отдельный spike:
   - export trace через OTEL (у DeepEval - `ConfidentSpanExporter`, у LangChain-стека - LangSmith OTEL ingestion);
   - завести один eval run в LangSmith;
   - завести один eval run в Confident AI;
   - проверить, можно ли увести спаны в свой OTLP-backend (Jaeger/Tempo), минуя SaaS;
   - сравнить, где меньше glue-кода для production path.
5. Для production G-Eval: зафиксировать `evaluation_steps` руками (воспроизводимость + минус один LLM-вызов) и проверить судью на калибровочном наборе known-good/known-bad кейсов (заготовка уже есть в `src/evals_agent/calibration.py`, но она прогонялась только для фикстурного агента).

## Команды воспроизведения

```bash
cd /Users/aogabbasov/evals
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

Live LLM runs требуют локальный `.env`:

```text
FM_API_KEY=<cloud.ru foundation models key>
```

Секреты в artifacts не пишутся.

## Источники

- OpenEvals repo: https://github.com/langchain-ai/openevals
- OpenEvals LLM-as-judge: https://github.com/langchain-ai/openevals#llm-as-judge
- OpenEvals trajectory LLM-as-judge: https://github.com/langchain-ai/openevals#trajectory-llm-as-judge
- AgentEvals (graph trajectory для LangGraph): https://github.com/langchain-ai/agentevals
- G-Eval paper (Liu et al., 2023, EMNLP): https://arxiv.org/abs/2303.16634
- DeepEval repo: https://github.com/confident-ai/deepeval
- DeepEval test cases: https://deepeval.com/docs/evaluation-test-cases
- DeepEval G-Eval: https://deepeval.com/docs/metrics-llm-evals
- DeepEval Tool Correctness: https://deepeval.com/docs/metrics-tool-correctness
- DeepEval tracing: https://deepeval.com/docs/evaluation-llm-tracing
- Confident AI tracing quickstart / OTEL note: https://www.confident-ai.com/docs/llm-tracing/quickstart
- LangSmith OpenTelemetry evaluation: https://docs.langchain.com/langsmith/evaluate-with-opentelemetry
- LangSmith OpenTelemetry tracing: https://docs.langchain.com/langsmith/trace-with-opentelemetry
- Open-Meteo docs: https://open-meteo.com/en/docs
