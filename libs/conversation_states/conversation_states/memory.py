from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemoryFrom(BaseModel):
    """Stable snapshot of who created the memory record."""

    username: Optional[str] = None
    telegram_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None


class MemoryRecord(BaseModel):
    id: str
    created_at: datetime
    category: str
    text: str
    from_user: MemoryFrom = Field(default_factory=MemoryFrom)

