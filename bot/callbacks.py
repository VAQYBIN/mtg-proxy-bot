from aiogram.filters.callback_data import CallbackData


class NodeSelectCallback(CallbackData, prefix="node_select"):
    node_id: int


class ProxyViewCallback(CallbackData, prefix="proxy_view"):
    proxy_id: int


class ProxyDeleteCallback(CallbackData, prefix="proxy_delete"):
    proxy_id: int


class ProxyDeleteConfirmCallback(CallbackData, prefix="proxy_delete_confirm"):
    proxy_id: int
