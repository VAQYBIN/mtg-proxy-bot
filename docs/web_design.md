# Web Interface & Mini App — Design Document

> Статус: **Проектирование**
> Последнее обновление: 2026-03-22

## Принятые решения

| Вопрос | Решение | Обоснование |
|--------|---------|-------------|
| Email-сервис | **Resend** | Простой API, 3000 писем/месяц бесплатно, Python SDK |
| Frontend | **React + Vite** | SPA, собирается в статику → nginx, не нужен Node.js сервер |
| Mini App | Та же React-сборка | Один `if` для определения контекста запуска |

---

## Цель

Добавить веб-интерфейс и Telegram Mini App поверх существующего бота, с общей БД и бизнес-логикой. Пользователь может управлять своими прокси как через Telegram-бот, так и через сайт.

**Приоритет:** Пользователь без доступа к Telegram регистрируется на сайте по email → получает прокси → подключается → опционально привязывает Telegram-аккаунт.

---

## Архитектурная схема

```
[Telegram Bot]     [Website]     [Mini App]
       │               │               │
       └───────────────┴───────────────┘
                       │
               [FastAPI Backend]
                       │
            ┌──────────┴──────────┐
       [bot/services/]      [bot/dao/]
       [admin_panel.py]    [SQLAlchemy]
                       │
              [PostgreSQL] [Redis]
```

Один бэкенд, три интерфейса. Бот и API импортируют один и тот же `bot/services/` и `bot/dao/`.

---

## Чеклист реализации

### Фаза 0: Проектирование (текущая)
- [x] Анализ существующих моделей и DAO
- [x] Проектирование изменений User модели
- [x] Проектирование схемы авторизации
- [x] Проектирование API endpoints
- [ ] Проверка: ревью документа, нет противоречий

### Фаза 1: Изменения схемы БД ✅
- [x] 1.1 Обновить модель `User` (telegram_id → nullable, добавить email, email_verified, display_name)
- [x] 1.2 Создать модель `EmailVerification` (OTP код + UUID токен, TTL, user_id nullable)
- [x] 1.3 Создать модель `AccountLinkToken` (короткий код для /link в боте)
- [x] 1.4 Написать Alembic-миграцию `e5f6a7b8c9d0`
- [x] 1.5 Обновить `UserDAO` (get_by_email, create_email_user, link_telegram, link_email, merge_into, fix get_all_ids)
- [x] **Проверка:** миграция применена (`d4e5f6a7b8c9 → e5f6a7b8c9d0`), бот запущен, ошибок нет

### Фаза 2: FastAPI — основа ✅
- [x] 2.1 Создать `api/` — `main.py`, `deps.py`, `jwt.py`, `routers/health.py`
- [x] 2.2 Shared подключение к БД через `bot/database.py` (async_session_factory)
- [x] 2.3 Добавить `api` сервис в `docker-compose.yml`, `entrypoint-api.sh`
- [x] 2.4 JWT: `create_access_token` / `decode_access_token` (HS256, python-jose)
- [x] 2.5 Добавить `fastapi`, `uvicorn[standard]`, `python-jose[cryptography]` в `pyproject.toml`
- [x] 2.6 Добавить новые env vars в `bot/config.py` (API_SECRET_KEY, JWT_EXPIRE_HOURS, RESEND_API_KEY, EMAIL_FROM, SITE_URL)
- [x] **Проверка:** `GET /health` → `{"status":"ok","db":"ok"}`, JWT encode/decode работает, UserDAO из API доступен

### Фаза 3: Авторизация ✅
- [x] 3.1 `POST /auth/email/register` → 202, код в логах (fallback) или Resend
- [x] 3.2 `POST /auth/email/verify {email, code}` → JWT; неверный/истёкший → 400
- [x] 3.3 `GET /auth/email/verify?token=` → JWT по ссылке из письма
- [x] 3.4 `POST /auth/email/resend` → аннулирует старые коды, создаёт новый
- [x] 3.5 `POST /auth/telegram/widget` → HMAC-SHA256 верификация + JWT; невалидный hash → 401; устаревший auth_date → 401
- [x] 3.6 `POST /auth/telegram/miniapp` → WebAppData HMAC верификация + JWT
- [x] 3.7 `bot/dao/email_verification.py` — EmailVerificationDAO (create, get_active_by_code, get_active_by_token, mark_used, invalidate_pending)
- [x] 3.8 `api/email_service.py` — Resend интеграция с fallback на лог
- [x] **Проверка:** все 5 endpoints возвращают JWT; повторный вход тем же email → тот же user_id; использованный код → 400; неверный hash → 401

### Фаза 4: API — пользователь ✅
- [x] 4.1 `GET /api/me` → профиль; без токена → 401; невалидный токен → 401
- [x] 4.2 `GET /api/nodes` → список активных нод
- [x] 4.3 `GET /api/proxies` → список прокси пользователя (пустой для нового)
- [x] 4.4 `POST /api/proxies {node_id}` → 201 + proxy; дубль → 409; несуществующая нода → 404
- [x] 4.5 `DELETE /api/proxies/{id}` → 204; чужой → 403; повторно → 404
- [x] 4.6 `GET /api/proxies/{id}/stats` → connections/max_devices/traffic из panel summary
- [x] Примечание: mtg_username для web-юзеров = `web_{user.id}`, для Telegram = `tg_{telegram_id}`
- [x] **Проверка:** все статус-коды верные, прокси создаётся и удаляется на панели, stats возвращает данные

