from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)

    # 6-значный цифровой код (для ввода вручную)
    code: Mapped[str] = mapped_column(String(8))
    # UUID-токен (для ссылки в письме)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # NULL — новый пользователь; заполнен — добавление email к существующему аккаунту
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<EmailVerification id={self.id} email={self.email}>"
