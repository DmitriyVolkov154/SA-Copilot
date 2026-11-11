from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import urllib.request
import urllib.error
import uuid

from validator import validate_task
from process_analysis import (
    ScenarioStore,
    ScenarioStoreError,
    ScenarioValidationError,
    compare_scenarios,
    suggest_experiments,
)

HOST = "127.0.0.1"
PORT = 8000
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:8b"
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR / "templates" / "index.html"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
SCENARIO_STORE = ScenarioStore(DATA_DIR / "scenarios.json")
MAX_REQUEST_BYTES = 100_000

SYSTEM_PROMPT = """
Ты — помощник системного аналитика. Отвечай на русском языке.
Не выдумывай требования, бизнес-правила, интеграции, ограничения и детали интерфейса.
Не превращай отсутствие требования в утверждение. Если аспект не определён, вынеси его в открытые вопросы.
Явно отделяй подтверждённые требования от предположений.
Не утверждай, что функция входит или не входит в область задачи, если этого нет во входных данных.
Не добавляй дополнительные функции только потому, что они типичны для подобных систем.
Сформируй ответ со следующими разделами:
1. Цель и границы задачи
2. Функциональные требования (идентификаторы FR-01 и далее)
3. Нефункциональные требования (NFR-01 и далее; если требований нет, укажи, что они не заданы)
4. Бизнес-правила (BR-01 и далее)
5. Критерии приёмки в формате Given / When / Then
6. Тест-кейсы: предусловия, шаги, тестовые данные и ожидаемый результат; включи позитивные и негативные сценарии
7. Открытые вопросы
8. Предположения (по умолчанию не делай предположений; если их нет, так и напиши)
В каждом спорном месте предпочитай вопрос догадке. Сохраняй числа, сроки и условия из исходного текста без изменений.
""".strip()


def generate_answer(task: str) -> str:
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": "Проанализируй исходное описание задачи. Не добавляй неподтверждённые требования.\n\nИСХОДНОЕ ОПИСАНИЕ:\n" + task,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 2200},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.loads(response.read().decode("utf-8"))
    answer = result.get("response", "").strip()
    if not answer:
        raise RuntimeError("Модель вернула пустой ответ.")
    return answer


class AppHandler(BaseHTTPRequestHandler):
    def send_bytes(self, status: int, data: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, status: int, content: str, content_type="text/plain; charset=utf-8"):
        self.send_bytes(status, content.encode("utf-8"), content_type)

    def send_json(self, status: int, payload: dict):
        self.send_text(
            status,
            json.dumps(payload, ensure_ascii=False),
            "application/json; charset=utf-8",
        )

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Некорректный размер запроса")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Тело запроса должно быть JSON-объектом")
        return data

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/scenarios":
            try:
                self.send_json(200, {"scenarios": SCENARIO_STORE.list_scenarios()})
            except ScenarioStoreError as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if path in ("/", "/index.html"):
            file_path, content_type = TEMPLATE_FILE, "text/html; charset=utf-8"
        elif path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            if "/" in relative or ".." in relative:
                self.send_text(400, "Некорректный путь")
                return
            file_path = STATIC_DIR / relative
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".svg": "image/svg+xml",
            }.get(file_path.suffix, "application/octet-stream")
        elif path == "/api/health":
            self.send_json(200, {"ok": True, "model": MODEL})
            return
        else:
            self.send_text(404, "Страница не найдена")
            return
        try:
            self.send_bytes(200, file_path.read_bytes(), content_type)
        except FileNotFoundError:
            self.send_text(500, f"Файл не найден: {file_path}")
        except OSError as exc:
            self.send_text(500, f"Не удалось прочитать файл: {exc}")

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            data = self.read_json_body()
            if path == "/api/scenarios":
                scenario = {
                    "scenario_id": "SC-" + uuid.uuid4().hex[:10].upper(),
                    "process_name": str(data.get("process_name", "")).strip(),
                    "input_parameters": data.get("input_parameters", []),
                    "user_actions": data.get("user_actions", []),
                    "system_responses": data.get("system_responses", []),
                    "calculation_result": data.get(
                        "calculation_result",
                        {"value": None, "status": "unknown"},
                    ),
                    "observations": data.get("observations", []),
                    "hypotheses": data.get("hypotheses", []),
                    "open_questions": data.get("open_questions", []),
                    "verification_status": "not_verified",
                }
                if not scenario["process_name"]:
                    self.send_json(400, {"error": "Укажи название бизнес-процесса."})
                    return
                saved = SCENARIO_STORE.add_scenario(scenario)
                self.send_json(201, {"scenario": saved})
                return

            if path == "/api/scenarios/compare":
                scenario_ids = data.get("scenario_ids")
                scenarios = SCENARIO_STORE.get_scenarios(scenario_ids)
                comparison = compare_scenarios(scenarios)
                comparison["suggested_experiments"] = suggest_experiments(comparison)
                self.send_json(200, comparison)
                return

            if path != "/api/generate":
                self.send_text(404, "Маршрут не найден")
                return

            task = str(data.get("task", "")).strip()
            if not task:
                self.send_text(400, "Опиши задачу системного аналитика")
                return
            if len(task) > 20_000:
                self.send_text(400, "Описание слишком длинное: максимум 20 000 символов")
                return
            answer = generate_answer(task)
            issues = validate_task(task, answer)
            response = {"answer": answer, "issues": issues, "issue_count": len(issues), "model": MODEL}
            self.send_json(200, response)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.send_json(400, {"error": str(exc) or "Не удалось прочитать JSON запроса"})
        except (ScenarioStoreError, ScenarioValidationError) as exc:
            self.send_json(400, {"error": str(exc)})
        except urllib.error.URLError as exc:
            print(f"Ошибка подключения к Ollama: {exc}", flush=True)
            self.send_text(502, "Не удалось подключиться к Ollama. Проверь, что Ollama запущена и модель доступна.")
        except Exception as exc:
            print(f"Ошибка запроса: {exc!r}", flush=True)
            self.send_json(500, {"error": f"Ошибка приложения: {exc}"})

    def log_message(self, fmt, *args):
        print(f"[HTTP] {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"Папка проекта: {BASE_DIR}", flush=True)
    print(f"HTML: {TEMPLATE_FILE}", flush=True)
    print(f"Модель: {MODEL}", flush=True)
    print(f"Хранилище сценариев: {DATA_DIR / 'scenarios.json'}", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"SA-Copilot запущен: http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка SA-Copilot", flush=True)
    finally:
        server.server_close()
