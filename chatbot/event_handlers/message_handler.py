from _log_utils.meow_httpx import enable_meowx
from _log_utils.faker.tg_message import generate_fake_context, generate_fake_update
from telegram import Update, ReactionTypeEmoji
from telegram.ext import ContextTypes
from event_handlers.utils.stream.stream_producer import StreamProducer
from event_handlers.utils.stream.stream_consumer import StreamConsumer
from event_handlers.utils.stream.context_extractor import ContextExtractor
from event_handlers.utils.stream.stream_queue import StreamQueue

import traceback
from langgraph_sdk import get_client
from server.config import LANGGRAPH_API_URL
from langgraph_sdk.client import LangGraphClient
import asyncio
import httpx


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str):
    queue = StreamQueue()
    ctx = ContextExtractor.from_update(
        update, context, content_type=content_type)
    producer = await StreamProducer.initialize(ctx, queue)
    consumer = await StreamConsumer.initialize(ctx, queue)
    await asyncio.gather(
        producer.run(),
        consumer.run_messages(),
        consumer.run_actions()
    )
