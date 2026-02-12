"""Setup menu button for bot with dynamic chat_id parameter."""

import logging
import os
from telegram import Bot, MenuButtonWebApp, WebAppInfo

logger = logging.getLogger(__name__)

MINIAPP_URL = os.getenv("MINIAPP_URL", "https://design-community-miniapp-af674cc00f0f.herokuapp.com")


async def setup_menu_button_for_chat(bot: Bot, chat_id: int):
    """
    Set up menu button for a specific chat with chat_id parameter.

    This creates a menu button (next to the message input field) that opens
    the mini app with the correct chat_id encoded in the URL.

    Note: This needs to be called for each chat separately, as each chat
    gets a different URL with its own chat_id.
    """
    try:
        start_param = f"chat_{chat_id}"
        webapp_url = f"{MINIAPP_URL}?startapp={start_param}"

        menu_button = MenuButtonWebApp(
            text="Mini App",
            web_app=WebAppInfo(url=webapp_url)
        )

        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=menu_button
        )

        logger.info(f"Set menu button for chat {chat_id} with URL: {webapp_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to set menu button for chat {chat_id}: {e}")
        return False
