import unittest
from validator import (
    find_lockout_threshold,
    find_lockout_duration_minutes,
    check_lockout_consistency,
    check_unsupported_features,
    validate_task,
)


class LockoutThresholdTests(unittest.TestCase):
    def test_three_attempts_word_form(self):
        self.assertEqual(find_lockout_threshold("После трёх неверных попыток вход блокируется."), 3)

    def test_two_attempts_genitive_form(self):
        self.assertEqual(find_lockout_threshold("После двух неверных попыток вход блокируется."), 2)

    def test_two_attempts_digit_form(self):
        self.assertEqual(find_lockout_threshold("Блокировка после 2 неверных попыток."), 2)

    def test_three_attempts_digit_form(self):
        self.assertEqual(find_lockout_threshold("Блокировка после 3 неверных попыток."), 3)

    def test_missing_threshold_is_none(self):
        self.assertIsNone(find_lockout_threshold("При ошибке входа показать сообщение."))


class LockoutDurationTests(unittest.TestCase):
    def test_duration_after_lockout_phrase(self):
        self.assertEqual(find_lockout_duration_minutes("После трёх неверных попыток блокировка на 15 минут."), 15)

    def test_duration_before_lockout_phrase(self):
        self.assertEqual(find_lockout_duration_minutes("Блокировка длится 20 минут."), 20)


class ValidationTests(unittest.TestCase):
    def test_detects_changed_threshold_and_duration(self):
        source = "После трёх неверных попыток вход блокируется на 15 минут."
        answer = "После двух неверных попыток блокировка на 20 минут."
        issues = check_lockout_consistency(source, answer)
        self.assertTrue(any("Порог блокировки изменён" in issue for issue in issues))
        self.assertTrue(any("Длительность блокировки изменена" in issue for issue in issues))

    def test_detects_possible_unsupported_feature(self):
        issues = check_unsupported_features("Пользователь входит по логину и паролю.", "Добавить CAPTCHA при входе.")
        self.assertTrue(any("CAPTCHA" in issue for issue in issues))

    def test_empty_answer(self):
        self.assertEqual(validate_task("Требование", "  "), ["Ответ модели пустой."])


if __name__ == "__main__":
    unittest.main(verbosity=2)
