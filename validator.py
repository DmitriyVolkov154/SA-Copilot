"""Deterministic checks for common SA-Copilot output problems.

These checks are heuristic: findings should be reviewed by a system analyst.
"""
import re

NUMBER_WORDS = {
    "один": 1, "одна": 1, "одну": 1, "одного": 1, "одной": 1,
    "два": 2, "две": 2, "двух": 2,
    "три": 3, "трех": 3, "трёх": 3,
    "четыре": 4, "четырех": 4, "четырёх": 4,
    "пять": 5, "пяти": 5, "шесть": 6, "шести": 6,
    "семь": 7, "семи": 7, "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9, "десять": 10, "десяти": 10,
}

NUMBER = r"(?P<number>\d{1,2}|одного|одной|одну|один|одна|двух|две|два|трёх|трех|три|четырёх|четырех|четыре|пяти|пять|шести|шесть|семи|семь|восьми|восемь|девяти|девять|десяти|десять)"


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
    if source_threshold is not None and answer_threshold is not None and source_threshold != answer_threshold:
        issues.append(f"Порог блокировки изменён: в исходном требовании {source_threshold}, в ответе {answer_threshold}.")
    source_duration = find_lockout_duration_minutes(source)
    answer_duration = find_lockout_duration_minutes(answer)
    if source_duration is not None and answer_duration is not None and source_duration != answer_duration:
        issues.append(f"Длительность блокировки изменена: в исходном требовании {source_duration} минут, в ответе {answer_duration} минут.")
    if source_threshold is not None and answer_threshold is None:
        issues.append("Не удалось однозначно проверить порог блокировки в ответе модели.")
    if source_duration is not None and answer_duration is None:
        issues.append("Не удалось однозначно проверить длительность блокировки в ответе модели.")
    return issues


def check_unsupported_features(source: str, answer: str):
    source_n, answer_n, issues = normalize(source), normalize(answer), []
    feature_groups = {
        "OAuth": ("oauth",),
        "двухфакторная аутентификация": ("двухфакторная аутентификация", "двухфакторной аутентификации", "2fa"),
        "оформление заказов": ("оформление заказов", "оформления заказов", "оформлять заказы", "создание заказа"),
        "корзина": ("корзина", "корзину", "корзине"),
        "просмотр товаров": ("просмотр товаров", "просматривать товары", "каталог товаров"),
        "отображение времени снятия блокировки": ("время снятия блокировки", "времени снятия блокировки", "обратный отсчет", "обратный отсчёт"),
        "сброс пароля": ("сброс пароля", "восстановление пароля"),
        "CAPTCHA": ("captcha", "капча"),
    }
    for feature, variants in feature_groups.items():
        in_answer = any(v in answer_n for v in variants)
        in_source = any(v in source_n for v in variants)
        if in_answer and not in_source:
            issues.append(f"Возможное неподтверждённое требование: {feature}.")
    return issues


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
    return [f"Возможен пропуск обязательного раздела: {label}." for label, variants in required.items() if not any(v in normalized for v in variants)]


def check_weak_test_cases(answer: str):
    normalized = normalize(answer)
    issues = []
    if "тест-кейс" not in normalized and "тест кейс" not in normalized and "тестовые сценарии" not in normalized:
        return issues
    if not any(word in normalized for word in ("ожидаемый результат", "ожидается", "результат:")):
        issues.append("В тест-кейсах не найден явный ожидаемый результат.")
    if not any(word in normalized for word in ("предусловие", "предварительное условие", "подготовка:")):
        issues.append("В тест-кейсах не найдены предусловия; проверь полноту сценариев.")
    return issues


def validate_task(source: str, answer: str):
    if not answer or not answer.strip():
        return ["Ответ модели пустой."]
    issues = []
    issues.extend(check_lockout_consistency(source, answer))
    issues.extend(check_unsupported_features(source, answer))
    issues.extend(check_required_sections(answer))
    issues.extend(check_weak_test_cases(answer))
    return list(dict.fromkeys(issues))
