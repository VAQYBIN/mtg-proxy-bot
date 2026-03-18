from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    panel_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    host: Mapped[str] = mapped_column(String(256))
    flag: Mapped[str | None] = mapped_column(String(8), nullable=True)
    agent_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    proxies: Mapped[list["Proxy"]] = relationship(back_populates="node")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Node id={self.id} panel_id={self.panel_id} name={self.name}>"
