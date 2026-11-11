"""Thread-safe local JSON storage for process-analysis scenarios."""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from .comparison import ScenarioValidationError, validate_scenario


class ScenarioStoreError(RuntimeError):
    """Raised when scenario storage cannot be read or written safely."""


class ScenarioStore:
    """Persist scenarios in a local JSON file using atomic replacement."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self._lock = threading.RLock()

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []

        try:
            raw = self.file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScenarioStoreError(
                f"Не удалось прочитать хранилище сценариев: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise ScenarioStoreError(
                "Хранилище сценариев повреждено: ожидался JSON-массив."
            )

        scenarios: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for index, scenario in enumerate(data):
            try:
                validate_scenario(scenario)
            except ScenarioValidationError as exc:
                raise ScenarioStoreError(
                    f"Некорректный сценарий в хранилище, запись {index + 1}: {exc}"
                ) from exc
            scenario_id = scenario["scenario_id"]
            if scenario_id in seen_ids:
                raise ScenarioStoreError(
                    f"Повторяющийся scenario_id в хранилище: {scenario_id}"
                )
            seen_ids.add(scenario_id)
            scenarios.append(scenario)

        return scenarios

    def _write_unlocked(self, scenarios: Sequence[Mapping[str, Any]]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.file_path.with_name(
            f".{self.file_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            serialized = json.dumps(
                list(scenarios),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            temporary_path.write_text(serialized + "\n", encoding="utf-8")
            os.replace(temporary_path, self.file_path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ScenarioStoreError(
                f"Не удалось сохранить сценарии: {exc}"
            ) from exc

    def list_scenarios(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def get_scenarios(self, scenario_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not isinstance(scenario_ids, Sequence) or isinstance(
            scenario_ids, (str, bytes)
        ):
            raise ScenarioStoreError("scenario_ids должен быть списком идентификаторов.")

        if len(scenario_ids) < 2:
            raise ScenarioStoreError("Для сравнения выбери не менее двух сценариев.")

        if len(set(scenario_ids)) != len(scenario_ids):
            raise ScenarioStoreError("В списке сравнения есть повторяющиеся сценарии.")

        with self._lock:
            scenarios = self._read_unlocked()
            by_id = {scenario["scenario_id"]: scenario for scenario in scenarios}
            missing = [item for item in scenario_ids if item not in by_id]
            if missing:
                raise ScenarioStoreError(
                    "Не найдены сценарии: " + ", ".join(str(item) for item in missing)
                )
            return [by_id[item] for item in scenario_ids]

    def add_scenario(self, scenario: Mapping[str, Any]) -> dict[str, Any]:
        validate_scenario(scenario)
        # A JSON round-trip provides a detached copy and guarantees serializability.
        try:
            detached = json.loads(
                json.dumps(scenario, ensure_ascii=False, allow_nan=False)
            )
        except (TypeError, ValueError) as exc:
            raise ScenarioValidationError(
                "Сценарий должен содержать только JSON-совместимые значения."
            ) from exc

        with self._lock:
            scenarios = self._read_unlocked()
            scenario_id = detached["scenario_id"]
            if any(item["scenario_id"] == scenario_id for item in scenarios):
                raise ScenarioStoreError(
                    f"Сценарий с идентификатором {scenario_id} уже существует."
                )
            scenarios.append(detached)
            self._write_unlocked(scenarios)

        return detached
