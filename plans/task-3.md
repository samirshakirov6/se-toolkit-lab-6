# Task 3: The System Agent — Implementation Plan

## Overview

В Task 3 мы расширяем агента из Task 2, добавляя инструмент `query_api` для взаимодействия с backend API. Это позволит агенту отвечать на два новых типа вопросов:
1. **Статические системные факты** — фреймворк, порты, коды статуса
2. **Зависимые от данных запросы** — количество элементов, оценки, аналитика

## Deliverables

1. **План** (`plans/task-3.md`) — этот документ
2. **Обновлённый `agent.py`** — с инструментом `query_api` и обновлённым system prompt
3. **Обновлённая `AGENT.md`** — документация архитектуры и lessons learned (200+ слов)
4. **2 regression теста** — для проверки вызовов `query_api` и `read_file`

## План реализации

### Шаг 1: Определение схемы инструмента query_api

**Цель:** Добавить `query_api` как function-calling schema для OpenAI API.

**Параметры:**
- `method` (string, required) — HTTP метод: GET, POST, PUT, DELETE
- `path` (string, required) — путь к endpoint: `/items/`, `/analytics/completion-rate`
- `body` (string, optional) — JSON тело для POST/PUT запросов
- `use_auth` (boolean, optional) — использовать ли аутентификацию (по умолчанию true)

