# Eval Agents Library Selection Design

## Цель

Подготовить технический пакет для выбора библиотеки eval-оценки агентских решений в платформе, где есть два режима:

- Golden Path with LLM as Judge: оценка траектории агента относительно ожидаемого пути.
- Blackbox LLM as Judge: оценка финального ответа без опоры на внутренний trace.

Итоговый материал должен быть готов для переноса в wiki, но сама публикация в wiki не входит в этот workspace.

## Что считаем результатом

В результате должны появиться:

- локальный reproducible benchmark для `openevals` и `DeepEval`;
- минимум один тестовый агент, на котором можно прогнать оба класса оценок;
- зафиксированные команды запуска;
- артефакты прогонов в `artifacts/`;
- сравнительная таблица по критериям задачи;
- рекомендация, какая библиотека лучше подходит как base path для Eval Agents.

## Критерии выбора

Основные критерии:

1. Поддержка сообществом.
   Проверяем GitHub stars, forks, recent commits, releases, issues/PR activity, PyPI downloads или доступные аналоги.

2. Гибкость eval-сценариев.
   Проверяем поддержку blackbox LLM-as-judge, trajectory/tool-call evaluation, custom rubrics, structured outputs, sync/async usage, batch runs, интеграцию с CI и расширение своими метриками.

3. Интеграция с OpenTelemetry tracing.
   Проверяем, есть ли out-of-the-box OpenTelemetry/OpenInference/LangSmith/LangGraph trace integration, можно ли оценивать уже записанные traces, насколько много glue-code нужно платформе.

Вторичные критерии:

- простота установки и запуска;
- понятность API для платформенного wrapper-а;
- vendor lock-in;
- качество документации;
- стабильность контрактов и формат результатов.

## Библиотеки в сравнении

Обязательные:

- `openevals`
- `deepeval`

Опциональный третий кандидат добавляется только если он явно полезен для критерия tracing. Возможные кандидаты: `braintrust/autoevals`, Phoenix/OpenInference evals, LangSmith evaluators. Третий кандидат не должен размывать основной вывод по `openevals` vs `DeepEval`.

## Тестовый агент

Для воспроизводимости используем минимального локального агента без зависимости от внешних бизнес-систем.

Агент должен:

- принимать задачу пользователя;
- выбирать 1-3 инструмента из локального набора;
- возвращать финальный ответ;
- сохранять trace шагов в структурированном виде.

Базовый сценарий:

- пользователь просит найти подходящий репозиторий по требованиям;
- агент вызывает локальные tools `search_repos`, `inspect_repo`, `recommend_repo`;
- expected trajectory задает корректную последовательность действий;
- blackbox rubric проверяет качество финальной рекомендации.

Такой сценарий близок к Eval Agents: есть tool-use, промежуточные решения и финальная оценка качества.

## Golden Path Evaluation

Golden Path test проверяет не только финальный ответ, но и путь:

- вызваны ли нужные tools;
- не было ли запрещенного или лишнего tool call;
- соответствует ли порядок действий expected path;
- достаточно ли evidence собрано перед рекомендацией;
- совпадает ли финальная рекомендация с trace evidence.

Для `openevals` основной путь проверки: trajectory LLM-as-judge из документации LangChain.

Для `DeepEval` проверяем, можно ли выразить аналогичный сценарий через доступные metrics, custom metric или conversational/tool-call evaluation. Если нужен существенный custom wrapper, это фиксируется как минус по out-of-the-box trajectory support.

## Blackbox Evaluation

Blackbox test оценивает только вход и финальный ответ:

- ответил ли агент на вопрос;
- выбрал ли релевантный репозиторий;
- объяснил ли trade-offs;
- не выдумал ли факты;
- соблюден ли формат ответа.

Обе библиотеки должны пройти одинаковый rubric и одинаковые test cases.

## Артефакты

Планируемая структура:

```text
/Users/aogabbasov/evals/
  docs/
    eval-agents-library-selection-design.md
    eval-agents-library-selection-report.md
    eval-agents-implementation-plan.md
  src/
    evals_agent/
      agent.py
      fixtures.py
      trace_schema.py
      runners/
        run_openevals.py
        run_deepeval.py
  tests/
    test_agent_fixture.py
    test_openevals_runner.py
    test_deepeval_runner.py
  artifacts/
    openevals/
    deepeval/
    comparison/
```

## Исследовательский процесс

1. Проверить свежую документацию и репозитории.
   Нужен live research, потому что stars, releases, API и tracing-интеграции меняются.

2. Собрать минимальный benchmark.
   Цель - не production framework, а честный smoke/proof-of-use для обеих библиотек.

3. Прогнать blackbox eval.
   Зафиксировать setup, API friction, формат результата и качество судейства.

4. Прогнать golden path/trajectory eval.
   Зафиксировать, насколько нативно каждая библиотека работает с trajectory/tool-call trace.

5. Проверить tracing story.
   Отдельно описать, есть ли out-of-the-box OTel путь или требуется платформенный adapter.

6. Сформировать вывод.
   Победитель выбирается по совокупности критериев, а не по одному green test.

## Acceptance Criteria

Работа считается законченной, если:

- есть runnable команды для обоих eval runners;
- для каждой библиотеки есть хотя бы один успешный или осмысленно зафейленный прогон с артефактом;
- report содержит таблицу сравнения по всем основным критериям;
- recommendation объясняет, почему выбранная библиотека лучше подходит как base path;
- явно указаны риски, ограничения и объем glue-code для платформы;
- отдельно зафиксировано, трогались ли `.env` и внешние credentials.

## Границы

Не входит в текущую работу:

- публикация в wiki;
- production-интеграция в платформу;
- полноценная CI/CD матрица;
- сравнение всех существующих eval-фреймворков;
- оценка качества конкретных боевых агентов платформы, если пользователь отдельно не даст их repo.

## Основные риски

- У библиотек может быть разный уровень нативной поддержки trajectory eval, поэтому для честного сравнения нужно отделять "работает через custom wrapper" от "поддержано из коробки".
- LLM-as-judge требует ключи/endpoint. Если credentials недоступны, нужно использовать mock judge только для unit tests, а вывод по реальному качеству пометить как не подтвержденный live.
- OpenTelemetry может оказаться не прямой функцией eval-библиотеки, а функцией соседней экосистемы. Это нужно явно отразить в выводах.
- Community метрики быстро устаревают, поэтому они должны сниматься live в день подготовки отчета.
