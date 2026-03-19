from aiogram.filters.callback_data import CallbackData


# ── Пользовательские ──────────────────────────────────────────

class NodeSelectCallback(CallbackData, prefix="node_select"):
    node_id: int


class ProxyViewCallback(CallbackData, prefix="proxy_view"):
    proxy_id: int


class ProxyDeleteCallback(CallbackData, prefix="proxy_delete"):
    proxy_id: int


class ProxyDeleteConfirmCallback(CallbackData, prefix="proxy_delete_confirm"):
    proxy_id: int


# ── Админ: пользователи ───────────────────────────────────────

class AdminUserListCallback(CallbackData, prefix="adm_users"):
    page: int
    query: str = ""


class AdminUserViewCallback(CallbackData, prefix="adm_user_view"):
    user_id: int


class AdminUserBanCallback(CallbackData, prefix="adm_user_ban"):
    user_id: int


class AdminUserDeleteCallback(CallbackData, prefix="adm_user_del"):
    user_id: int


class AdminUserDeleteConfirmCallback(CallbackData, prefix="adm_user_del_ok"):
    user_id: int


# ── Админ: ноды / дашборд ─────────────────────────────────────

class AdminNodeViewCallback(CallbackData, prefix="adm_node_view"):
    node_id: int


class AdminNodeToggleCallback(CallbackData, prefix="adm_node_toggle"):
    node_id: int


class AdminNodeSyncCallback(CallbackData, prefix="adm_node_sync"):
    pass


# ── Админ: настройки прокси ───────────────────────────────────

class AdminProxySettingsFieldCallback(CallbackData, prefix="admin_ps_field"):
    field: str


# ── Админ: выбор прокси пользователя ─────────────────────────

class AdminProxySelectCallback(CallbackData, prefix="admin_proxy_sel"):
    user_id: int


# ── Админ: редактирование прокси пользователя ─────────────────

class AdminProxyEditCallback(CallbackData, prefix="admin_proxy_edit"):
    proxy_id: int


class AdminProxyEditFieldCallback(CallbackData, prefix="admin_proxy_field"):
    proxy_id: int
    field: str


class AdminProxyResetTrafficCallback(CallbackData, prefix="admin_proxy_reset"):
    proxy_id: int


class AdminProxyResetTrafficConfirmCallback(
    CallbackData, prefix="admin_proxy_reset_ok"
):
    proxy_id: int


# ── Админ: рассылка ───────────────────────────────────────────

class AdminBroadcastConfirmCallback(CallbackData, prefix="adm_bc_ok"):
    pass


class AdminBroadcastCancelCallback(CallbackData, prefix="adm_bc_cancel"):
    pass
