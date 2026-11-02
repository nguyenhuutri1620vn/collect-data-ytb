from datetime import datetime

from sqlalchemy import DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def in_check(column: str, values: tuple[str, ...]) -> str:
    """SQL for a CHECK constraint limiting a text column to fixed values (NULL allowed)."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def text_array(**kwargs: object) -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), server_default=text("'{}'"), nullable=False, **kwargs)


def jsonb_list() -> Mapped[list]:
    return mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)


def jsonb_object() -> Mapped[dict]:
    return mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


CATEGORIES = ("an", "uong", "tham_quan", "vui_choi", "khac")
SETTINGS = ("indoor", "outdoor", "mixed")
PRICE_UNITS = ("per_item", "per_person", "ticket")
