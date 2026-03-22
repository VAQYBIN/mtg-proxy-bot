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

### Фаза 5: Привязка аккаунтов ✅
- [x] 5.1 `POST /api/me/link/request` → код привязки (8 символов, TTL 15 мин); уже привязан → 400
- [x] 5.2 Команда `/link <КОД>` в боте → простая привязка или merge двух аккаунтов
- [x] 5.3 `POST /api/me/link/miniapp {init_data}` → HMAC-верификация initData + привязка/merge
- [x] 5.4 Стратегия merge: старший аккаунт остаётся основным; прокси и email/telegram_id переносятся
- [x] `bot/dao/account_link_token.py` — AccountLinkTokenDAO (create, get_active_by_code, mark_used, invalidate_pending)
- [x] **Проверка:** все три сценария привязки работают без потери данных

### Фаза 6: Frontend (сайт) ✅
- [x] 6.1 Настройка проекта: React 19 + Vite + TypeScript + Tailwind v4 + shadcn/ui
- [x] 6.2 LoginPage `/login` — email+OTP (InputOTP 6 цифр) + Telegram Login Widget
- [x] 6.3 ProxiesPage `/` — список прокси с Card/Skeleton/Dialog выбора ноды
- [x] 6.4 ProxyDetailPage `/proxy/:id` — детали, QR-код, статистика, AlertDialog удаления
- [x] 6.5 AccountPage `/account` — инфо, привязка Telegram (код + таймер), logout
- [x] Docker: multi-stage Dockerfile, nginx.conf с proxy на api, сервис в docker-compose (порт 3000)
- [x] **Проверка:** TypeScript билд без ошибок (`npm run build`)

### Фаза 7: Mini App ✅
- [x] 7.1 Адаптация фронтенда для Mini App (Telegram WebApp SDK, `telegram.ts` хелпер, скрытие logout/header в Mini App)
- [x] 7.2 Настройка BotFather — WebApp кнопка (инструкция в README)
- [x] 7.3 Авторизация через initData (переиспользует `/auth/telegram/miniapp`, auto-login в `useAuth`)
- [x] **Проверка:** Mini App открывается в Telegram, авторизует пользователя автоматически

### Фаза 8: Панель администратора

Администратор (тот, чей `telegram_id` есть в `ADMIN_IDS`) входит в `/admin` как обычный пользователь. Флаг `is_admin: bool` возвращается в `/api/me`. Панель позволяет настроить брендинг: название сервиса и логотип.

#### 8.1 Бэкенд — модель и миграция ✅
- [x] 8.1.1 Новая модель `bot/models/site_setting.py` — `SiteSetting(key VARCHAR PK, value TEXT, updated_at)`
- [x] 8.1.2 Добавить `SiteSetting` в `bot/models/__init__.py`
- [x] 8.1.3 Alembic-миграция: создать таблицу `site_settings`
- [x] 8.1.4 `bot/dao/site_setting.py` — `SiteSettingDAO`: методы `get(key)`, `set(key, value)`, `get_many(keys)`

#### 8.2 Бэкенд — загрузка логотипа (volume) ✅
- [x] 8.2.1 Добавить volume `uploads_data:/app/uploads` в `docker-compose.yml` и `docker-compose.prod.yml` (сервис `api`)
- [x] 8.2.2 Монтировать `StaticFiles` в FastAPI: `app.mount("/uploads", StaticFiles(directory="/app/uploads"))`
- [x] 8.2.3 Добавить `/uploads/` в nginx proxy в `web/nginx.conf` (рядом с `/api/` и `/auth/`)

#### 8.3 Бэкенд — API эндпоинты ✅
- [x] 8.3.1 `api/deps.py` — новая dependency `require_admin`: проверяет `user.telegram_id in settings.ADMIN_IDS`, иначе 403
- [x] 8.3.2 `api/routers/admin.py` — новый роутер:
  - `GET /api/admin/settings` (admin) → `{brand_name, brand_logo_url}`
  - `PUT /api/admin/settings` (admin) → обновить `brand_name`; возвращает обновлённые настройки
  - `POST /api/admin/settings/logo` (admin) → `multipart/form-data`, сохранить файл как `/app/uploads/logo.{ext}`, вернуть `{url: "/uploads/logo.{ext}"}`; старый файл удалять перед записью нового
