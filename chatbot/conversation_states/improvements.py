from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field


ImprovementCategory = Literal["bug", "feature"]
ImprovementStatus = Literal["open", "closed"]


class Improvement(BaseModel):
    id: str
    category: ImprovementCategory
    description: str = Field(
        default="",
        validation_alias=AliasChoices("description", "improvement_description"),
    )
    reporter: Optional[str] = None
    status: ImprovementStatus = "open"
    created_at: datetime
