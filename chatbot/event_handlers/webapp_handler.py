"""Handler for /webapp command - opens mini app with correct chat_id parameter."""

from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import logging
import os

logger = logging.getLogger(__name__)

# Get mini app URL from environment
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://your-miniapp-domain.com")


async def handle_webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send a button that opens the mini app with chat_id encoded in start_param.

    Usage: /webapp

    Security flow:
    1. Gets the current chat ID from Telegram
    2. Encodes it in the WebApp URL as start_param (e.g., "chat_-1002557941720")
    3. Mini app receives this in initDataUnsafe.start_param
    4. Mini app sends request with X-Telegram-Init-Data header
    5. Secure API validates the signature and checks user membership
    6. Only authorized users can access the thread

    This prevents users from manually changing the chat_id to access other chats.
    """
    message = update.message or update.edited_message
    if not message:
        logger.warning("No message found in update")
        return

    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = getattr(message.chat, "title", None) or getattr(
        message.chat, "username", None
    ) or "этот чат"

    logger.info(f"Opening webapp for chat_id={chat_id}, chat_type={chat_type}")

    # Encode chat_id in start_param so mini app can retrieve it
    # Format: chat_-1002557941720 (matches the pattern in miniapp/src/services/telegram.js)
    start_param = f"chat_{chat_id}"

    # Build WebApp URL with start parameter
    webapp_url = f"{MINIAPP_URL}?startapp={start_param}"

    # Create reply keyboard with WebApp button
    # Note: WebApp buttons work in ReplyKeyboard but not InlineKeyboard in groups
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton(
            text="🚀 Открыть Mini App",
            web_app=WebAppInfo(url=webapp_url)
        )]
    ], resize_keyboard=True, one_time_keyboard=True)

    # Send message with button
    if chat_type == "private":
        response_text = (
            "🎯 Открыть Mini App\n\n"
            "Нажмите кнопку ниже 👇"
        )
    else:
        response_text = (
            f"🎯 Mini App для чата: {chat_title}\n\n"
            f"Chat ID: {chat_id}\n"
            f"Тип: {chat_type}\n\n"
            "Нажмите кнопку ниже 👇"
        )

    await message.reply_text(
        response_text,
        reply_markup=keyboard
    )

    logger.info(f"Sent webapp button with start_param={start_param}")