### Фаза 5: Привязка аккаунтов
- [ ] 5.1 `POST /api/me/link/request` — запрос кода привязки (для web-пользователя)
- [ ] 5.2 Команда в боте `/link <код>` — привязка Telegram к web-аккаунту
- [ ] 5.3 `POST /api/me/link/miniapp` — привязка через Mini App (автоматически)
- [ ] 5.4 Стратегия merge: что делать если у обоих аккаунтов есть прокси
- [ ] **Проверка:** все три сценария привязки работают без потери данных

### Фаза 6: Frontend (сайт)
- [ ] 6.1 Настройка проекта (React + Vite + TypeScript)
- [ ] 6.2 Страница входа (email форма + Telegram Login Widget)
- [ ] 6.3 Главная страница — список прокси
- [ ] 6.4 Страница прокси — детали, статистика, QR-код
- [ ] 6.5 Страница привязки аккаунта
- [ ] **Проверка:** полный пользовательский сценарий от регистрации до получения прокси

### Фаза 7: Mini App
- [ ] 7.1 Адаптация фронтенда для Mini App (Telegram WebApp SDK)
- [ ] 7.2 Настройка BotFather — WebApp кнопка
- [ ] 7.3 Авторизация через initData (переиспользует `/auth/telegram/miniapp`)
- [ ] **Проверка:** Mini App открывается в Telegram, авторизует пользователя автоматически

---

## Проектирование: Фаза 1

### Изменения модели `User`

**Текущее состояние:**
```python
telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)  # NOT NULL
first_name: Mapped[str] = mapped_column(String(128))  # NOT NULL
```

**Проблема:** `telegram_id` обязателен — невозможно создать пользователя без Telegram.

**Новое состояние:**
```python
# Telegram-поля — все nullable
telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
username: Mapped[str | None] = mapped_column(String(64), nullable=True)
language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

# Email-поля — новые
email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
```

**Инвариант:** у пользователя должен быть хотя бы один из: `telegram_id` или `email`.
Это проверяется на уровне приложения, не БД (SQLAlchemy check constraint опционально).

---

### Новая модель `EmailVerification`

Хранит OTP-коды и токены для подтверждения email.

```python
class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)

    # Два варианта подтверждения: цифровой код ИЛИ ссылка с токеном
    code: Mapped[str] = mapped_column(String(8))   # 6-значный цифровой код
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # UUID для ссылки

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Если NULL — это новый пользователь, если заполнен — добавление email к существующему
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
```

---

### Новая модель `AccountLinkToken`

Одноразовый токен для привязки web-аккаунта к Telegram-боту.

```python
class AccountLinkToken(Base):
    __tablename__ = "account_link_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # короткий код для бота

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

### Стратегия merge аккаунтов

**Приоритет: более старый аккаунт остаётся основным.**
Типичный путь пользователя: бот → сайт (Telegram был доступен изначально).

| Сценарий | Действие |
|----------|----------|
| **Бот → сайт** (типичный): есть telegram_id, нет email | Добавить `email` к существующему Telegram-аккаунту. Никакого merge — один аккаунт |
| **Сайт → бот** (Telegram был заблокирован): есть email, нет telegram_id | Добавить `telegram_id` к существующему web-аккаунту |
| **Два отдельных аккаунта с прокси** (редкий случай) | Основной — более старый (`created_at`). Перенести прокси и рефералов с нового на старый, удалить новый |

---

### Изменения в `UserDAO`

Добавить методы:
- `get_by_email(email)` → `User | None`
- `get_by_id(user_id)` → уже есть ✓
- `create_email_user(email, display_name)` → `User`
- `link_telegram(user, tg_user)` → `User` (устанавливает telegram_id и Telegram-поля)
- `merge_into(source: User, target: User)` → `User` (перенос прокси и рефералов)

---

## Схема авторизации

```
Email-регистрация:
POST /auth/email/register {email}
  → создать EmailVerification (code + token)
  → отправить письмо: "Ваш код: 123456" + ссылка /verify?token=uuid
POST /auth/email/verify {email, code} ИЛИ GET /verify?token=uuid
  → проверить code/token, TTL
  → создать User (если нет) или пометить email_verified=True
  → вернуть JWT

Telegram Widget:
POST /auth/telegram/widget {id, first_name, username, hash, ...}
  → проверить HMAC-SHA256(data, bot_token)
  → get_or_create пользователя по telegram_id
  → вернуть JWT

Mini App:
POST /auth/telegram/miniapp {initData}
  → проверить HMAC-SHA256(initData, bot_token)
  → get_or_create пользователя по telegram_id
  → вернуть JWT
```

---

## Окружение и конфигурация

Новые переменные в `.env`:

```env
# Web API
API_SECRET_KEY=          # для JWT подписи
JWT_EXPIRE_HOURS=720     # 30 дней

# Email (Resend)
RESEND_API_KEY=          # получить на resend.com
EMAIL_FROM=noreply@yourdomain.com

# Site
SITE_URL=https://yourdomain.com
```

---

## Docker Compose — новые сервисы

```yaml
api:
  build: .
  command: uvicorn api.main:app --host 0.0.0.0 --port 8000
  env_file: .env
  depends_on: [db, redis]
  volumes:
    - .:/app

web:
  image: nginx:alpine
  volumes:
    - ./web/dist:/usr/share/nginx/html
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
  ports:
    - "80:80"
    - "443:443"
  depends_on: [api]
```
