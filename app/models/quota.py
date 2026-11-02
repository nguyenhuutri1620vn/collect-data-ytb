import datetime as dt

from sqlalchemy import BigInteger, Date, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QuotaUsage(Base):
    """Daily usage per service and metric; `date` is in QUOTA_TIMEZONE (FR-7.2)."""

    __tablename__ = "quota_usage"

    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    service: Mapped[str] = mapped_column(Text, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
