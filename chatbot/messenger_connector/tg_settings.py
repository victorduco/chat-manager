from event_handlers.message_handler import handle_message
from event_handlers.webapp_handler import handle_webapp_command
from telegram.ext import MessageHandler, CommandHandler, filters
from telegram import BotCommand
from functools import partial


# Commands shown in Telegram's command menu
TELEGRAM_COMMANDS = [
    BotCommand("webapp", "Открыть Mini App"),
    # Admin commands (not shown in menu, but still work):
    # /show_all_users - Show all users with intro status (admin only)
]


TELEGRAM_HANDLERS = [
    # WebApp command - opens mini app with secure chat_id parameter
    CommandHandler("webapp", handle_webapp_command),

    # Regular message handlers
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   partial(handle_message, content_type="text")),
    MessageHandler(filters.COMMAND,
                   partial(handle_message, content_type="command"))
]
