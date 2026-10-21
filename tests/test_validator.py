import unittest

from validator import (
    find_lockout_threshold,
    find_lockout_duration_minutes,
    check_lockout_consistency,
    check_unsupported_features,
    check_requirement_contradictions,
    check_unsupported_success_rule,
    validate_task,
)


class LockoutThresholdTests(unittest.TestCase):
    def test_three_attempts_word_form(self):
        self.assertEqual(
            find_lockout_threshold(
                "После трёх неверных попыток вход блокируется."
            ),
            3,
        )

    def test_two_attempts_genitive_form(self):
        self.assertEqual(
            find_lockout_threshold(
                "После двух неверных попыток вход блокируется."
            ),
            2,
        )

    def test_two_attempts_digit_form(self):
        self.assertEqual(
            find_lockout_threshold(
                "Блокировка после 2 неверных попыток."
            ),
            2,
        )

    def test_three_attempts_digit_form(self):
        self.assertEqual(
            find_lockout_threshold(
                "Блокировка после 3 неверных попыток."
            ),
            3,
        )

    def test_missing_threshold_is_none(self):
        self.assertIsNone(
            find_lockout_threshold(
                "При ошибке входа показать сообщение."
            )
        )


class LockoutDurationTests(unittest.TestCase):
    def test_duration_after_lockout_phrase(self):
        self.assertEqual(
            find_lockout_duration_minutes(
                "После трёх неверных попыток блокировка на 15 минут."
            ),
            15,
        )

    def test_duration_before_lockout_phrase(self):
        self.assertEqual(
            find_lockout_duration_minutes(
                "Блокировка длится 20 минут."
            ),
            20,
        )


class ValidationTests(unittest.TestCase):
    def test_detects_changed_threshold_and_duration(self):
        source = (
            "После трёх неверных попыток вход блокируется на 15 минут."
        )
        answer = (
            "После двух неверных попыток блокировка на 20 минут."
        )
        issues = check_lockout_consistency(source, answer)

        self.assertTrue(
            any("Порог блокировки изменён" in issue for issue in issues)
        )
        self.assertTrue(
            any("Длительность блокировки изменена" in issue for issue in issues)
        )

    def test_detects_possible_unsupported_feature(self):
        issues = check_unsupported_features(
            "Пользователь входит по логину и паролю.",
            "Добавить CAPTCHA при входе.",
        )
        self.assertTrue(any("CAPTCHA" in issue for issue in issues))

    def test_empty_answer(self):
        self.assertEqual(
            validate_task("Требование", "  "),
            ["Ответ модели пустой."],
        )

    def test_detects_requirement_contradiction(self):
        source = (
            "Подключение должно завершаться только после проверки данных "
            "контрагента. Если данные не проверены, подключение всё равно "
            "должно завершаться автоматически."
        )
        issues = check_requirement_contradictions(source, "")

        self.assertTrue(
            any("противоречие требований" in issue.lower() for issue in issues)
        )

    def test_no_contradiction_when_only_waiting_for_check_is_required(self):
        source = (
            "Подключение должно завершаться только после проверки данных "
            "контрагента."
        )
        self.assertEqual(check_requirement_contradictions(source, ""), [])

    def test_flags_unsupported_success_condition(self):
        source = (
            "Подключение завершается после проверки данных контрагента."
        )
        answer = (
            "Подключение завершается только после успешной проверки данных."
        )
        issues = check_unsupported_success_rule(source, answer)

        self.assertTrue(
            any("неподтверждённое условие" in issue.lower() for issue in issues)
        )

    def test_does_not_flag_success_condition_when_source_confirms_it(self):
        source = (
            "Подключение завершается только после успешной проверки данных."
        )
        answer = (
            "Подключение завершается только после успешной проверки данных."
        )
        self.assertEqual(
            check_unsupported_success_rule(source, answer),
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
class ConflictDecisionTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            "Подключение должно завершаться только после проверки данных "
            "контрагента. Если данные не проверены, подключение всё равно "
            "должно завершаться автоматически."
        )

    def test_flags_conflicting_acceptance_criteria(self):
        answer = """
        Критерии приёмки
        Then — Подключение завершается (согласно FR-02).

        Тест-кейсы
        Ожидаемый результат — Подключение завершается автоматически (FR-02).
        """
        issues = validate_task(self.source, answer)

        self.assertTrue(
            any(
                "критерии приёмки" in issue.lower()
                and "противоречие" in issue.lower()
                for issue in issues
            )
        )

    def test_flags_completion_when_requisites_are_missing(self):
        answer = """
        Тест-кейсы
        Предусловия: менеджер инициировал подключение,
        контрагент не предоставил реквизиты.
        Ожидаемый результат: подключение завершается автоматически.
        """
        issues = validate_task(self.source, answer)

        self.assertTrue(
            any(
                "отсутствии реквизитов" in issue.lower()
                for issue in issues
            )
        )

    def test_does_not_flag_conflicting_criteria_without_source_conflict(self):
        source = (
            "Подключение должно завершаться только после проверки данных "
            "контрагента."
        )
        answer = """
        Критерии приёмки
        Подключение завершается после проверки данных.
        """
        issues = validate_task(source, answer)

        self.assertFalse(
            any("неразрешённое противоречие" in issue.lower() for issue in issues)
        )