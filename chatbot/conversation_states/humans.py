from typing import Optional, Dict
from pydantic import BaseModel, Field


class Human(BaseModel):
    username: str
    first_name: str
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    information: Dict = Field(default_factory=dict)
    intro_completed: bool = False  # Track if user has written intro
    # When set by an admin (e.g., via admin panel), keep the value stable across merges.
    intro_locked: bool = False
    telegram_id: Optional[int] = None  # Telegram user ID for permissions
    messages_without_intro: int = 0  # Count messages sent without intro
    intro_message: Optional[str] = None  # Link to Telegram intro message (e.g., message_id or t.me link)

    def update_info(self, updates: dict[str, str] | list[dict[str, str]]) -> None:
        if isinstance(updates, dict):
            updates = [updates]

        for pair in updates:
            for key, value in pair.items():
                if value:
                    self.information[key] = value  # Add or update
                elif key in self.information:
                    # Remove existing if value is empty
                    del self.information[key]
                # else: ignore non-existent empty key
