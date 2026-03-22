from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.dao.account_link_token import AccountLinkTokenDAO
from bot.dao.user import UserDAO

router = Router()


@router.message(Command("link"))
async def handle_link(
    message: Message,
    session: AsyncSession,
    command: CommandObject,
) -> None:
    """Привязать web-аккаунт к Telegram по коду с сайта."""
    if not command.args:
        await message.answer(
            "Использование: /link <КОД>\n"
            "Код можно получить на сайте в разделе привязки аккаунта."
        )
        return

    code = command.args.strip().upper()
    token_dao = AccountLinkTokenDAO(session)
    token = await token_dao.get_active_by_code(code)
    if token is None:
        await message.answer(
            "Код не найден или истёк. Запросите новый код на сайте."
        )
        return

    user_dao = UserDAO(session)
    web_user = await user_dao.get_by_id(token.user_id)
    if web_user is None:
        await message.answer("Аккаунт не найден. Попробуйте снова.")
        return

    if web_user.telegram_id is not None:
        await message.answer("Этот web-аккаунт уже привязан к Telegram.")
        return

    tg_user = message.from_user
    existing_tg = await user_dao.get_by_telegram_id(tg_user.id)

    if existing_tg is not None:
        # У текущего Telegram-пользователя уже есть аккаунт в боте
        # → два отдельных аккаунта, нужен merge
        if existing_tg.created_at <= web_user.created_at:
            # Telegram-аккаунт старше → оставляем его, добавляем email.
            # mark_used ДО merge_into: CASCADE удалит токен вместе с web_user.
            await token_dao.mark_used(token)
            web_email = web_user.email if existing_tg.email is None else None
            web_email_verified = web_user.email_verified
            await user_dao.merge_into(source=web_user, target=existing_tg)
            if web_email:
                existing_tg.email = web_email
                existing_tg.email_verified = web_email_verified
                await session.commit()
            await message.answer(
                "✅ Аккаунты объединены!\n"
                "Ваш Telegram-аккаунт остался основным. "
                "Прокси с сайта перенесены к нему."
            )
        else:
            # Web-аккаунт старше → оставляем его, добавляем telegram_id
            # mark_used и merge_into ДО присвоения telegram_id:
            # existing_tg владеет этим telegram_id — удаляем его первым,
            # чтобы освободить уникальный индекс ix_users_telegram_id.
            await token_dao.mark_used(token)
            await user_dao.merge_into(source=existing_tg, target=web_user)
            web_user.telegram_id = tg_user.id
            web_user.username = tg_user.username
            web_user.first_name = web_user.first_name or tg_user.first_name
            web_user.last_name = web_user.last_name or tg_user.last_name
            web_user.language_code = tg_user.language_code
            await session.commit()
            await message.answer(
                "✅ Аккаунты объединены!\n"
                "Ваш web-аккаунт остался основным. "
                "Прокси из Telegram перенесены к нему."
            )
    else:
        # Простой случай: привязываем telegram_id к web-аккаунту
        web_user.telegram_id = tg_user.id
        web_user.username = tg_user.username
        web_user.first_name = web_user.first_name or tg_user.first_name
        web_user.last_name = web_user.last_name or tg_user.last_name
        web_user.language_code = tg_user.language_code
        await session.commit()
        await token_dao.mark_used(token)

        name = tg_user.first_name or tg_user.username or "пользователь"
        await message.answer(
            f"✅ Аккаунт привязан, {name}!\n"
            "Теперь вы можете управлять прокси и через Telegram, "
            "и через сайт."
        )
