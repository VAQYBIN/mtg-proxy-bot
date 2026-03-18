from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class Proxy(Base):
    __tablename__ = "proxies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), index=True
    )

    mtg_username: Mapped[str] = mapped_column(String(128), index=True)
    link: Mapped[str] = mapped_column(String(512))
    port: Mapped[int] = mapped_column(Integer)
    secret: Mapped[str] = mapped_column(String(256))

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    traffic_limit_gb: Mapped[float | None] = mapped_column(Double, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="proxies")  # noqa: F821
    node: Mapped["Node"] = relationship(back_populates="proxies")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Proxy id={self.id} user_id={self.user_id}"
            f" node={self.node_id} port={self.port}>"
        )
