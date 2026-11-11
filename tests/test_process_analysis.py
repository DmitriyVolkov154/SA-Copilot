import unittest

from process_analysis import (
    ScenarioValidationError,
    compare_scenarios,
    validate_scenario,
)


def make_scenario(
    scenario_id,
    parameters=None,
    result="approved",
    result_status="observed",
    process_name="Расчёт условий перевозки",
):
    return {
        "scenario_id": scenario_id,
        "process_name": process_name,
        "input_parameters": parameters or [],
        "calculation_result": {
            "value": result,
            "status": result_status,
        },
    }


def parameter(name, value, status="observed"):
    return {"name": name, "value": value, "status": status}


class ScenarioValidationTests(unittest.TestCase):
    def test_valid_scenario(self):
        validate_scenario(
            make_scenario("SC-001", [parameter("region_from", "A")])
        )

    def test_rejects_empty_scenario_id(self):
        with self.assertRaises(ScenarioValidationError):
            validate_scenario(make_scenario(" ", []))

    def test_rejects_duplicate_parameter_names(self):
        scenario = make_scenario(
            "SC-001",
            [parameter("region", "A"), parameter("region", "B")],
        )
        with self.assertRaisesRegex(ScenarioValidationError, "более одного раза"):
            validate_scenario(scenario)

    def test_rejects_unknown_status(self):
        scenario = make_scenario(
            "SC-001", [parameter("region", "A", status="approved_by_ai")]
        )
        with self.assertRaisesRegex(ScenarioValidationError, "недопустимый статус"):
            validate_scenario(scenario)

    def test_rejects_non_json_value(self):
        scenario = make_scenario(
            "SC-001", [parameter("region", object())]
        )
        with self.assertRaisesRegex(ScenarioValidationError, "совместимо с JSON"):
            validate_scenario(scenario)


class ScenarioComparisonTests(unittest.TestCase):
    def test_detects_changed_and_unchanged_parameters(self):
        baseline = make_scenario(
            "SC-001",
            [
                parameter("region_from", "Region A"),
                parameter("product", "pigs"),
            ],
            result="approved",
        )
        candidate = make_scenario(
            "SC-002",
            [
                parameter("region_from", "Region B"),
                parameter("product", "pigs"),
            ],
            result="denied",
        )

        comparison = compare_scenarios([baseline, candidate])["comparisons"][0]

        self.assertEqual(
            [item["name"] for item in comparison["changed_parameters"]],
            ["region_from"],
        )
        self.assertEqual(
            [item["name"] for item in comparison["unchanged_parameters"]],
            ["product"],
        )
        self.assertEqual(comparison["calculation_result"]["status"], "changed")
        self.assertEqual(comparison["causal_attribution"], "not_established")

    def test_multiple_changed_parameters_produce_warning(self):
        baseline = make_scenario(
            "SC-001",
            [parameter("region", "A"), parameter("product", "pigs")],
        )
        candidate = make_scenario(
            "SC-002",
            [parameter("region", "B"), parameter("product", "cattle")],
            result="denied",
        )

        comparison = compare_scenarios([baseline, candidate])
        item = comparison["comparisons"][0]

        self.assertEqual(len(item["changed_parameters"]), 2)
        self.assertTrue(comparison["summary"]["multiple_parameters_changed"])
        self.assertTrue(any("несколько" in warning for warning in item["warnings"]))
        self.assertFalse(comparison["summary"]["causal_relationships_established"])

    def test_hypothesis_is_not_treated_as_confirmed_change(self):
        baseline = make_scenario(
            "SC-001", [parameter("region", "A", status="hypothesis")]
        )
        candidate = make_scenario(
            "SC-002", [parameter("region", "B", status="observed")]
        )

        item = compare_scenarios([baseline, candidate])["comparisons"][0]

        self.assertEqual(item["changed_parameters"], [])
        self.assertEqual(len(item["uncertain_parameters"]), 1)
        self.assertTrue(item["uncertain_parameters"][0]["values_differ"])

    def test_missing_parameter_is_uncertain_not_changed(self):
        baseline = make_scenario("SC-001", [parameter("region", "A")])
        candidate = make_scenario("SC-002", [])

        item = compare_scenarios([baseline, candidate])["comparisons"][0]

        self.assertEqual(item["changed_parameters"], [])
        self.assertEqual(len(item["uncertain_parameters"]), 1)
        self.assertFalse(item["uncertain_parameters"][0]["candidate"]["present"])

    def test_added_parameter_is_uncertain_not_changed(self):
        baseline = make_scenario("SC-001", [])
        candidate = make_scenario("SC-002", [parameter("region", "A")])

        item = compare_scenarios([baseline, candidate])["comparisons"][0]

        self.assertEqual(item["changed_parameters"], [])
        self.assertEqual(len(item["uncertain_parameters"]), 1)

    def test_same_result_is_unchanged(self):
        baseline = make_scenario("SC-001", [parameter("region", "A")])
        candidate = make_scenario("SC-002", [parameter("region", "B")])

        result = compare_scenarios([baseline, candidate])["comparisons"][0][
            "calculation_result"
        ]

        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["values_differ"])

    def test_unconfirmed_result_is_uncertain(self):
        baseline = make_scenario(
            "SC-001", [parameter("region", "A")], result_status="unknown"
        )
        candidate = make_scenario(
            "SC-002", [parameter("region", "B")], result="denied"
        )

        result = compare_scenarios([baseline, candidate])["comparisons"][0][
            "calculation_result"
        ]

        self.assertEqual(result["status"], "uncertain")
        self.assertTrue(result["values_differ"])

    def test_multiple_candidates_are_compared_to_first_scenario(self):
        first = make_scenario("SC-001", [parameter("region", "A")])
        second = make_scenario("SC-002", [parameter("region", "B")])
        third = make_scenario("SC-003", [parameter("region", "C")])

        result = compare_scenarios([first, second, third])

        self.assertEqual(result["comparison_count"], 2)
        self.assertEqual(
            [item["baseline_scenario_id"] for item in result["comparisons"]],
            ["SC-001", "SC-001"],
        )
        self.assertEqual(
            [item["scenario_id"] for item in result["comparisons"]],
            ["SC-002", "SC-003"],
        )

    def test_rejects_less_than_two_scenarios(self):
        with self.assertRaises(ScenarioValidationError):
            compare_scenarios([make_scenario("SC-001")])

    def test_rejects_duplicate_scenario_ids(self):
        first = make_scenario("SC-001")
        second = make_scenario("SC-001")
        with self.assertRaisesRegex(ScenarioValidationError, "уникальными"):
            compare_scenarios([first, second])

    def test_rejects_different_processes(self):
        first = make_scenario("SC-001", process_name="Process A")
        second = make_scenario("SC-002", process_name="Process B")
        with self.assertRaisesRegex(ScenarioValidationError, "разными process_name"):
            compare_scenarios([first, second])

    def test_boolean_and_number_are_different_json_values(self):
        baseline = make_scenario("SC-001", [parameter("flag", True)])
        candidate = make_scenario("SC-002", [parameter("flag", 1)])

        item = compare_scenarios([baseline, candidate])["comparisons"][0]

        self.assertEqual(len(item["changed_parameters"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
