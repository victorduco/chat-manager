from typing import Dict, Any
import logging
from abc import ABC, abstractmethod
from telegram import Update, BotCommandScopeDefault
from telegram.ext import ApplicationBuilder, Application
import asyncio
import server.config as CONFIG
from .tg_settings import TELEGRAM_COMMANDS, TELEGRAM_HANDLERS


class MessengerConnector(ABC):
    """Base class for messenger platform connectors."""

    @abstractmethod
    async def process_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook update."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Start messenger connection."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Stop messenger connection."""
        pass

    @abstractmethod
    def get_webhook_path(self) -> str:
        """Return webhook path for routing."""
        pass


class TelegramConnector(MessengerConnector):
    app: Application

    def __init__(self):
        self.app = ApplicationBuilder().token(CONFIG.TELEGRAM_TOKEN).build()

    async def process_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            update = Update.de_json(data, self.app.bot)
            asyncio.create_task(self.app.process_update(update))
            return {"status": "ok"}
        except Exception as e:
            error_msg = f"Error processing Telegram update: {e}"
            logging.error(error_msg)
            return {"error": str(e)}

    async def initialize(self) -> None:
        await self.app.initialize()
        await self.app.start()
        if getattr(CONFIG, "TELEGRAM_WEBHOOK_URL", None):
            await self.app.start()
            await self.app.bot.set_webhook(url=CONFIG.TELEGRAM_WEBHOOK_URL)
        else:
            self.app.run_polling()
            await self.app.bot.set_my_commands(TELEGRAM_COMMANDS, BotCommandScopeDefault())
        for handler in TELEGRAM_HANDLERS:
            self.app.add_handler(handler)

    async def shutdown(self) -> None:
        await self.app.stop()

    def get_webhook_path(self) -> str:
        return f"/{self.app.bot.token}"
