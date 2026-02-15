from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field


ImprovementCategory = Literal["bug", "feature"]
ImprovementStatus = Literal["open", "closed", "wont_do"]


class Improvement(BaseModel):
    id: str
    task_number: Optional[str] = None
    category: ImprovementCategory
    description: str = Field(
        default="",
        validation_alias=AliasChoices("description", "improvement_description"),
    )
    reporter: Optional[str] = None
    status: ImprovementStatus = "open"
    resolution: Optional[str] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
