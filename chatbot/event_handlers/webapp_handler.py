"""Handler for /webapp command."""

from telegram import Update
from telegram.ext import ContextTypes
import logging
from .setup_menu_button import setup_menu_button_for_chat

logger = logging.getLogger(__name__)


async def handle_webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply with a direct mini app deep link for the current chat."""
    message = update.message or update.edited_message
    if not message:
        logger.warning("No message found in update")
        return

    chat_id = message.chat.id
    logger.info(f"Opening webapp for chat_id={chat_id}")

    # Set up menu button for this chat (so user can easily access mini app later)
    try:
        bot = context.bot if hasattr(context, 'bot') else update.get_bot()
        await setup_menu_button_for_chat(bot, chat_id)
    except Exception as e:
        logger.warning(f"Failed to set menu button: {e}")

    start_param = f"chat_{chat_id}"
    bot = context.bot if hasattr(context, "bot") else update.get_bot()
    username = (getattr(bot, "username", None) or "").strip()
    if not username:
        try:
            me = await bot.get_me()
            username = str(getattr(me, "username", "") or "").strip()
        except Exception:
            username = ""

    if username:
        response_text = f"Ссылка на мини-апп: t.me/{username}/app?startapp={start_param}"
    else:
        response_text = f"Ссылка на мини-апп: t.me/[имя бота]/app?startapp={start_param}"

    await message.reply_text(response_text)
