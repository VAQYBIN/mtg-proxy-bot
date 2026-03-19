# MTG Proxy Bot

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://github.com/aiogram/aiogram)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

Telegram-бот для управления MTProto-прокси. Интегрируется с **[MTG Admin Panel](https://github.com/MaksimTMB/mtg-adminpanel)** через HTTP REST API и предоставляет пользователям интерфейс для создания и управления прокси, а администраторам — полный контроль над нодами и пользователями.

## Содержание

- [Возможности](#возможности)
- [Стек](#стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Настройка Webhook](#настройка-webhook)
- [Структура проекта](#структура-проекта)
- [Команды](#команды)

---

## Возможности

### Для пользователей

- Получение MTProto-прокси на выбранной ноде (одна нода — один прокси)
- Список своих прокси с текущим статусом, количеством устройств и лимитами
- QR-код и ссылка для быстрого подключения (`tg://proxy?...`)
- Удаление прокси с подтверждением

### Для администраторов

- **Дашборд нод** — статус онлайн/офлайн, активные соединения, трафик
- **Управление пользователями** — список, поиск по username или Telegram ID, бан/разбан, удаление с каскадным удалением прокси
- **Рассылка** — HTML-сообщения всем незабаненным пользователям с прогресс-трекингом
- Синхронизация нод из удалённой панели, включение/выключение нод

---

## Стек

| Слой | Технология |
|------|-----------|
| Bot framework | [aiogram](https://github.com/aiogram/aiogram) 3.x |
| Web-сервер | aiohttp (webhook) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| HTTP-клиент | httpx (async) |
| TOTP 2FA | pyotp |
| Rate limiting | Redis (asyncio) |
| QR-коды | qrcode[pil] |
| Конфигурация | pydantic-settings |
| Миграции | Alembic |
| База данных | PostgreSQL 17 |
| Кэш | Redis 7 |
| Деплой | Docker Compose + nginx |

---

## Архитектура

```
Telegram (HTTPS POST /mtg-webhook)
        │
        ▼
     nginx (443 SSL)
        │
        ▼
MTG Proxy Bot — aiohttp :8080
        │
        ▼
MTG Admin Panel (HTTP REST API)   ←  TOTP 2FA (опционально)
        │
        ▼
MTG Agent (agent_port на каждой ноде)
        │
        ▼
PostgreSQL + Redis
```

Бот работает в режиме **webhook**: Telegram сам присылает апдейты на HTTPS-эндпоинт, проксируемый через nginx. Это исключает постоянный polling-цикл и снижает задержку обработки сообщений.

### Ключевые потоки данных

1. **Создание прокси**: пользователь → `AdminPanelClient.create_user()` → панель создаёт пользователя на ноде → запись в БД
2. **Просмотр прокси**: `get_node_summary()` (кэш панели, ~10с TTL) → актуальные данные по соединениям и устройствам
3. **Дашборд ноды**: `get_node_summary()` + `get_node_traffic()` параллельно

### Аутентификация панели

Панель поддерживает опциональный TOTP 2FA. При задании `ADMIN_PANEL_TOTP_SECRET` клиент генерирует 6-значный код и кэширует session-токен из заголовка `x-totp-session` на 24 часа — новый код генерируется только при 403.

---

## Быстрый старт

### Требования

- Docker и Docker Compose (`sudo curl -fsSL https://get.docker.com | sh`)
- Работающая [MTG Admin Panel](https://github.com/MaksimTMB/mtg-adminpanel)
- Домен с A-записью, указывающей на сервер (нужен для webhook)
- Nginx с SSL-сертификатом для этого домена

### Установка

```bash
bash <(curl -fsSL git.new/mtg-bot-docker -o docker-compose.yml)

bash <(curl -fsSL git.new/mtg-bot-env -o .env)

# Заполнить .env (см. раздел Конфигурация)
nano .env

docker compose up -d && docker compose logs -f
```

Миграции применяются автоматически при старте контейнера.

### Обновление

```bash
docker compose pull && docker compose down && docker compose up -d && docker compose logs -f
```

---

## Конфигурация

Отредактируйте `.env` и заполните значения:

### Основные параметры

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | ✅ | Список Telegram ID администраторов, например `[123456789, 987654321]` |
| `ADMIN_PANEL_URL` | ✅ | URL MTG Admin Panel, например `http://panel-host:3000` или `https://host.panel.com` |
| `ADMIN_PANEL_TOKEN` | ✅ | Токен доступа к Admin Panel (из .env панели) |
| `AGENT_TOKEN` | ✅ | Секрет MTG-агента (из .env панели) |
| `ADMIN_PANEL_TOTP_SECRET` | ❌ | TOTP-секрет для 2FA панели (если включена) |
| `POSTGRES_USER` | ✅ | Имя пользователя PostgreSQL |
| `POSTGRES_PASSWORD` | ✅ | Пароль PostgreSQL |
| `POSTGRES_DB` | ✅ | Имя базы данных PostgreSQL |
| `POSTGRES_HOST` | ✅ | Хост PostgreSQL (в Docker Compose — `postgres`) |
| `POSTGRES_PORT` | ✅ | Порт PostgreSQL (обычно `5432`) |
| `REDIS_HOST` | ✅ | Хост Redis (в Docker Compose — `redis`) |
| `REDIS_PORT` | ✅ | Порт Redis (обычно `6379`) |
| `REDIS_DB` | ✅ | Номер базы данных Redis (обычно `0`) |

### Webhook

| Переменная | Обязательная | Описание |
|---|---|---|
| `WEBHOOK_BASE_URL` | ✅ | Публичный HTTPS-URL домена, например `https://webhook.domain.com` |
| `WEBHOOK_PATH` | ✅ | Путь эндпоинта (по умолчанию `/mtg-webhook`) |
| `WEBHOOK_SECRET` | ✅ | Случайная строка для верификации запросов от Telegram (`openssl rand -hex 16`) |
| `WEB_SERVER_HOST` | ❌ | Хост aiohttp-сервера (по умолчанию `0.0.0.0`) |
| `WEB_SERVER_PORT` | ❌ | Порт aiohttp-сервера (по умолчанию `8080`) |

### Пример `.env`

```dotenv
# Telegram Bot
BOT_TOKEN=123456:ABCDef...
ADMIN_IDS=[123456789, 987654321]

# MTG Admin Panel
ADMIN_PANEL_URL=http://panel-host:3000
ADMIN_PANEL_TOKEN=your-panel-token
AGENT_TOKEN=mtg-agent-secret
ADMIN_PANEL_TOTP_SECRET=

# PostgreSQL
POSTGRES_USER=bot
POSTGRES_PASSWORD=secret
POSTGRES_DB=mtg_bot
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Webhook
WEBHOOK_BASE_URL=https://webhook.domain.com
WEBHOOK_PATH=/mtg-webhook
WEBHOOK_SECRET=replace-with-random-secret
WEB_SERVER_HOST=0.0.0.0
WEB_SERVER_PORT=8080
```

---

## Настройка Webhook

### 1. DNS — A-запись

Создайте A-запись, указывающую на IP вашего сервера:

```
webhook.domain.com.  A  <IP-адрес сервера>
```

Telegram требует, чтобы webhook-эндпоинт был доступен по HTTPS на 443, 80, 88 или 8443 порту. Nginx терминирует TLS и проксирует запросы на внутренний порт `8080` контейнера.

### 2. Конфигурация nginx

```nginx
upstream mtg-proxy-bot {
    server mtg-proxy-bot:8080;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    "" close;
}

server {
    server_name webhook.domain.com;
    listen 443 ssl;
    http2 on;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.key;
    ssl_trusted_certificate /etc/nginx/ssl/fullchain.pem;

    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header Upgrade           $http_upgrade;
    proxy_set_header Connection        $connection_upgrade;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;
    proxy_set_header X-Forwarded-Port  $server_port;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_intercept_errors on;
    error_page 400 404 500 502 @redirect;

    location /mtg-webhook {
        proxy_pass http://mtg-proxy-bot$request_uri;
    }

    location @redirect {
        return 404;
    }
}
```

> Если nginx запущен вне Docker-сети бота, замените `server mtg-proxy-bot:8080` на `server 127.0.0.1:8080` и убедитесь, что в `docker-compose.yml` есть `ports: ["127.0.0.1:8080:8080"]`.

### 3. Проверка

После запуска бота и применения конфига nginx:

```bash
# Убедиться, что бот слушает порт
docker compose logs bot | grep "Running on"

# Проверить регистрацию webhook в Telegram
curl https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

Ожидаемый ответ:

```json
{
  "url": "https://webhook.domain.com/mtg-webhook",
  "has_custom_certificate": false,
  "pending_update_count": 0,
  "secret_token_set": true
}
```

---

## Структура проекта

```
mtg-proxy-bot/
├── bot/
│   ├── main.py                  # Точка входа, регистрация роутеров и middleware
│   ├── config.py                # Настройки (pydantic-settings)
│   ├── web_server.py            # aiohttp webhook-сервер
│   ├── database.py              # SQLAlchemy engine
│   ├── callbacks.py             # CallbackData-классы aiogram
│   ├── filters.py               # AdminFilter
│   ├── models/                  # ORM-модели
│   │   ├── user.py              # User
│   │   ├── node.py              # Node (proxy-нода)
│   │   └── proxy.py             # Proxy (прокси пользователя)
│   ├── dao/                     # Data Access Objects (тонкие обёртки над SQLAlchemy)
│   │   ├── user.py
│   │   ├── node.py
│   │   └── proxy.py
│   ├── handlers/
│   │   ├── common.py            # /start, главное меню
│   │   ├── proxy.py             # Пользовательский флоу прокси
│   │   └── admin/
│   │       ├── dashboard.py     # Дашборд нод
│   │       ├── users.py         # Управление пользователями
│   │       └── broadcast.py     # Рассылка
│   ├── middleware/
│   │   ├── db.py                # Инжекция AsyncSession в хендлеры
│   │   ├── ban.py               # Блокировка забаненных пользователей
│   │   └── throttling.py        # Rate limiting через Redis (500мс cooldown)
│   ├── services/
│   │   └── admin_panel.py       # AdminPanelClient — все запросы к панели
│   └── utils/
│       ├── qr.py                # Генерация QR-кодов
│       └── flags.py             # Код страны → флаг-эмодзи
├── alembic/
│   └── versions/                # Миграции БД
├── docker-compose.yml           # Dev-окружение
├── docker-compose.prod.yml      # Продакшн
├── Dockerfile
├── entrypoint.sh                # Запуск миграций + бот
└── pyproject.toml
```

### Схема БД

**users** — `telegram_id`, `username`, `first_name`, `is_banned`, `created_at`

**nodes** — `panel_id` (ID на удалённой панели), `name`, `host`, `flag`, `agent_port`, `is_active`

**proxies** — `user_id`, `node_id`, `mtg_username` (формат `tg_{telegram_id}`), `link`, `port`, `secret`, `expires_at`, `traffic_limit_gb`, `is_active`

---

## Команды

### Разработка

```bash
# Запуск
docker compose up -d
docker compose logs -f bot

# Перезапуск после изменений кода (пересборка не нужна, volume примонтирован)
docker compose up -d --force-recreate bot

# Миграции
docker exec mtg-proxy-bot alembic upgrade head
docker exec mtg-proxy-bot alembic revision --autogenerate -m "description"

# Линтер
flake8 bot/
```
