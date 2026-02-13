"""
Thread access validator.

Validates that a user has access to a specific Telegram chat/thread
by checking their membership via Telegram Bot API.
"""

import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class ThreadAccessValidator:
    """Validates user access to Telegram chats."""

    # Chat member statuses that grant read access
    ALLOWED_STATUSES = {
        "creator",      # Chat owner
        "administrator", # Admin
        "member",       # Regular member
        "restricted"    # Restricted but still in chat
    }

    # Statuses that deny access
    DENIED_STATUSES = {
        "left",         # User left the chat
        "kicked"        # User was banned/kicked
    }

    def __init__(self, bot: Bot):
        """
        Initialize validator with Telegram bot instance.

        Args:
            bot: python-telegram-bot Bot instance
        """
        self.bot = bot

    async def validate_access(self, chat_id: str, user_id: int) -> bool:
        """
        Check if user has access to the chat.

        Args:
            chat_id: Telegram chat ID (e.g., "-1002557941720")
            user_id: Telegram user ID (e.g., 118497177)

        Returns:
            True if user has access, False otherwise
        """
        try:
            # Handle private chats (user chatting with bot 1-on-1)
            # In private chats, chat_id equals user_id (without minus sign)
            if str(chat_id) == str(user_id) or str(chat_id) == f"-{user_id}":
                logger.info(f"Private chat detected: chat_id={chat_id}, user_id={user_id}")
                return True

            # Get chat member info from Telegram
            chat_member = await self.bot.get_chat_member(
                chat_id=int(chat_id),
                user_id=user_id
            )

            status = chat_member.status
            logger.info(f"User {user_id} status in chat {chat_id}: {status}")

            # Check status
            if status in self.ALLOWED_STATUSES:
                return True
            elif status in self.DENIED_STATUSES:
                logger.warning(f"User {user_id} denied access to chat {chat_id}: status={status}")
                return False
            else:
                # Unknown status - deny by default for security
                logger.warning(f"Unknown chat member status '{status}' for user {user_id} in chat {chat_id}")
                return False

        except TelegramError as e:
            # Common errors:
            # - Chat not found (bot not in chat)
            # - User not found
            # - Bad Request: chat not found
            logger.error(f"Telegram API error checking access for user {user_id} in chat {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking access: {e}", exc_info=True)
            return False

    async def validate_or_raise(self, chat_id: str, user_id: int):
        """
        Validate access or raise exception.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID

        Raises:
            PermissionError: If user doesn't have access
        """
        has_access = await self.validate_access(chat_id, user_id)
        if not has_access:
            raise PermissionError(
                f"User {user_id} does not have access to chat {chat_id}"
            )


async def validate_thread_access(
    bot: Bot,
    chat_id: str,
    user_id: int
) -> bool:
    """
    Convenience function to validate thread access.

    Args:
        bot: Telegram bot instance
        chat_id: Telegram chat ID
        user_id: Telegram user ID

    Returns:
        True if user has access, False otherwise
    """
    validator = ThreadAccessValidator(bot)
    return await validator.validate_access(chat_id, user_id)
