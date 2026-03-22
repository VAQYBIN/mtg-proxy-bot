from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SiteSetting key={self.key!r} value={self.value!r}>"
