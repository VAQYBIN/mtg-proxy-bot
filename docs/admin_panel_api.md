# MTG Admin Panel — API Reference

**Source:** https://github.com/MaksimTMB/mtg-adminpanel
**Panel:** Node.js Express, port 3000
**Agent:** FastAPI, порт `agent_port` (по умолчанию 8081) на каждом узле

---

## Аутентификация

### Panel API

Все эндпоинты, кроме `GET /api/version` и `GET /api/totp/status`, требуют заголовок:

```
x-auth-token: YOUR_AUTH_TOKEN
```

Или как query-параметр: `?token=YOUR_AUTH_TOKEN`

**При включённом TOTP 2FA** каждый запрос (кроме эндпоинтов управления TOTP) требует дополнительно:

```
x-totp-code: 123456          # валидный 30-секундный TOTP-код, ИЛИ
x-totp-code: <session-token> # 24h session-токен из заголовка x-totp-session
```

При отсутствии или невалидном TOTP:
```json
HTTP 403
{ "error": "TOTP required", "totp": true }
```

При успешной валидации TOTP в ответе приходит заголовок `x-totp-session: <token>` (TTL 24ч).
Клиент кеширует этот токен и использует вместо нового TOTP-кода в последующих запросах.

**Эндпоинты, освобождённые от TOTP** (требуют только `x-auth-token`):
- `GET /api/totp/status`
- `POST /api/totp/setup`
- `POST /api/totp/verify`
- `POST /api/totp/disable`

### Agent API

Все эндпоинты агента (кроме `GET /health`) требуют:
```
x-agent-token: YOUR_AGENT_TOKEN
```
При ошибке: HTTP 401 `{"detail": "Unauthorized"}`

---

## Panel API

### Общие

#### `GET /api/version`
Аутентификация не требуется.

**Ответ:**
```json
{ "version": "2.1.0" }
```

---

#### `GET /api/status`
Мгновенный ответ из кеша узлов (без SSH).

**Ответ:**
```json
[
  {
    "id": 1,
    "name": "Helsinki",
    "host": "hel.example.com",
    "online": true,
    "containers": 5,
    "online_users": 2
  }
]
```

---

### Узлы (Nodes)

#### `GET /api/nodes`
Список всех узлов из БД (без SSH).

**Ответ:** массив объектов узла:
```json
[
  {
    "id": 1,
    "name": "Helsinki",
    "host": "hel.example.com",
    "ssh_user": "root",
    "ssh_port": 22,
    "base_dir": "/opt/mtg/users",
    "start_port": 4433,
    "created_at": "2026-03-01T00:00:00",
    "flag": "fi",
    "agent_port": 8081
  }
]
```
`ssh_key` и `ssh_password` в ответе не возвращаются.

---

#### `GET /api/nodes/counts`
Количество пользователей на каждом узле (из БД, без SSH).

**Ответ:**
```json
{ "1": 5, "2": 3 }
```
Ключи — ID узлов в виде строк, значения — количество пользователей.

---

#### `POST /api/nodes`
Создать новый узел. Опционально устанавливает MTG Agent через SSH в фоне.

**Тело запроса:**
```json
{
  "name": "Helsinki",            // обязательно
  "host": "hel.example.com",    // обязательно
  "ssh_user": "root",            // по умолчанию: "root"
  "ssh_port": 22,                // по умолчанию: 22
  "ssh_key": "/ssh_keys/id_rsa", // путь к файлу приватного ключа или null
  "ssh_password": "secret",      // SSH-пароль или null
  "base_dir": "/opt/mtg/users",  // по умолчанию: "/opt/mtg/users"
  "start_port": 4433,            // по умолчанию: 4433
  "flag": "fi",                  // ISO 3166-1 alpha-2 или null
  "agent_port": 8081,            // по умолчанию: 8081
  "auto_install_agent": true     // по умолчанию: true
}
```

