"""Deterministic suggestions for follow-up process experiments."""

from __future__ import annotations

from typing import Any, Mapping


def suggest_experiments(comparison: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Suggest controlled experiments from a scenario comparison result.

    Suggestions are plans, not conclusions. When multiple reliable inputs
    changed, each plan varies one of them while holding the other recorded
    inputs at their baseline values. Unknown or hypothesized values remain
    explicit limitations.
    """
    suggestions: list[dict[str, Any]] = []

    for item in comparison.get("comparisons", []):
        baseline_id = item.get("baseline_scenario_id")
        scenario_id = item.get("scenario_id")
        changed = item.get("changed_parameters", [])
        uncertain = item.get("uncertain_parameters", [])
        result_changed = (
            item.get("calculation_result", {}).get("status") == "changed"
        )

        if len(changed) > 1:
            for parameter in changed:
                name = parameter["name"]
                suggestions.append(
                    {
                        "experiment_id": f"EXP-{len(suggestions) + 1:03d}",
                        "type": "isolate_parameter",
                        "title": f"Проверить влияние параметра «{name}»",
                        "based_on": [baseline_id, scenario_id],
                        "change_only": name,
                        "baseline_value": parameter["baseline"]["value"],
                        "test_value": parameter["candidate"]["value"],
                        "hold_other_recorded_parameters": "baseline",
                        "steps": [
                            "Возьмите исходный сценарий за основу.",
                            f"Измените только параметр «{name}» с "
                            f"{parameter['baseline']['value']!r} на "
                            f"{parameter['candidate']['value']!r}.",
                            "Оставьте остальные зафиксированные параметры без изменений.",
                            "Выполните расчёт и зафиксируйте результат.",
                            "Повторите исходный расчёт, чтобы проверить воспроизводимость.",
                        ],
                        "limitation": (
                            "Эксперимент проверяет один изменяемый параметр при "
                            "зафиксированных известных входных данных. Неучтённые "
                            "параметры и состояние системы также могут влиять на результат."
                        ),
                    }
                )

        elif len(changed) == 1:
            parameter = changed[0]
            name = parameter["name"]
            suggestions.append(
                {
                    "experiment_id": f"EXP-{len(suggestions) + 1:03d}",
                    "type": "reproduce_single_change",
                    "title": f"Повторить расчёт с изменением «{name}»",
                    "based_on": [baseline_id, scenario_id],
                    "change_only": name,
                    "baseline_value": parameter["baseline"]["value"],
                    "test_value": parameter["candidate"]["value"],
                    "hold_other_recorded_parameters": "baseline",
                    "steps": [
                        "Повторите исходный сценарий без изменений.",
                        f"Измените только параметр «{name}» с "
                        f"{parameter['baseline']['value']!r} на "
                        f"{parameter['candidate']['value']!r}.",
                        "Сравните результаты двух расчётов и сохраните наблюдения.",
                    ],
                    "limitation": (
                        "Один наблюдаемый сценарий не доказывает причинность; "
                        "необходимо подтвердить воспроизводимость результата."
                    ),
                }
            )

        if uncertain:
            suggestions.append(
                {
                    "experiment_id": f"EXP-{len(suggestions) + 1:03d}",
                    "type": "clarify_input",
                    "title": "Уточнить неподтверждённые входные параметры",
                    "based_on": [baseline_id, scenario_id],
                    "parameters": [
                        {
                            "name": parameter["name"],
                            "baseline_status": parameter["baseline"]["status"],
                            "candidate_status": parameter["candidate"]["status"],
                        }
                        for parameter in uncertain
                    ],
                    "steps": [
                        "Проверьте значения по исходной форме или повторной записи.",
                        "Укажите источник и подтвердите значения у аналитика.",
                        "Повторите сравнение после уточнения данных.",
                    ],
                    "limitation": (
                        "До подтверждения значений эти параметры нельзя использовать "
                        "для вывода о влиянии на результат."
                    ),
                }
            )

        if result_changed and not changed and not uncertain:
            suggestions.append(
                {
                    "experiment_id": f"EXP-{len(suggestions) + 1:03d}",
                    "type": "check_reproducibility",
                    "title": "Проверить воспроизводимость расчёта",
                    "based_on": [baseline_id, scenario_id],
                    "steps": [
                        "Повторите оба сценария с теми же входными данными.",
                        "Зафиксируйте время выполнения и видимые состояния формы.",
                        "Проверьте, не менялись ли справочники, правила или другие внешние условия.",
                    ],
                    "limitation": (
                        "Различие результатов при одинаковых записанных параметрах "
                        "указывает на неполноту наблюдений, но не объясняет причину."
                    ),
                }
            )

    return suggestions
