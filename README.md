# kad-parser-doc

Отдельный сервис для парсинга текстов судебных актов из `ras.arbitr.ru`.

## Что делает сервис

- Читает задачи из обычной YMQ очереди (без FIFO-группировки по делу).
- Формат одной задачи: `job_uuid`, `doc_id`, `doc_uuid`.
- Для каждой задачи получает HTML текста через браузерный:
  - `POST /Ras/HtmlDocument/{doc_uuid}`
  - `RecaptchaToken` через `Common.executePravocaptcha`.
- При успехе отправляет результат в CORE:
  - endpoint: `/api/parse-result/document-text/`
  - payload: `job_uuid`, `doc_id`, `doc_uuid`, `text_base64`, `start_ip`, `service_id`.
- Сообщение удаляется из очереди только если CORE подтвердил успех (`HTTP ok` и `success=true`).
- При ошибке парсинга/CORE отправляет error payload в тот же endpoint, но сообщение из очереди не удаляет.
- Если очередь пуста, браузер закрывается. При появлении новой задачи запускается заново.

## Запуск

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Запускать из директории `kad-parser-doc/`.

Требуется установленный Google Chrome. Selenium использует Selenium Manager для подбора драйвера.

## Healthcheck

- `GET /api/ping`

Пример ответа:

```json
{
  "message": "pong",
  "ymq_enabled": true
}
```

## Формат входной задачи (YMQ message Body)

```json
{
  "job_uuid": "0e187...",
  "doc_id": 1,
  "doc_uuid": "a39..."
}
```

## Payload в CORE

### Success

Endpoint: `/api/parse-result/document-text/`

```json
{
  "job_uuid": "0e187...",
  "doc_id": 1,
  "doc_uuid": "a39...",
  "text_base64": "PGh0bWw+Li4uPC9odG1sPg==",
  "start_ip": "203.0.113.10",
  "service_id": 2
}
```

### Error

Endpoint: `/api/parse-result/document-text/`

```json
{
  "job_uuid": "0e187...",
  "doc_id": 1,
  "doc_uuid": "a39...",
  "status": "error",
  "message": "Ошибка 451",
  "start_ip": "203.0.113.10",
  "service_id": 2
}
```

## Переменные окружения

См. `.env.example`.

Ключевые:

- `ENABLE_YMQ`
- `YMQ_*`
- `CORE_API_URL`, `CORE_API_TOKEN`, `SERVICE_ID`
- `CHECK_IP_ENABLED`, `CHECK_IP_URL`, `CHECK_IP_BEARER`
- `HEADLESS`, `LOG_LEVEL`, `DEBUG`, `PORT`

