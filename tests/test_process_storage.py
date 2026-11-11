import json
import tempfile
import unittest
from pathlib import Path

from process_analysis import (
    ScenarioStore,
    ScenarioStoreError,
    compare_scenarios,
    suggest_experiments,
)


def scenario(scenario_id, region, product, result):
    return {
        "scenario_id": scenario_id,
        "process_name": "Расчёт условий перевозки",
        "input_parameters": [
            {"name": "region", "value": region, "status": "observed"},
            {"name": "product", "value": product, "status": "observed"},
        ],
        "calculation_result": {"value": result, "status": "observed"},
        "observations": [],
    }


class ScenarioStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "data" / "scenarios.json"
        self.store = ScenarioStore(self.path)

    def test_missing_store_starts_empty(self):
        self.assertEqual(self.store.list_scenarios(), [])

    def test_add_and_read_scenario(self):
        item = scenario("SC-001", "A", "Свиньи", "Ввоз разрешён")
        saved = self.store.add_scenario(item)

        self.assertEqual(saved["scenario_id"], "SC-001")
        self.assertEqual(self.store.list_scenarios(), [item])
        self.assertTrue(self.path.exists())

    def test_duplicate_id_is_rejected(self):
        item = scenario("SC-001", "A", "Свиньи", "Разрешён")
        self.store.add_scenario(item)

        with self.assertRaisesRegex(ScenarioStoreError, "уже существует"):
            self.store.add_scenario(item)

    def test_selected_scenarios_keep_requested_order(self):
        first = scenario("SC-001", "A", "Свиньи", "Разрешён")
        second = scenario("SC-002", "B", "КРС", "Запрещён")
        self.store.add_scenario(first)
        self.store.add_scenario(second)

        selected = self.store.get_scenarios(["SC-002", "SC-001"])

        self.assertEqual(
            [item["scenario_id"] for item in selected],
            ["SC-002", "SC-001"],
        )

    def test_missing_selected_scenario_is_reported(self):
        self.store.add_scenario(scenario("SC-001", "A", "Свиньи", "Разрешён"))

        with self.assertRaisesRegex(ScenarioStoreError, "Не найдены сценарии"):
            self.store.get_scenarios(["SC-001", "SC-404"])

    def test_corrupted_json_is_reported(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not-json", encoding="utf-8")

        with self.assertRaisesRegex(ScenarioStoreError, "прочитать хранилище"):
            self.store.list_scenarios()


class ExperimentSuggestionTests(unittest.TestCase):
    def test_multiple_changes_create_one_parameter_at_a_time_experiments(self):
        first = scenario("SC-001", "A", "Свиньи", "Разрешён")
        second = scenario("SC-002", "B", "КРС", "Запрещён")
        comparison = compare_scenarios([first, second])

        experiments = suggest_experiments(comparison)

        self.assertEqual(len(experiments), 2)
        self.assertEqual(
            {item["change_only"] for item in experiments},
            {"region", "product"},
        )
        self.assertTrue(
            all(item["hold_other_recorded_parameters"] == "baseline" for item in experiments)
        )

    def test_single_change_creates_reproduction_experiment(self):
        first = scenario("SC-001", "A", "Свиньи", "Разрешён")
        second = scenario("SC-002", "B", "Свиньи", "Запрещён")

        experiments = suggest_experiments(compare_scenarios([first, second]))

        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0]["type"], "reproduce_single_change")
        self.assertEqual(experiments[0]["change_only"], "region")

    def test_no_changes_and_same_result_need_no_suggestions(self):
        first = scenario("SC-001", "A", "Свиньи", "Разрешён")
        second = scenario("SC-002", "A", "Свиньи", "Разрешён")

        self.assertEqual(
            suggest_experiments(compare_scenarios([first, second])),
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
