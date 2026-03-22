# MTG Proxy Bot

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://github.com/aiogram/aiogram)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

Telegram-бот + веб-приложение для управления MTProto-прокси. Интегрируется с **[MTG Admin Panel](https://github.com/MaksimTMB/mtg-adminpanel)** через HTTP REST API и предоставляет пользователям интерфейс для создания и управления прокси как через бот, так и через браузер или Telegram Mini App.

## Содержание

- [Возможности](#возможности)
- [Стек](#стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Настройка Nginx](#настройка-nginx)
- [Структура проекта](#структура-проекта)
- [Команды](#команды)

---

## Возможности

### Для пользователей (бот)

- Получение MTProto-прокси на выбранной ноде (одна нода — один прокси)
- Список своих прокси с текущим статусом, количеством устройств и лимитами
- QR-код и ссылка для быстрого подключения (`tg://proxy?...`)
- Удаление прокси с подтверждением
- **Реферальная система** — кнопка «Поделиться» отправляет реферальную ссылку на бота; при желании в текст можно включить и сам прокси (`SHARE_PROXY_ON_INVITE_ENABLED`)
- **FAQ** — встроенный раздел вопросов и ответов

### Для пользователей (веб-приложение)

- Авторизация через **email** (код подтверждения на почту), **Telegram Login Widget** или **Telegram Mini App** (автоматически)
- Список и создание прокси с выбором сервера
- Детальная страница прокси: QR-код, ссылка, кнопка копирования
- **Привязка Telegram-аккаунта** к email-аккаунту (`/link <код>` в боте)
- Страница аккаунта: имя, email, статус подтверждения, привязанный Telegram

### Для администраторов

- **Дашборд нод** — статус онлайн/офлайн, активные соединения, трафик
- **Управление пользователями** — список, поиск, бан/разбан, удаление с каскадным удалением прокси
- **Редактирование прокси** — лимиты устройств, трафика, срок действия, сброс трафика
- **Настройки по умолчанию** — дефолтные значения `max_devices`, `traffic_limit_gb`, `expires_days`, `traffic_reset_interval`
- **Управление FAQ** — добавление, редактирование, удаление и сортировка вопросов
- **Рассылка** — HTML-сообщения всем незабаненным пользователям с прогресс-трекингом
- Синхронизация нод из удалённой панели, включение/выключение нод

---

## Стек

| Слой | Технология |
|------|-----------|
| Bot framework | [aiogram](https://github.com/aiogram/aiogram) 3.x |
| Web-сервер (бот) | aiohttp (webhook) |
| REST API | FastAPI + uvicorn |
| Аутентификация | JWT (python-jose), email OTP, Telegram Widget/Mini App |
| Email | [Resend](https://resend.com) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| HTTP-клиент | httpx (async) |
| TOTP 2FA | pyotp |
| Rate limiting | Redis (asyncio) |
| QR-коды | qrcode[pil] |
| Конфигурация | pydantic-settings |
| Миграции | Alembic |
| База данных | PostgreSQL 17 |
| Кэш | Redis 7 |
| Фронтенд | React 19 + Vite + TypeScript |
| UI-компоненты | shadcn/ui + Tailwind CSS |
| Деплой | Docker Compose + nginx |

---

## Архитектура

```
Telegram (HTTPS POST /mtg-webhook)
        │
        ▼
     nginx (443 SSL)  ◄──── Браузер / Telegram Mini App
        │                         │
        │                         ▼ /api/, /auth/
        ▼                   FastAPI :8000
MTG Proxy Bot — aiohttp :8080     │
        │                         │
        └─────────┬───────────────┘
                  ▼
       MTG Admin Panel (HTTP REST API)  ←  TOTP 2FA (опционально)
                  │
                  ▼
       MTG Agent (agent_port на каждой ноде)
                  │
                  ▼
       PostgreSQL + Redis
```

Бот поддерживает два режима работы, управляемых переменной `WEBHOOK_MODE_ENABLED`:
- **Webhook** (`True`, рекомендуется для продакшна) — Telegram присылает апдейты на HTTPS-эндпоинт.
- **Polling** (`False`, для локальной разработки) — бот опрашивает Telegram API.

---

## Быстрый старт

### Требования

- Docker и Docker Compose (`sudo curl -fsSL https://get.docker.com | sh`)
- Работающая [MTG Admin Panel](https://github.com/MaksimTMB/mtg-adminpanel)
- Домен (или субдомены) с A-записями, указывающими на сервер
- Nginx с SSL-сертификатами

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/vaqybin/mtg-proxy-bot.git
cd mtg-proxy-bot

# Скопировать и заполнить конфиг
cp .env.example .env
nano .env

# Запустить (продакшн)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f
```

Миграции применяются автоматически при старте контейнера `bot`.

### Обновление

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## Конфигурация

Отредактируйте `.env` и заполните значения:

### Основные параметры

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | ✅ | Список Telegram ID администраторов, например `[123456789, 987654321]` |
| `ADMIN_PANEL_URL` | ✅ | URL MTG Admin Panel, например `http://panel-host:3000` |
| `ADMIN_PANEL_TOKEN` | ✅ | Токен доступа к Admin Panel |
| `AGENT_TOKEN` | ✅ | Секрет MTG-агента |
| `ADMIN_PANEL_TOTP_SECRET` | ❌ | TOTP-секрет для 2FA панели (если включена) |
| `SHARE_PROXY_ON_INVITE_ENABLED` | ❌ | Включать ли прокси-ссылку при шаринге. По умолчанию `False` |
| `VPN_ADS_ON_SHARE_LINK` | ❌ | Ссылка на VPN-сервис для рекламы в кнопке «Поделиться» |
| `POSTGRES_USER` | ✅ | Имя пользователя PostgreSQL |
| `POSTGRES_PASSWORD` | ✅ | Пароль PostgreSQL |
| `POSTGRES_DB` | ✅ | Имя базы данных |
| `POSTGRES_HOST` | ✅ | Хост PostgreSQL (в Docker Compose — `postgres`) |
| `POSTGRES_PORT` | ✅ | Порт PostgreSQL (обычно `5432`) |
| `REDIS_HOST` | ✅ | Хост Redis (в Docker Compose — `redis`) |
| `REDIS_PORT` | ✅ | Порт Redis (обычно `6379`) |
| `REDIS_DB` | ✅ | Номер базы данных Redis (обычно `0`) |

### Webhook

| Переменная | Обязательная | Описание |
|---|---|---|
| `WEBHOOK_MODE_ENABLED` | ❌ | `True` — webhook (продакшн), `False` — polling (разработка). По умолчанию `True` |
| `WEBHOOK_BASE_URL` | ✅* | Публичный HTTPS-URL домена webhook, например `https://bot.domain.com` |
| `WEBHOOK_PATH` | ✅* | Путь эндпоинта (по умолчанию `/mtg-webhook`) |
| `WEBHOOK_SECRET` | ✅* | Случайная строка (`openssl rand -hex 16`) |
| `WEB_SERVER_HOST` | ❌ | Хост aiohttp-сервера (по умолчанию `0.0.0.0`) |
| `WEB_SERVER_PORT` | ❌ | Порт aiohttp-сервера (по умолчанию `8080`) |

> \* Обязательны только при `WEBHOOK_MODE_ENABLED=True`

### Веб-приложение и API

| Переменная | Обязательная | Описание |
|---|---|---|
| `API_SECRET_KEY` | ✅ | Секрет для подписи JWT (`openssl rand -hex 32`) |
| `JWT_EXPIRE_HOURS` | ❌ | Срок действия JWT в часах. По умолчанию `720` (30 дней) |
| `RESEND_API_KEY` | ❌ | API-ключ [Resend](https://resend.com) для отправки писем. Без него email-авторизация недоступна |
| `EMAIL_FROM` | ❌ | Адрес отправителя писем. По умолчанию `noreply@example.com` |
| `SITE_URL` | ✅ | Публичный URL веб-приложения, например `https://app.domain.com`. Используется в ссылках подтверждения email |

### Пример `.env`

```dotenv
# Telegram Bot
BOT_TOKEN=123456:ABCDef...
ADMIN_IDS=[123456789]

# MTG Admin Panel
ADMIN_PANEL_URL=http://panel-host:3000
ADMIN_PANEL_TOKEN=your-panel-token
AGENT_TOKEN=mtg-agent-secret
ADMIN_PANEL_TOTP_SECRET=
SHARE_PROXY_ON_INVITE_ENABLED=False
VPN_ADS_ON_SHARE_LINK=

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
WEBHOOK_MODE_ENABLED=True
WEBHOOK_BASE_URL=https://bot.domain.com
WEBHOOK_PATH=/mtg-webhook
WEBHOOK_SECRET=replace-with-random-secret

# Web API / JWT
API_SECRET_KEY=replace-with-random-secret
SITE_URL=https://app.domain.com

# Email (Resend) — опционально
RESEND_API_KEY=re_...
EMAIL_FROM=MTG Proxy <noreply@domain.com>
```

---

## Настройка Resend (email)

Email-авторизация работает через сервис [Resend](https://resend.com). Без него вкладка «Email» в веб-приложении недоступна — но всё остальное (Telegram-авторизация, Mini App) работает без изменений.

### 1. Получить API-ключ

1. Зарегистрируйтесь на [resend.com](https://resend.com)
2. Перейдите в **API Keys → Create API Key**
3. Скопируйте ключ — он начинается с `re_`
4. Вставьте в `.env`: `RESEND_API_KEY=re_...`

> На бесплатном плане: 100 писем в день, 3 000 в месяц. Отправка возможна только с верифицированного домена.

### 2. Верифицировать домен

Отправка писем возможна только с домена, который вы подтвердили в Resend (например, `noreply@yourdomain.com`). Домен `resend.dev` доступен только для тестирования на собственный адрес.

1. Перейдите в **Domains → Add Domain**
2. Введите ваш домен (например, `yourdomain.com`)
3. Resend покажет DNS-записи, которые нужно добавить у вашего регистратора:

| Тип | Имя | Значение |
|-----|-----|---------|
| TXT | `resend._domainkey` | DKIM-ключ (длинная строка) |
| TXT | `@` или `yourdomain.com` | SPF: `v=spf1 include:amazonses.com ~all` |
| MX | `bounce` | `feedback-smtp.us-east-1.amazonses.com` |

4. После добавления нажмите **Verify** — статус сменится на `Verified` (обычно занимает до 5 минут, иногда до часа)

### 3. Заполнить `EMAIL_FROM`

После верификации укажите адрес отправителя с вашего домена:

```dotenv
# Просто адрес
EMAIL_FROM=noreply@yourdomain.com

# С именем (рекомендуется — выглядит лучше в почтовом клиенте)
EMAIL_FROM=MTG Proxy <noreply@yourdomain.com>
```

### 4. Проверить отправку

```bash
curl -X POST https://app.domain.com/auth/email/register \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com"}'
```

Ожидаемый ответ: `202 Accepted`. Письмо придёт в течение нескольких секунд.

> **Режим разработки:** если `RESEND_API_KEY` не задан — письмо не отправляется, код выводится в логи контейнера `api`:
> ```bash
> docker compose logs api | grep "Verification code"
> ```

---

## Настройка Nginx

Проект использует **два виртуальных хоста**:

| Хост | Назначение | Проксирует на |
|---|---|---|
| `bot.domain.com` | Telegram webhook | `127.0.0.1:8080` |
| `app.domain.com` | Веб-приложение + API | `127.0.0.1:3000` |

### DNS

Создайте A-записи, указывающие на IP сервера:
```
bot.domain.com.  A  <IP>
app.domain.com.  A  <IP>
```

### Конфиг для webhook (бот)

```nginx
server {
    server_name bot.domain.com;
    listen 443 ssl;
    http2 on;

    ssl_certificate     /etc/nginx/ssl/bot/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/bot/privkey.key;

    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    location /mtg-webhook {
        proxy_pass http://127.0.0.1:8080;
    }

    location / {
        return 404;
    }
}
```

### Конфиг для веб-приложения

```nginx
server {
    server_name app.domain.com;
    listen 443 ssl;
    http2 on;

    ssl_certificate     /etc/nginx/ssl/app/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/app/privkey.key;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> Web-контейнер на порту 3000 сам обрабатывает статику React и проксирует `/api/` и `/auth/` во внутренний FastAPI-контейнер.

### Настройка Telegram Mini App

Чтобы веб-приложение открывалось как Mini App:

1. В [@BotFather](https://t.me/BotFather) выполните `/newapp` (или `/myapps` для существующего бота)
2. Укажите URL: `https://app.domain.com`
3. Установите **Menu Button** или используйте `setMenuButton` через Bot API

### Проверка webhook

```bash
curl https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo
```

Ожидаемый ответ:
```json
{
  "url": "https://bot.domain.com/mtg-webhook",
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
│   ├── models/                  # ORM-модели
│   │   ├── user.py              # User
│   │   ├── node.py              # Node
│   │   ├── proxy.py             # Proxy
│   │   ├── settings.py          # ProxySettings (singleton)
│   │   ├── faq.py               # FAQItem
│   │   ├── email_verification.py
│   │   └── account_link_token.py
│   ├── dao/                     # Data Access Objects
│   │   ├── user.py
│   │   ├── node.py
│   │   ├── proxy.py
│   │   ├── settings.py
│   │   ├── faq.py
│   │   ├── email_verification.py
│   │   └── account_link_token.py
│   ├── handlers/
│   │   ├── common.py            # /start, главное меню
│   │   ├── proxy.py             # Пользовательский флоу прокси
│   │   ├── faq.py               # Пользовательский FAQ
│   │   ├── link.py              # /link <код> — привязка Telegram к web-аккаунту
│   │   └── admin/
│   │       ├── dashboard.py
│   │       ├── users.py
│   │       ├── proxy_edit.py
│   │       ├── settings.py
│   │       ├── faq.py
│   │       └── broadcast.py
│   ├── middleware/
│   │   ├── db.py
│   │   ├── ban.py
│   │   └── throttling.py
│   ├── services/
│   │   └── admin_panel.py       # AdminPanelClient
│   └── utils/
│       ├── qr.py
│       └── flags.py
├── api/                         # FastAPI REST API
│   ├── main.py                  # FastAPI app
│   ├── deps.py                  # Зависимости (сессия БД, текущий пользователь)
│   ├── jwt.py                   # Создание и проверка JWT
│   ├── email_service.py         # Отправка писем через Resend
│   └── routers/
│       ├── auth.py              # Email OTP, Telegram Widget, Mini App
│       ├── users.py             # GET /api/me, POST /api/me/link-request
│       ├── proxies.py           # CRUD прокси
│       └── health.py
├── web/                         # React SPA (Vite + TypeScript)
│   ├── src/
│   │   ├── api/                 # Клиент API (fetch-обёртки)
│   │   ├── components/ui/       # shadcn/ui компоненты
│   │   ├── hooks/               # useAuth
│   │   ├── lib/                 # telegram.ts (isMiniApp)
│   │   ├── pages/               # LoginPage, ProxiesPage, ProxyDetailPage, AccountPage
│   │   └── types/               # telegram.d.ts
│   ├── Dockerfile               # Multi-stage: node builder → nginx
│   ├── nginx.conf               # SPA + proxy /api/ /auth/ → api:8000
│   └── index.html
├── docs/
│   └── email_preview.html       # Превью шаблона письма (открыть в браузере)
├── alembic/
│   └── versions/
├── docker-compose.yml           # Dev-окружение (с volume-монтированием)
├── docker-compose.prod.yml      # Продакшн (pull из GHCR)
├── Dockerfile                   # Python образ (bot + api)
├── entrypoint.sh                # Миграции + запуск бота
├── entrypoint-api.sh            # Запуск FastAPI
└── pyproject.toml
```

### Схема БД

**users** — `telegram_id`, `email`, `email_verified`, `username`, `first_name`, `last_name`, `display_name`, `is_banned`, `referred_by_id`, `created_at`

**nodes** — `panel_id`, `name`, `host`, `flag`, `agent_port`, `is_active`

**proxies** — `user_id`, `node_id`, `mtg_username`, `link`, `port`, `secret`, `tme_link`, `expires_at`, `traffic_limit_gb`, `is_active`

**proxy_settings** — singleton: `max_devices`, `traffic_limit_gb`, `expires_days`, `traffic_reset_interval`, `faq_enabled`

**faq_items** — `question`, `answer`, `position`, `created_at`

**email_verifications** — `email`, `code`, `token`, `used`, `expires_at`

**account_link_tokens** — `user_id`, `code`, `used`, `expires_at`

---

## Команды

### Разработка

```bash
# Запуск (dev)
docker compose up -d
docker compose logs -f bot

# Перезапуск после изменений Python-кода (volume примонтирован, пересборка не нужна)
docker compose up -d --force-recreate bot api

# Перезапуск после изменений фронтенда
docker compose up -d --build web

# Миграции
docker exec mtg-proxy-bot alembic upgrade head
docker exec mtg-proxy-bot alembic revision --autogenerate -m "description"

# Линтер
flake8 bot/ api/
```

### Продакшн

```bash
# Обновление до последней версии
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Логи
docker compose -f docker-compose.prod.yml logs -f bot
docker compose -f docker-compose.prod.yml logs -f api
```