- [x] 8.3.3 `GET /api/settings` (публичный, без auth) → `{brand_name, brand_logo_url}` — для отображения на сайте
- [x] 8.3.4 `api/routers/users.py` — добавить `is_admin: bool` в `UserResponse` (вычисляется через `settings.ADMIN_IDS`)
- [x] 8.3.5 Подключить роутеры в `api/main.py` (admin + settings)
- [x] **Проверка:** `PUT /api/admin/settings` сохраняет, `GET /api/settings` возвращает без токена, загрузка лого сохраняет файл в volume

#### 8.4 Фронтенд — BrandingContext ✅
- [x] 8.4.1 `web/src/api/settings.ts` — функции `getPublicSettings()` и `getAdminSettings()`, `updateAdminSettings()`, `uploadLogo()`
- [x] 8.4.2 `web/src/hooks/useBranding.tsx` — `BrandingProvider`: при старте приложения загружает `GET /api/settings`, хранит `brandName` и `brandLogoUrl` в контексте, экспортирует `useBranding()`
- [x] 8.4.3 Обернуть `App` в `BrandingProvider` (в `App.tsx`)
- [x] 8.4.4 Заменить все хардкоды `"MTG Proxy"` на `useBranding().brandName` (LoginPage, ProxiesPage header, `document.title` через BrandingProvider)
- [x] 8.4.5 Показать логотип в шапке LoginPage и основного layout (если `brandLogoUrl` не пустой — `<img>`, иначе только текст)

#### 8.5 Фронтенд — страницы `/admin` ✅
- [x] 8.5.1 `AdminRoute` — компонент-гард: если `!user?.is_admin` → редирект на `/` (реализован внутри `AdminSettingsPage.tsx` через `useEffect`)
- [x] 8.5.2 Добавить маршрут `/admin` в `App.tsx` (внутри `ProtectedRoute`)
- [x] 8.5.3 `web/src/pages/AdminSettingsPage.tsx`:
  - Поле "Название бренда" (Input, кнопка "Сохранить")
  - Загрузка логотипа (Input type=file, превью текущего логотипа, кнопка "Загрузить")
  - Toast при успехе/ошибке каждого действия
  - После сохранения — обновить `BrandingContext` через `refresh()`
- [x] 8.5.4 Ссылка на `/admin` в навигации (видна только если `user?.is_admin && !isMiniApp()`)
- [x] **Проверка:** TypeScript build ✅, API endpoints ✅ (admin 200, non-admin 403), nginx ✅

### Фаза 9: Рекламный баннер

Администратор может включить рекламный баннер на главной странице клиента. Баннер показывает произвольный текст с кнопкой-ссылкой (например, на VPN-бота в Telegram). Пользователь может скрыть баннер на текущую сессию.

**Ключевые решения:**
- Настройки хранятся в уже существующей таблице `site_settings` (key-value), миграция не нужна
- Баннер виден только если `ad_enabled = true` И `ad_url` не пустой
- Данные баннера входят в публичный `GET /api/settings` — без авторизации, вместе с брендингом
- Управление баннером — в той же странице `/admin`, новая карточка после логотипа
- Shadcn `Switch` для включения/выключения, `Alert` для отображения баннера у клиента
- Dismiss — только на текущую сессию (React state, без localStorage)