**Ответ:**
```json
{ "id": 1, "name": "Helsinki", "host": "hel.example.com" }
```

---

#### `PUT /api/nodes/:id`
Обновить настройки узла. Все поля опциональны.

**Тело запроса:** те же поля, что у POST (без `auto_install_agent`).

**Ответ:**
```json
{ "ok": true }
```

---

#### `DELETE /api/nodes/:id`
Удалить узел и всех его пользователей из БД (каскадно). Файлы на удалённом узле не удаляются.

**Ответ:**
```json
{ "ok": true }
```

---

#### `GET /api/nodes/:id/check`
Проверить SSH-подключение к узлу.

**Ответ:**
```json
{ "online": true }
// или:
{ "online": false, "error": "Connection refused" }
```

---

#### `GET /api/nodes/:id/check-agent`
Проверить HTTP-подключение к MTG Agent на узле.

**Ответ:**
```json
{ "available": true }
// или:
{ "available": false, "reason": "ECONNREFUSED" }
// или (agent_port не настроен):
{ "available": false, "reason": "no agent_port configured" }
```

---

#### `POST /api/nodes/:id/update-agent`
Установить или обновить MTG Agent через SSH. Скачивает файлы с GitHub, записывает `.env`, перезапускает контейнер агента.

**Ответ:**
```json
{ "ok": true, "output": "==> Done" }
// или:
{ "ok": false, "error": "SSH error message" }
```

---

#### `GET /api/nodes/:id/summary`
Сводная информация по узлу со всеми пользователями и метриками. Из кеша (TTL 10с) — мгновенно.

**Ответ:**
```json
{
  "online": true,
  "users": [
    {
      "id": 1,
      "node_id": 1,
      "name": "tg_123456789",
      "port": 4433,
      "secret": "ee...hex",
      "status": "active",
      "note": "",
      "expires_at": "2026-06-01T00:00:00",
      "traffic_limit_gb": 100.0,
      "created_at": "2026-03-01T00:00:00",
      "traffic_rx_snap": null,
      "traffic_tx_snap": null,
      "traffic_reset_at": null,
      "last_seen_at": "2026-03-19T10:00:00",
      "billing_price": 5.0,
      "billing_currency": "USD",
      "billing_period": "monthly",
      "billing_paid_until": "2026-04-01",
      "billing_status": "active",
      "max_devices": 3,
      "traffic_reset_interval": "monthly",
      "next_reset_at": "2026-04-01T00:00:00",
      "total_traffic_rx_bytes": 56797474,
      "total_traffic_tx_bytes": 58972294,
      "running": true,
      "connections": 2,
      "is_online": true,
      "traffic": { "rx": "54.17MB", "tx": "56.24MB", "rx_bytes": 56797474, "tx_bytes": 58972294 },
      "link": "tg://proxy?server=hel.example.com&port=4433&secret=ee...",
      "expired": false
    }
  ],
  "traffic": {
    "tg_123456789": { "rx": "54.17MB", "tx": "56.24MB" }
  }
}
```

---

#### `GET /api/nodes/:id/traffic`
Свежий трафик всех пользователей узла. Прямой SSH-вызов (не из кеша) — всегда актуален.

**Ответ:**
```json
{
  "tg_123456789": { "rx": "54.17MB", "tx": "56.24MB" },
  "tg_987654321": { "rx": "1.25GB",  "tx": "2.10GB" }
}
```

---

#### `GET /api/nodes/:id/agent-version`
Возвращает закешированную версию агента.

**Ответ:**
```json
{ "version": "2.2.1", "available": true, "online": true }
// или:
{ "version": null, "available": false, "online": false }
```

---

#### `GET /api/nodes/:id/mtg-version`
Запускает `docker inspect nineseconds/mtg:2` на узле через SSH.

**Ответ:**
```json
{ "version": "mtg:2 | built 2025-12-01T00:00:00Z", "raw": "..." }
// или:
{ "version": "error", "error": "SSH error message" }
```

