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
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| HTTP-клиент | httpx (async) |
| TOTP 2FA | pyotp |
| Rate limiting | Redis (asyncio) |
| QR-коды | qrcode[pil] |
| Конфигурация | pydantic-settings |
| Миграции | Alembic |
| База данных | PostgreSQL 17 |
| Кэш | Redis 7 |
| Деплой | Docker Compose |

---

## Архитектура

```
Telegram Bot (aiogram)
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

### Ключевые потоки данных

1. **Создание прокси**: пользователь → `AdminPanelClient.create_user()` → панель создаёт пользователя на ноде → запись в БД
2. **Просмотр прокси**: `get_node_summary()` (кэш панели, ~10с TTL) → актуальные данные по соединениям и устройствам
3. **Дашборд ноды**: `get_node_summary()` + `get_node_traffic()` параллельно

### Аутентификация панели

Панель поддерживает опциональный TOTP 2FA. При задании `ADMIN_PANEL_TOTP_SECRET` клиент генерирует 6-значный код и кэширует session-токен из заголовка `x-totp-session` на 24 часа — новый код генерируется только при 403.

---

## Быстрый старт

### Требования

- Docker и Docker Compose
- Работающая [MTG Admin Panel](https://github.com/MaksimTMB/mtg-adminpanel)

### Установка

```bash
git clone https://github.com/VAQYBIN/mtg-proxy-bot.git
cd mtg-proxy-bot

cp .env.example .env
# Заполнить .env (см. раздел Конфигурация)

docker compose up -d
docker compose logs -f bot
```

Миграции применяются автоматически при старте контейнера.

### Продакшн-деплой

Используйте `docker-compose.prod.yml` — он использует собранный образ из registry и `restart: always`:

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните:

```dotenv
# Telegram Bot
BOT_TOKEN=123456:ABCDef...
ADMIN_IDS=[123456789, 987654321]     # ID администраторов через запятую

# MTG Admin Panel
ADMIN_PANEL_URL=http://panel-host:3000
ADMIN_PANEL_TOKEN=your-panel-token
AGENT_TOKEN=mtg-agent-secret
ADMIN_PANEL_TOTP_SECRET=              # TOTP-секрет, опционально

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
```

---

## Структура проекта

```
mtg-proxy-bot/
├── bot/
│   ├── main.py                  # Точка входа, регистрация роутеров и middleware
│   ├── config.py                # Настройки (pydantic-settings)
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