**Новые ключи в `site_settings`:**
| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `ad_enabled` | `"true"` / `""` | `""` (выкл) | Включён ли баннер |
| `ad_url` | строка | `""` | Ссылка кнопки (t.me/..., https://...) |
| `ad_text` | строка | `""` | Текст баннера (если пусто — показывается только кнопка) |
| `ad_button_text` | строка | `"Подробнее"` | Текст кнопки |

#### 9.1 Бэкенд — константы и DAO ✅
- [x] 9.1.1 Добавить константы `AD_ENABLED`, `AD_URL`, `AD_TEXT`, `AD_BUTTON_TEXT` в `bot/dao/site_setting.py`
- [x] 9.1.2 Добавить дефолты: `ad_enabled=""`, `ad_url=""`, `ad_text=""`, `ad_button_text="Подробнее"`

#### 9.2 Бэкенд — расширение API ✅
- [x] 9.2.1 `api/routers/admin.py` — расширить `AdminSettingsResponse` полями `ad_enabled: bool`, `ad_url: str`, `ad_text: str`, `ad_button_text: str`
- [x] 9.2.2 `api/routers/admin.py` — расширить `AdminSettingsUpdate` теми же полями (все опциональные)
- [x] 9.2.3 `api/routers/admin.py` — в `PUT /api/admin/settings` сохранять ad-поля: `ad_enabled` → `"true"`/`""`, остальные trimmed или None
- [x] 9.2.4 `api/routers/pub_settings.py` — расширить `PublicSettingsResponse` полями `ad_enabled: bool`, `ad_url: str`, `ad_text: str`, `ad_button_text: str`; читать через `dao.get_many([..., AD_ENABLED, AD_URL, AD_TEXT, AD_BUTTON_TEXT])`
- [x] **Проверка:** `GET /api/settings` возвращает ad-поля без токена; `PUT /api/admin/settings` с невалидным токеном → 401 (схема парсится корректно)

#### 9.3 Фронтенд — типы и API-клиент ✅
- [x] 9.3.1 `web/src/api/types.ts` — добавить `ad_enabled`, `ad_url`, `ad_text`, `ad_button_text` в `PublicSettings` и `AdminSettings`; новый тип `AdminSettingsUpdate`
- [x] 9.3.2 `web/src/api/settings.ts` — переименовать `updateBrandName` → `updateAdminSettings(data: AdminSettingsUpdate)`, принимает объект с любыми полями, отправляет `PUT /api/admin/settings`
- [x] 9.3.3 Обновить вызов в `AdminSettingsPage.tsx` на `updateAdminSettings({ brand_name })`

#### 9.4 Фронтенд — BrandingContext расширение ✅
- [x] 9.4.1 `web/src/hooks/useBranding.tsx` — добавить в контекст: `adEnabled: boolean`, `adUrl: string`, `adText: string`, `adButtonText: string`; парсить из ответа `GET /api/settings`

#### 9.5 Фронтенд — компонент AdBanner ✅
- [x] 9.5.1 `web/src/components/AdBanner.tsx` — компонент-баннер:
  - Принимает `{ url, text, buttonText }` через props
  - Рендерит shadcn `Alert` со слотом `AlertAction` (кнопка ✕ для dismiss)
  - Иконка `Megaphone` из `lucide-react`
  - `AlertTitle` — `text` (если не пустой); `<a>` со стилями вместо `asChild` (Button использует `@base-ui/react`)
  - Dismiss через `useState(false)` — при нажатии ✕ скрывает компонент на сессию

#### 9.6 Фронтенд — интеграция в ProxiesPage ✅
- [x] 9.6.1 `web/src/pages/ProxiesPage.tsx` — рендерить `<AdBanner />` между `<Separator />` и списком прокси, только если `adEnabled && adUrl`

#### 9.7 Фронтенд — AdminSettingsPage расширение ✅
- [x] 9.7.1 Добавить `Switch` из shadcn: `npx shadcn@latest add switch`
- [x] 9.7.2 `web/src/pages/AdminSettingsPage.tsx` — новая карточка "Рекламный баннер" после карточки логотипа:
  - `Switch` + Label "Показывать баннер на главной странице"
  - `Input` для URL, текста баннера, текста кнопки (disabled если `!adEnabled`)
  - Кнопка "Сохранить" — disabled если включён, но URL пустой
  - Toast при успехе/ошибке; после сохранения — `refresh()` обновляет `BrandingContext`
- [x] **Проверка:** TypeScript build ✅, vite build ✅, `GET /api/settings` через nginx → ad-поля присутствуют

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