---

#### `POST /api/nodes/:id/mtg-update`
Запускает `docker pull nineseconds/mtg:2` на узле через SSH.

**Ответ:**
```json
{ "ok": true, "output": "Digest: sha256:...\nStatus: Image is up to date..." }
// или:
{ "error": "SSH error message" }
```

---

#### `GET /api/nodes/:id/debug`
Диагностический эндпоинт. Возвращает состояние кеша и прямые результаты от агента.

**Ответ:**
```json
{
  "node": { "id": 1, "name": "Helsinki", "host": "...", "agent_port": 8081, "base_dir": "/opt/mtg/users" },
  "nodeCache": {
    "status": { "online": true, "containers": 3, "online_users": 1 },
    "remoteUsers": [],
    "agentVersion": "2.2.1",
    "updatedAt": 1742382000000,
    "error": null
  },
  "agentDirect": { "status": "ok", "version": "2.2.1" },
  "agentDirectError": null,
  "agentUsersRaw": [],
  "agentUsersError": null
}
```

---

### Пользователи (Users)

#### `GET /api/nodes/:id/users`
Список всех пользователей узла с живыми данными из кеша. Мгновенно.
Побочный эффект: применяет ограничение `max_devices` (останавливает пользователя при превышении), обновляет `last_seen_at`.

**Ответ:** массив объектов пользователя:
```json
[
  {
    "id": 1,
    "node_id": 1,
    "name": "tg_123456789",
    "port": 4433,
    "secret": "ee...",
    "status": "active",
    "note": "",
    "expires_at": null,
    "traffic_limit_gb": null,
    "created_at": "...",
    "connections": 2,
    "running": true,
    "is_online": true,
    "traffic_rx": "54.17MB",
    "traffic_tx": "56.24MB",
    "link": "tg://proxy?server=hel.example.com&port=4433&secret=ee...",
    "expired": false,
    "max_devices": null,
    "traffic_reset_interval": null,
    "next_reset_at": null,
    "total_traffic_rx_bytes": 0,
    "total_traffic_tx_bytes": 0,
    "last_seen_at": null,
    "billing_price": null,
    "billing_currency": "RUB",
    "billing_period": "monthly",
    "billing_paid_until": null,
    "billing_status": "active"
  }
]
```

Отличие от `/summary`: `traffic_rx`/`traffic_tx` — плоские строки вместо вложенного объекта.

---

#### `POST /api/nodes/:id/users`
Создать нового пользователя. Создаёт контейнер MTG через SSH (или агент), затем сохраняет в БД.

**Тело запроса:**
```json
{
  "name": "tg_123456789",              // обязательно, regex: ^[a-zA-Z0-9_-]{1,32}$
  "note": "John Doe",                  // опционально
  "expires_at": "2026-06-01T00:00:00", // опционально, ISO 8601
  "traffic_limit_gb": 100.0            // опционально, только для отображения
}
```

**Ответ:**
```json
{
  "id": 1,
  "name": "tg_123456789",
  "port": 4433,
  "secret": "ee7a3b...676f6f676c652e636f6d",
  "note": "",
  "expires_at": null,
  "traffic_limit_gb": null,
  "link": "tg://proxy?server=hel.example.com&port=4433&secret=ee..."
}
```

**Ошибки:**
- `400` — имя отсутствует, невалидный формат или уже существует на этом узле
- `500` — SSH/agent ошибка

---

#### `PUT /api/nodes/:id/users/:name`
Обновить метаданные пользователя только в БД (без SSH). Все поля опциональны.

**Тело запроса:**
```json
{
  "note": "Updated name",
  "expires_at": "2026-12-01T00:00:00",
  "traffic_limit_gb": 200.0,
  "billing_price": 5.0,
  "billing_currency": "USD",
  "billing_period": "monthly",
  "billing_paid_until": "2026-04-01",
  "billing_status": "active",           // "active" | "trial" | "expired"
  "max_devices": 3,                     // null = без ограничений
  "traffic_reset_interval": "monthly"   // "daily" | "monthly" | "yearly" | null
}
```

