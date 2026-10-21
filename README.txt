SA-COPILOT — обновлённый локальный пакет

Содержимое:
- app.py                  HTTP-сервер + запрос к Ollama + запуск валидатора
- validator.py            эвристические проверки требований
- templates/index.html    интерфейс
- static/styles.css       оформление страницы
- static/app.js           взаимодействие страницы с API
- tests/test_validator.py автоматические тесты валидатора

Установка в существующий проект:
1. Останови сервер SA-Copilot в PowerShell: Ctrl+C.
2. Сделай резервную копию папки C:\Users\DmitriyWolf\SA-Copilot.
3. Распакуй архив во временную папку.
4. Скопируй app.py и validator.py в C:\Users\DmitriyWolf\SA-Copilot с заменой.
5. Скопируй папки templates, static и tests в папку проекта. Если Windows спросит о замене, подтверди.
   Не удаляй и не заменяй папку .venv.
6. Открой PowerShell и выполни:
   Set-Location "$HOME\SA-Copilot"
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
7. Если тесты прошли, запусти:
   .\.venv\Scripts\python.exe app.py
8. Открой http://127.0.0.1:8000

Зависимости: стандартная библиотека Python. Отдельно установливать пакеты не нужно.
Ollama должна быть запущена, а модель qwen3:8b — доступна.

Важно: валидатор использует эвристики. Он помогает находить часть расхождений и возможных выдуманных функций, но не доказывает корректность ТЗ. Все замечания нужно проверять вручную.
