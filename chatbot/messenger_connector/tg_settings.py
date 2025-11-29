from event_handlers.message_handler import handle_message
from telegram.ext import MessageHandler, filters
from telegram import BotCommand
from functools import partial


TELEGRAM_COMMANDS = [
    BotCommand("show_thinking", "Show last message thinking"),
    BotCommand("clear_context", "Clear overall context"),
    BotCommand("show_context", "Show overall context")

]


TELEGRAM_HANDLERS = [
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   partial(handle_message, content_type="text")),
    MessageHandler(filters.COMMAND,
                   partial(handle_message, content_type="command"))
]
