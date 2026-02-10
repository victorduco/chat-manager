from event_handlers.message_handler import handle_message
from telegram.ext import MessageHandler, filters
from telegram import BotCommand
from functools import partial


# Commands are now managed via config and only shown to authorized users
# Commands will not appear in Telegram's command menu to maintain privacy
TELEGRAM_COMMANDS = [
    # Admin commands (not shown in menu, but still work):
    # /show_all_users - Show all users with intro status (admin only)
]


TELEGRAM_HANDLERS = [
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   partial(handle_message, content_type="text")),
    MessageHandler(filters.COMMAND,
                   partial(handle_message, content_type="command"))
]
