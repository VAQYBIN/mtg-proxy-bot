from sqlalchemy import Boolean, Double, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class ProxySettings(Base):
    __tablename__ = "proxy_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_devices: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_limit_gb: Mapped[float | None] = mapped_column(Double, nullable=True)
    expires_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_reset_interval: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    faq_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    def __repr__(self) -> str:
        return (
            f"<ProxySettings max_devices={self.max_devices}"
            f" traffic_limit_gb={self.traffic_limit_gb}"
            f" expires_days={self.expires_days}"
            f" traffic_reset_interval={self.traffic_reset_interval}>"
        )