**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Query the backend Learning Management Service API. Use this to get real-time data about items, users, analytics, or test API endpoints.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE)",
          "enum": ["GET", "POST", "PUT", "DELETE"]
        },
        "path": {
          "type": "string",
          "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "JSON request body for POST/PUT requests (optional)"
        },
        "use_auth": {
          "type": "boolean",
          "description": "Whether to use authentication (default true). Set to false to test unauthenticated access."
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Шаг 2: Реализация функции query_api

**Цель:** Реализовать функцию для отправки HTTP запросов к backend API.

**Требования:**
- Использовать `httpx` для HTTP запросов
- Читать `LMS_API_KEY` из `.env.docker.secret`
- Читать `AGENT_API_BASE_URL` из env (default: `http://localhost:42002`)
- Добавлять `Authorization: Bearer <LMS_API_KEY>` заголовок при `use_auth=true`
- Возвращать JSON строку с `status_code` и `body`

**Поток данных:**
```
query_api(method, path, body, use_auth)
    ↓
Чтение LMS_API_KEY и AGENT_API_BASE_URL из env
    ↓
Создание URL: f"{api_base}{path}"
    ↓
Добавление заголовков (Authorization если use_auth)
    ↓
HTTP запрос через httpx.request()
    ↓
Возврат: json.dumps({"status_code": ..., "body": ...})
```

### Шаг 3: Обновление load_config()

**Цель:** Убедиться, что все конфигурационные переменные читаются из environment.

**Переменные:**
| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api | env (default: `http://localhost:42002`) |

**Код:**
```python
def load_config() -> dict:
    # Load LLM config from .env.agent.secret
    env_file = Path(__file__).parent / ".env.agent.secret"
    load_dotenv(env_file)

    # Also load LMS API key from .env.docker.secret
    docker_env_file = Path(__file__).parent / ".env.docker.secret"
    if docker_env_file.exists():
        load_dotenv(docker_env_file, override=True)

    return {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
        "lms_api_key": os.getenv("LMS_API_KEY"),
        "agent_api_base_url": os.getenv("AGENT_API_BASE_URL", "http://localhost:42002"),
    }
```

### Шаг 4: Обновление system prompt

**Цель:** Научить LLM правильно выбирать между инструментами.

**Decision tree:**
```
Вопрос → Выбор инструмента
─────────────────────────────────────────
Wiki документация → list_files → read_file
Исходный код → read_file (pyproject.toml, backend/)
Данные (item count, scores) → query_api (GET /items/)
Статус коды → query_api (use_auth: false для 401)
Диагностика багов → query_api → read_file (найти баг)
```

**Обновлённый system prompt:**
```
You are a documentation and system assistant for a software engineering project.
Answer questions using:
1. Project wiki documentation (via list_files and read_file tools)
2. Live backend API data (via query_api tool)
3. Source code files (via read_file tool)

IMPORTANT: You MUST use at least one tool before answering. Never answer from your general knowledge alone.

Tools available:
- list_files(path): List files and directories at a path
- read_file(path): Read the contents of a file
- query_api(method, path, body, use_auth): Query the backend API to get real-time data

When to use each tool:

**Wiki questions** (documentation, workflows, how-to):
- Use list_files to discover wiki files
- Use read_file to read specific wiki files
- Include source reference: (source: wiki/file.md#section)

**System facts** (framework, ports, status codes, API structure):
- Use query_api to get real-time system information
- Example: "What framework does the backend use?" → query_api GET /health
- For authentication status questions: use query_api with use_auth=false to test unauthenticated access

**Data queries** (item count, user scores, analytics):
- Use query_api to query the database via API endpoints
- Example: "How many items?" → query_api GET /items/

**Bug diagnosis**:
- First use query_api to reproduce the error
- Then use read_file to find the buggy code
- Explain the bug and suggest a fix
```

### Шаг 5: Обновление execute_tool()

**Цель:** Добавить обработку `query_api` в функцию выполнения инструментов.

**Код:**
```python
def execute_tool(tool_name: str, args: dict, project_root: Path, config: dict = None) -> str:
    if tool_name == "read_file":
        return read_file(args.get("path", ""), project_root)
    elif tool_name == "list_files":
        return list_files(args.get("path", ""), project_root)
    elif tool_name == "query_api":
        if not config:
            return json.dumps({"status_code": 0, "body": "Error: config not provided"})
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            config.get("agent_api_base_url", "http://localhost:42002"),
            config.get("lms_api_key", ""),
            args.get("use_auth", True)
        )
    else:
        return f"Error: Unknown tool: {tool_name}"
```

### Шаг 6: Запуск run_eval.py и анализ результатов

**Команда:**
```bash
uv run run_eval.py
```

**Ожидаемые результаты:**
| # | Вопрос | Инструменты | Ожидаемый ответ |
|---|--------|-------------|-----------------|
| 0 | Branch protection (wiki) | read_file | branch, protect |
| 1 | SSH connection (wiki) | read_file | ssh / key / connect |
| 2 | Backend framework | read_file | FastAPI |
| 3 | API routers | list_files | items, interactions, analytics, pipeline |
| 4 | Item count | query_api | число > 0 |
| 5 | Auth status code | query_api | 401 / 403 |
| 6 | Division by zero bug | query_api, read_file | ZeroDivisionError / division by zero |
| 7 | TypeError bug | query_api, read_file | TypeError / None / NoneType / sorted |
| 8 | Request lifecycle | read_file | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency | read_file | external_id check, duplicates skipped |

### Шаг 7: Итеративное исправление ошибок

**Стратегия:**
1. Запустить `run_eval.py`
2. Проанализировать первый провал
3. Исправить причину (system prompt, tool description, error handling)
4. Повторить до прохождения всех 10 тестов

**Возможные проблемы и решения:**
| Симптом | Причина | Решение |
|---------|---------|---------|
| Агент не использует инструмент | Описание слишком размытое | Уточнить description в schema |
| Tool вызван с ошибкой | Баг в реализации | Исправить код, протестировать изолированно |
| Неправильные аргументы | LLM не понимает schema | Уточнить описания параметров |
| Timeout | Слишком много tool calls | Уменьшить max iterations, оптимизировать prompt |
| AttributeError: 'NoneType' | LLM возвращает content: null | Использовать `(msg.get("content") or "")` |

### Шаг 8: Обновление AGENT.md

**Требования:**
- Минимум 200 слов
- Документировать `query_api` инструмент
- Описать аутентификацию через `LMS_API_KEY`
- Объяснить, как LLM выбирает между инструментами
- Lessons learned из benchmark
- Финальный eval score

### Шаг 9: Добавление regression тестов

**Тест 1: Framework question**
- Вопрос: "What Python web framework does this project's backend use?"
- Ожидается: `read_file` в tool_calls, ответ содержит "FastAPI"

**Тест 2: Item count question**
- Вопрос: "How many items are currently stored in the database?"
- Ожидается: `query_api` в tool_calls, ответ содержит число > 0

## Benchmark Results

### Initial Run

*Будет заполнено после первого запуска `run_eval.py`*

**Score:** ?/10

**Failures:**
- ?

### Iteration Strategy

1. **Проблема:** [описание]
   **Решение:** [что изменили]
   **Результат:** [новый score]

## Acceptance Criteria

- [ ] `plans/task-3.md` существует с планом реализации
- [ ] `agent.py` определяет `query_api` как function-calling schema
- [ ] `query_api` аутентифицируется через `LMS_API_KEY` из env
- [ ] Агент читает все LLM config из env переменных
- [ ] Агент читает `AGENT_API_BASE_URL` из env (default: `http://localhost:42002`)
- [ ] Агент отвечает на статические вопросы правильно
- [ ] Агент отвечает на data-dependent вопросы
- [ ] `run_eval.py` проходит все 10 локальных вопросов
- [ ] `AGENT.md` документирует архитектуру и lessons learned (200+ слов)
- [ ] 2 tool-calling regression теста существуют и проходят
- [ ] Git workflow: issue, branch, PR с `Closes #...`, partner approval, merge
