"""Deterministic checks for common SA-Copilot output problems.

These checks are heuristic: findings should be reviewed by a system analyst.
"""
import re


NUMBER_WORDS = {
    "один": 1, "одна": 1, "одну": 1, "одного": 1, "одной": 1,
    "два": 2, "две": 2, "двух": 2,
    "три": 3, "трех": 3, "четырех": 4,
    "четыре": 4, "пяти": 5, "пять": 5,
    "шесть": 6, "шести": 6, "семь": 7, "семи": 7,
    "восемь": 8, "восьми": 8, "девять": 9,
    "девяти": 9, "десять": 10, "десяти": 10,
}

NUMBER = (
    r"(?P<number>\d{1,2}|одного|одной|одну|один|одна|"
    r"двух|две|два|трёх|трех|три|четырёх|четырех|четыре|"
    r"пяти|пять|шести|шесть|семи|семь|восьми|восемь|"
    r"девяти|девять|десяти|десять)"
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower().replace("ё", "е")).strip()


def _number_value(value: str):
    value = value.lower().replace("ё", "е")
    return int(value) if value.isdigit() else NUMBER_WORDS.get(value)


def find_lockout_threshold(text: str):
    """Find a numeric attempt threshold near failed-attempt/lockout wording."""
    text = normalize(text)
    number = NUMBER.replace("трёх", "трех").replace("четырёх", "четырех")
    patterns = [
        rf"{number}\s+(?:неверн\w*|неправильн\w*|неудачн\w*)\s+(?:попыт\w*|ввод\w*)",
        rf"(?:после|при|за)\s+{number}\s+(?:неверн\w*|неправильн\w*|неудачн\w*)",
        rf"(?:блокир\w*|блокировк\w*)[^.!?;]{{0,100}}?{number}\s+(?:попыт\w*)",
        rf"{number}\s+(?:последовательн\w*\s+)?(?:неверн\w*|неудачн\w*)\s+(?:попыт\w*|ввод\w*)[^.!?;]{{0,100}}?(?:блокир\w*|блокировк\w*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _number_value(match.group("number"))
    return None


def find_lockout_duration_minutes(text: str):
    """Find a duration explicitly tied to a lockout, in minutes."""
    text = normalize(text)
    patterns = [
        r"(?:блокир\w*|блокировк\w*)[^.!?;]{0,120}?(?P<minutes>\d{1,4})\s*минут",
        r"(?P<minutes>\d{1,4})\s*минут[^.!?;]{0,120}?(?:блокир\w*|блокировк\w*)",
        r"(?:заблокир\w*|доступ закрыт)[^.!?;]{0,120}?(?P<minutes>\d{1,4})\s*минут",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group("minutes"))
    return None


def check_lockout_consistency(source: str, answer: str):
    issues = []
    source_threshold = find_lockout_threshold(source)
    answer_threshold = find_lockout_threshold(answer)

    if (
        source_threshold is not None
        and answer_threshold is not None
        and source_threshold != answer_threshold
    ):
        issues.append(
            f"Порог блокировки изменён: в исходном требовании "
            f"{source_threshold}, в ответе {answer_threshold}."
        )

    source_duration = find_lockout_duration_minutes(source)
    answer_duration = find_lockout_duration_minutes(answer)

    if (
        source_duration is not None
        and answer_duration is not None
        and source_duration != answer_duration
    ):
        issues.append(
            f"Длительность блокировки изменена: в исходном требовании "
            f"{source_duration} минут, в ответе {answer_duration} минут."
        )

    if source_threshold is not None and answer_threshold is None:
        issues.append(
            "Не удалось однозначно проверить порог блокировки в ответе модели."
        )

    if source_duration is not None and answer_duration is None:
        issues.append(
            "Не удалось однозначно проверить длительность блокировки в ответе модели."
        )

    return issues


def check_unsupported_features(source: str, answer: str):
    source_n, answer_n, issues = normalize(source), normalize(answer), []
    feature_groups = {
        "OAuth": ("oauth",),
        "двухфакторная аутентификация": (
            "двухфакторная аутентификация",
            "двухфакторной аутентификации",
            "2fa",
        ),
        "оформление заказов": (
            "оформление заказов", "оформления заказов",
            "оформлять заказы", "создание заказа",
        ),
        "корзина": ("корзина", "корзину", "корзине"),
        "просмотр товаров": (
            "просмотр товаров", "просматривать товары", "каталог товаров",
        ),
        "отображение времени снятия блокировки": (
            "время снятия блокировки", "времени снятия блокировки",
            "обратный отсчет", "обратный отсчёт",
        ),
        "сброс пароля": ("сброс пароля", "восстановление пароля"),
        "CAPTCHA": ("captcha", "капча"),
    }

    for feature, variants in feature_groups.items():
        in_answer = any(v in answer_n for v in variants)
        in_source = any(v in source_n for v in variants)
        if in_answer and not in_source:
            issues.append(
                f"Возможное неподтверждённое требование: {feature}."
            )

    return issues


def check_requirement_contradictions(source: str, answer: str):
    """Detect common explicit contradictions in requirements.

    This is a heuristic check, not a general natural-language contradiction
    detector. It reports the conflict without choosing which requirement wins.
    """
    source_n = normalize(source)
    answer_n = normalize(answer)
    issues = []

    verification_terms = (
        "проверки данных",
        "проверки реквизитов",
        "проверки документов",
    )
    must_wait_terms = (
        "только после проверки",
        "только после успешной проверки",
        "лишь после проверки",
        "после успешной проверки",
    )
    bypass_terms = (
        "если данные не проверены",
        "даже если данные не проверены",
        "независимо от проверки",
        "без проверки",
    )
    complete_terms = (
        "подключение должно завершаться",
        "подключение завершается",
        "подключение должно завершиться",
    )

    source_requires_check = (
        any(term in source_n for term in must_wait_terms)
        and any(term in source_n for term in verification_terms)
    )
    source_allows_bypass = (
        any(term in source_n for term in bypass_terms)
        and any(term in source_n for term in complete_terms)
    )

    if source_requires_check and source_allows_bypass:
        issues.append(
            "Обнаружено возможное противоречие требований: "
            "подключение должно завершаться после проверки, "
            "но также допускается завершение без проверки. "
            "Необходимо решение заказчика; автоматически выбирать "
            "одно из требований нельзя."
        )

    if source_requires_check and source_allows_bypass:
        acceptance_section = re.search(
            r"(?:критерии при[её]мки)(.*?)(?="
            r"\n\s*(?:#{1,6}\s*)?(?:\d+[.)]\s*)?"
            r"(?:тест-кейсы|тест кейсы|открытые вопросы|предположения)"
            r"|\Z)",
            answer_n,
            flags=re.DOTALL,
        )

        if acceptance_section:
            section = acceptance_section.group(1)
            if any(term in section for term in bypass_terms):
                issues.append(
                    "Критерии приёмки закрепляют поведение при "
                    "неразрешённом противоречии. Пометьте критерий "
                    "как требующий уточнения у заказчика."
                )

        test_section = re.search(
            r"(?:тест-кейсы|тест кейсы|тестовые сценарии)"
            r"(.*?)(?=\n\s*(?:#{1,6}\s*)?(?:\d+[.)]\s*)?"
            r"(?:открытые вопросы|предположения)|\Z)",
            answer_n,
            flags=re.DOTALL,
        )

        if test_section:
            section = test_section.group(1)
            if any(term in section for term in bypass_terms):
                issues.append(
                    "Тест-кейсы закрепляют поведение при "
                    "неразрешённом противоречии. Ожидаемый результат "
                    "требует согласования с заказчиком."
                )

    return issues


def check_unsupported_success_rule(source: str, answer: str):
    """Flag a success condition that is absent from the source requirements."""
    source_n = normalize(source)
    answer_n = normalize(answer)

    success_terms = (
        "успешной проверки",
        "проверка успешна",
        "проверка прошла успешно",
        "успешно проверены",
    )
    verification_terms = (
        "проверки данных",
        "проверки реквизитов",
        "проверки документов",
        "проверка данных",
    )

    answer_adds_success_condition = (
        any(term in answer_n for term in success_terms)
        and any(term in answer_n for term in verification_terms)
        and not any(term in source_n for term in success_terms)
    )

    if answer_adds_success_condition:
        return [
            "Возможно, добавлено неподтверждённое условие: "
            "требуется именно успешная проверка. Уточните это у заказчика."
        ]

    return []


def check_required_sections(answer: str):
    normalized = normalize(answer)
    required = {
        "цель и границы задачи": ("цель",),
        "функциональные требования": ("функциональные требования",),
        "нефункциональные требования": ("нефункциональные требования",),
        "бизнес-правила": ("бизнес-правила", "бизнес правила"),
        "критерии приёмки": ("критерии приемки", "критерии приёмки"),
        "тест-кейсы": ("тест-кейсы", "тест кейсы", "тестовые сценарии"),
        "открытые вопросы": ("открытые вопросы",),
        "предположения": ("предположения",),
    }
    return [
        f"Возможен пропуск обязательного раздела: {label}."
        for label, variants in required.items()
        if not any(v in normalized for v in variants)
    ]


def check_weak_test_cases(answer: str):
    normalized = normalize(answer)
    issues = []

    if (
        "тест-кейс" not in normalized
        and "тест кейс" not in normalized
        and "тестовые сценарии" not in normalized
    ):
        return issues

    if not any(
        word in normalized
        for word in ("ожидаемый результат", "ожидается", "результат:")
    ):
        issues.append(
            "В тест-кейсах не найден явный ожидаемый результат."
        )

    if not any(
        word in normalized
        for word in (
            "предусловие",
            "предварительное условие",
            "подготовка:",
        )
    ):
        issues.append(
            "В тест-кейсах не найдены предусловия; "
            "проверь полноту сценариев."
        )

    return issues


def validate_task(source: str, answer: str):
    if not answer or not answer.strip():
        return ["Ответ модели пустой."]

    issues = []
    issues.extend(check_lockout_consistency(source, answer))
    issues.extend(check_unsupported_features(source, answer))
    issues.extend(check_requirement_contradictions(source, answer))
    issues.extend(check_unsupported_success_rule(source, answer))
    issues.extend(check_required_sections(answer))
    issues.extend(check_weak_test_cases(answer))

    return list(dict.fromkeys(issues))
def check_unresolved_conflict_decisions(source: str, answer: str):
    """Warn when acceptance criteria or test cases settle a known conflict."""
    if not check_requirement_contradictions(source, ""):
        return []

    answer_n = normalize(answer)
    issues = []

    sections = [
        (
            "критерии приёмки",
            r"критерии при[её]мки(.*?)(?=тест-кейсы|тест кейсы|"
            r"открытые вопросы|предположения|\Z)",
        ),
        (
            "тест-кейсы",
            r"(?:тест-кейсы|тест кейсы|тестовые сценарии)"
            r"(.*?)(?=открытые вопросы|предположения|\Z)",
        ),
    ]

    for section_name, pattern in sections:
        match = re.search(pattern, answer_n, flags=re.DOTALL)
        if not match:
            continue

        section = match.group(1)
        confirms_completion = any(
            phrase in section
            for phrase in (
                "подключение завершается",
                "подключение должно завершаться",
                "подключение завершается автоматически",
            )
        )
        selects_conflicting_requirement = (
            "fr-01" in section or "fr-02" in section
        )
        chooses_unverified_behavior = any(
            phrase in section
            for phrase in (
                "без проверки",
                "данные не проверены",
                "независимо от проверки",
                "завершается автоматически",
            )
        )

        if confirms_completion and (
            selects_conflicting_requirement or chooses_unverified_behavior
        ):
            issues.append(
                f"Неразрешённое противоречие: раздел «{section_name}» "
                "закрепляет спорное поведение как согласованное. "
                "Нужно уточнение заказчика."
            )

    return issues


def check_missing_requisites_behavior(source: str, answer: str):
    """Warn when missing requisites are treated as merely unverified data."""
    source_n = normalize(source)
    answer_n = normalize(answer)

    missing_requisites_phrases = (
        "не предоставил реквизиты",
        "реквизиты отсутствуют",
        "не предоставлены реквизиты",
        "данные отсутствуют",
    )
    automatic_completion_phrases = (
        "подключение завершается автоматически",
        "подключение завершается",
        "подключение должно завершаться",
    )

    answer_mentions_missing = any(
        phrase in answer_n for phrase in missing_requisites_phrases
    )
    answer_completes_despite_missing = (
        answer_mentions_missing
        and any(
            phrase in answer_n
            for phrase in automatic_completion_phrases
        )
    )

    source_defines_missing_behavior = (
        any(phrase in source_n for phrase in missing_requisites_phrases)
        and any(
            phrase in source_n
            for phrase in automatic_completion_phrases
        )
    )

    if answer_completes_despite_missing and not source_defines_missing_behavior:
        return [
            "Возможно, придумано неподтверждённое поведение: подключение "
            "завершается при отсутствии реквизитов. Отсутствие данных и "
            "непроверенные данные — разные состояния; уточните правило "
            "у заказчика."
        ]

    return []


_validate_task_before_extra_checks = validate_task


def validate_task(source: str, answer: str):
    issues = _validate_task_before_extra_checks(source, answer)

    if not answer or not answer.strip():
        return issues

    issues.extend(check_unresolved_conflict_decisions(source, answer))
    issues.extend(check_missing_requisites_behavior(source, answer))

    return list(dict.fromkeys(issues))