При изменении `traffic_reset_interval` поле `next_reset_at` пересчитывается автоматически.

**Ответ:**
```json
{ "ok": true }
```

---

#### `DELETE /api/nodes/:id/users/:name`
Остановить и удалить контейнер на узле через SSH, удалить из БД.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /api/nodes/:id/users/:name/stop`
Остановить контейнер. Перед остановкой сохраняет снапшот трафика в БД.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /api/nodes/:id/users/:name/start`
Запустить контейнер. Устанавливает статус `active` в БД.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /api/nodes/:id/users/:name/reset-traffic`
Сбросить счётчики трафика перезапуском контейнера (Docker stats сбрасываются при рестарте).
Перед сбросом накапливает текущий трафик в `total_traffic_*_bytes`. Очищает `traffic_rx_snap`/`traffic_tx_snap`, устанавливает `traffic_reset_at`.

**Ответ:**
```json
{ "ok": true }
```

---

#### `GET /api/nodes/:id/users/:name/history`
История подключений (до 48 записей ≈ 4 часа, пишется каждые 5 минут). Записи от старых к новым.

**Ответ:**
```json
[
  { "connections": 2, "recorded_at": "2026-03-19T10:00:00" },
  { "connections": 3, "recorded_at": "2026-03-19T10:05:00" }
]
```

---

#### `POST /api/nodes/:id/sync`
Импортировать существующих пользователей с узла, которых нет в БД. Читает удалённый узел через SSH.

**Ответ:**
```json
{ "imported": 3, "total": 5 }
```

---

### TOTP / 2FA

Все TOTP-эндпоинты требуют `x-auth-token`, но освобождены от проверки TOTP-кода.

#### `GET /api/totp/status`
Проверить, включена ли 2FA.

**Ответ:**
```json
{ "enabled": false }
```

---

#### `POST /api/totp/setup`
Сгенерировать новый TOTP-секрет и QR URI. 2FA ещё не включается — нужно вызвать `/verify`.

**Ответ:**
```json
{
  "secret": "BASE32SECRETHERE",
  "qr": "otpauth://totp/MTG%20Admin:admin?secret=BASE32SECRETHERE&issuer=MTG%20Admin"
}
```

---

#### `POST /api/totp/verify`
Проверить TOTP-код и включить 2FA при успехе.

**Тело запроса:**
```json
{ "code": "123456" }
```

**Ответ:**
```json
{ "ok": true }
// или:
{ "error": "Invalid code" }  // HTTP 400
{ "error": "Setup first" }   // HTTP 400 (секрет ещё не сгенерирован)
```

---

#### `POST /api/totp/disable`
Отключить 2FA. Требует текущий TOTP-код для подтверждения.

**Тело запроса:**
```json
{ "code": "123456" }
```

**Ответ:**
```json
{ "ok": true }
// или:
{ "error": "Invalid code" }  // HTTP 400
```

---

## MTG Agent API (порт `agent_port` на каждом узле)

Агент — FastAPI-сервис, работающий непосредственно на прокси-узле. Держит in-memory кеш, обновляемый каждые 5 секунд.

#### `GET /health`
Аутентификация не требуется.

**Ответ:**
```json
{ "status": "ok", "version": "2.2.1" }
```

---

#### `GET /metrics`
Метрики всех MTG-контейнеров. Из кеша (при холодном старте возвращает пустой список).

**Ответ:**
```json
{
  "containers": [
    {
      "name": "alice",
      "running": true,
      "status": "running",
      "connections": 3,
      "devices": 3,
      "is_online": true,
      "traffic": {
        "rx": "54.17MB",
        "tx": "56.24MB",
        "rx_bytes": 56797474,
        "tx_bytes": 58972294
      }
    }
  ],
  "total": 1,
  "cached_at": "2026-03-19T10:00:00.000000"
}
```

`connections` и `devices` — одно значение: количество уникальных удалённых IP, подключённых к порту 3128 (читается из `/proc/{pid}/net/tcp` и `/proc/{pid}/net/tcp6`).

---

#### `GET /users`
Полный список контейнеров из кеша, включая порт и секрет (читается из `config.toml` и `docker-compose.yml`).

**Ответ:**
```json
[
  {
    "name": "alice",
    "port": 4433,
    "secret": "ee7a3b...676f6f676c652e636f6d",
    "running": true,
    "status": "running",
    "connections": 3,
    "is_online": true,
    "traffic": {
      "rx": "54.17MB", "tx": "56.24MB",
      "rx_bytes": 56797474, "tx_bytes": 58972294
    }
  }
]
```

---

#### `POST /users`
Создать новый MTG-прокси контейнер. Генерирует случайный секрет, ищет свободный порт, пишет конфиг, запускает `docker compose up -d`.

**Тело запроса:**
```json
{ "name": "alice" }
```
Имя должно соответствовать `^[a-zA-Z0-9_-]{1,32}$`.

**Ответ:**
```json
{ "name": "alice", "port": 4433, "secret": "ee...", "status": "running" }
```

**Ошибки:** `400` (невалидное имя), `409` (пользователь существует), `500` (ошибка Docker).

---

#### `DELETE /users/{name}`
Остановить и удалить контейнер, удалить директорию конфига.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /users/{name}/start`
Запустить контейнер.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /users/{name}/stop`
Остановить контейнер.

**Ответ:**
```json
{ "ok": true }
```

---

#### `POST /users/{name}/restart`
Перезапустить контейнер.

**Ответ:**
```json
{ "ok": true }
```

---

#### `GET /version`
Получить дату сборки MTG Docker-образа.

**Ответ:**
```json
{ "image": "nineseconds/mtg:2", "created": "2025-12-01T00:00:00Z" }
```

---

#### `POST /pull`
Скачать последний MTG Docker-образ (`docker pull nineseconds/mtg:2`). Может занимать до 120 секунд.

**Ответ:**
```json
{ "ok": true, "output": "Digest: sha256:...\nStatus: Image is up to date" }
```

---

## Ключевые особенности

### Источники данных и кеш

| Эндпоинт | Источник | Задержка | Трафик |
|----------|----------|----------|--------|
| `GET /api/nodes/:id/summary` | Кеш панели (SSH каждые 10с) | ~0ms | `rx`/`tx` строки + `rx_bytes`/`tx_bytes` |
| `GET /api/nodes/:id/users` | Кеш панели | ~0ms | `traffic_rx`/`traffic_tx` плоские строки |
| `GET /api/nodes/:id/traffic` | Прямой SSH | ~сотни ms | `rx`/`tx` строки только |
| `GET /metrics` (агент) | Кеш агента (каждые 5с) | ~0ms | `rx_bytes`/`tx_bytes` + строки |

После мутаций (create/delete/start/stop) кеш узла принудительно обновляется.

### Формат прокси-ссылки
```
tg://proxy?server={host}&port={port}&secret={secret}
```

### Формат секрета
`ee` + 16 случайных hex-байт + `google.com` в hex = строка из 62 hex-символов.
Это формат MTG "fake TLS" секрета.

### Валидация имён пользователей
Панель: `^[a-zA-Z0-9_-]{1,32}$`
Бот использует формат `tg_{telegram_id}`, удовлетворяющий этому regex.

### TOTP session flow
1. Первый запрос с валидным TOTP-кодом → панель отвечает с `x-totp-session: <token>`
2. Следующие запросы: передавать этот токен в `x-totp-code` вместо нового кода
3. Токен действителен 24 часа
