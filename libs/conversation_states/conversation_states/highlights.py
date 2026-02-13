from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field


HighlightCategory = Literal["jobs", "resources", "services"]


class Highlight(BaseModel):
    id: str
    category: HighlightCategory
    tags: list[str] = Field(default_factory=list)
    highlight_link: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("highlight_link", "message_link"),
    )
    highlight_description: str = Field(
        default="",
        validation_alias=AliasChoices("highlight_description", "description"),
    )
    message_text: str
    author_username: str
    author_telegram_id: Optional[int] = None
    published_at: datetime
    expires_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
