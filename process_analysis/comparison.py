"""Compare observed process scenarios without inferring causal relationships.

The first scenario passed to :func:`compare_scenarios` is the baseline.
Only values marked as observed or confirmed by an analyst are treated as
reliable evidence for a change. Hypotheses and unknown values are reported
separately and are never silently promoted to facts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


SCENARIO_STATUSES = frozenset(
    {"observed", "hypothesis", "confirmed_by_analyst", "unknown"}
)
RELIABLE_STATUSES = frozenset({"observed", "confirmed_by_analyst"})


class ScenarioValidationError(ValueError):
    """Raised when a scenario does not follow the expected data structure."""


def _validate_json_value(value: Any, context: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ScenarioValidationError(
            f"{context}: значение должно быть совместимо с JSON."
        ) from exc


def _normalize_status(value: Any, context: str) -> str:
    status = value if value is not None else "unknown"
    if not isinstance(status, str) or status not in SCENARIO_STATUSES:
        allowed = ", ".join(sorted(SCENARIO_STATUSES))
        raise ScenarioValidationError(
            f"{context}: недопустимый статус {status!r}. Допустимые статусы: {allowed}."
        )
    return status


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate one scenario. Raises ScenarioValidationError on invalid data."""
    if not isinstance(scenario, Mapping):
        raise ScenarioValidationError("Сценарий должен быть объектом (словарём).")

    scenario_id = scenario.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ScenarioValidationError("У сценария должен быть непустой scenario_id.")

    process_name = scenario.get("process_name")
    if process_name is not None and (
        not isinstance(process_name, str) or not process_name.strip()
    ):
        raise ScenarioValidationError(
            f"{scenario_id}: process_name должен быть непустой строкой."
        )

    parameters = scenario.get("input_parameters", [])
    if not isinstance(parameters, list):
        raise ScenarioValidationError(
            f"{scenario_id}: input_parameters должен быть списком."
        )

    seen_names: set[str] = set()
    for index, parameter in enumerate(parameters):
        context = f"{scenario_id}: input_parameters[{index}]"
        if not isinstance(parameter, Mapping):
            raise ScenarioValidationError(f"{context} должен быть объектом.")

        name = parameter.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ScenarioValidationError(f"{context}: name должен быть непустой строкой.")
        if name in seen_names:
            raise ScenarioValidationError(
                f"{scenario_id}: параметр {name!r} указан более одного раза."
            )
        seen_names.add(name)

        if "value" not in parameter:
            raise ScenarioValidationError(f"{context}: отсутствует поле value.")
        _validate_json_value(parameter["value"], f"{context}.value")
        _normalize_status(parameter.get("status"), f"{context}.status")

    calculation_result = scenario.get("calculation_result")
    if calculation_result is not None:
        if not isinstance(calculation_result, Mapping):
            raise ScenarioValidationError(
                f"{scenario_id}: calculation_result должен быть объектом."
            )
        if "value" in calculation_result:
            _validate_json_value(
                calculation_result["value"],
                f"{scenario_id}: calculation_result.value",
            )
        _normalize_status(
            calculation_result.get("status"),
            f"{scenario_id}: calculation_result.status",
        )


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON-compatible values without Python's True == 1 quirk."""
    return json.dumps(
        left, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ) == json.dumps(
        right, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _parameter_map(scenario: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        parameter["name"]: parameter
        for parameter in scenario.get("input_parameters", [])
    }


def _value_state(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"present": False, "value": None, "status": "unknown"}

    return {
        "present": True,
        "value": item["value"],
        "status": _normalize_status(item.get("status"), "parameter.status"),
    }


def _compare_parameter(
    name: str,
    baseline_item: Mapping[str, Any] | None,
    candidate_item: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    baseline = _value_state(baseline_item)
    candidate = _value_state(candidate_item)

    both_reliable = (
        baseline["present"]
        and candidate["present"]
        and baseline["status"] in RELIABLE_STATUSES
        and candidate["status"] in RELIABLE_STATUSES
    )

    values_differ = None
    if baseline["present"] and candidate["present"]:
        values_differ = not _json_equal(baseline["value"], candidate["value"])

    if both_reliable:
        category = "changed" if values_differ else "unchanged"
    else:
        category = "uncertain"

    return category, {
        "name": name,
        "baseline": baseline,
        "candidate": candidate,
        "values_differ": values_differ,
    }


def _result_state(scenario: Mapping[str, Any]) -> dict[str, Any]:
    result = scenario.get("calculation_result")
    if result is None:
        return {"present": False, "value": None, "status": "unknown"}

    return {
        "present": "value" in result,
        "value": result.get("value"),
        "status": _normalize_status(result.get("status"), "calculation_result.status"),
    }


def _compare_result(
    baseline_scenario: Mapping[str, Any],
    candidate_scenario: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _result_state(baseline_scenario)
    candidate = _result_state(candidate_scenario)

    both_reliable = (
        baseline["present"]
        and candidate["present"]
        and baseline["status"] in RELIABLE_STATUSES
        and candidate["status"] in RELIABLE_STATUSES
    )

    values_differ = None
    if baseline["present"] and candidate["present"]:
        values_differ = not _json_equal(baseline["value"], candidate["value"])

    if both_reliable:
        status = "changed" if values_differ else "unchanged"
    else:
        status = "uncertain"

    return {
        "status": status,
        "baseline": baseline,
        "candidate": candidate,
        "values_differ": values_differ,
    }


def compare_scenarios(scenarios: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare two or more scenarios against the first scenario.

    The function reports observed differences; it does not determine why a
    result changed. Missing or unverified values are returned as uncertain.
    """
    if (
        not isinstance(scenarios, Sequence)
        or isinstance(scenarios, (str, bytes))
        or len(scenarios) < 2
    ):
        raise ScenarioValidationError(
            "Для сравнения необходимо передать не менее двух сценариев."
        )

    for scenario in scenarios:
        validate_scenario(scenario)

    scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ScenarioValidationError("scenario_id должны быть уникальными.")

    process_names = {
        scenario.get("process_name")
        for scenario in scenarios
        if scenario.get("process_name") is not None
    }
    if len(process_names) > 1:
        raise ScenarioValidationError(
            "Нельзя сравнивать сценарии с разными process_name."
        )

    baseline_scenario = scenarios[0]
    baseline_parameters = _parameter_map(baseline_scenario)
    comparison_results: list[dict[str, Any]] = []
    changed_parameter_names: set[str] = set()
    has_multiple_parameter_changes = False

    for candidate_scenario in scenarios[1:]:
        candidate_parameters = _parameter_map(candidate_scenario)
        parameter_names = list(baseline_parameters)
        parameter_names.extend(
            name for name in candidate_parameters if name not in baseline_parameters
        )

        changed_parameters = []
        unchanged_parameters = []
        uncertain_parameters = []

        for name in parameter_names:
            category, detail = _compare_parameter(
                name,
                baseline_parameters.get(name),
                candidate_parameters.get(name),
            )
            if category == "changed":
                changed_parameters.append(detail)
                changed_parameter_names.add(name)
            elif category == "unchanged":
                unchanged_parameters.append(detail)
            else:
                uncertain_parameters.append(detail)

        result_comparison = _compare_result(
            baseline_scenario, candidate_scenario
        )
        warnings = [
            "Сравнение показывает различия, но само по себе не доказывает причинно-следственную связь."
        ]

        if len(changed_parameters) > 1:
            has_multiple_parameter_changes = True
            warnings.append(
                "Одновременно изменилось несколько подтверждённых параметров. "
                "Нельзя определить влияние каждого из них на результат без дополнительных экспериментов."
            )

        if uncertain_parameters:
            warnings.append(
                "Есть отсутствующие или неподтверждённые значения параметров. "
                "Их необходимо уточнить до выводов о различиях."
            )

        if (
            result_comparison["status"] == "changed"
            and not changed_parameters
            and not uncertain_parameters
        ):
            warnings.append(
                "Результаты расчёта различаются, хотя зафиксированные входные параметры не изменились. "
                "Проверьте полноту исходных данных и воспроизводимость сценариев."
            )

        comparison_results.append(
            {
                "baseline_scenario_id": baseline_scenario["scenario_id"],
                "scenario_id": candidate_scenario["scenario_id"],
                "changed_parameters": changed_parameters,
                "unchanged_parameters": unchanged_parameters,
                "uncertain_parameters": uncertain_parameters,
                "calculation_result": result_comparison,
                "causal_attribution": "not_established",
                "warnings": warnings,
            }
        )

    return {
        "baseline_scenario_id": baseline_scenario["scenario_id"],
        "comparison_count": len(comparison_results),
        "comparisons": comparison_results,
        "summary": {
            "scenario_count": len(scenarios),
            "changed_parameter_names": sorted(changed_parameter_names),
            "multiple_parameters_changed": has_multiple_parameter_changes,
            "causal_relationships_established": False,
        },
    }
