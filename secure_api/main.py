"""
Secure API proxy for LangGraph.

Adds authentication and authorization layer on top of LangGraph API:
- Validates Telegram WebApp initData cryptographic signature
- Verifies user has access to the requested chat via Telegram Bot API
- Proxies authorized requests to LangGraph API

This prevents users from accessing threads/chats they don't belong to.
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from telegram import Bot

from telegram_validator import validate_init_data
from access_validator import ThreadAccessValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")

# Initialize Telegram bot
bot = Bot(token=BOT_TOKEN)
access_validator = ThreadAccessValidator(bot)

# Create FastAPI app
app = FastAPI(
    title="Secure LangGraph API",
    description="Authenticated proxy for LangGraph with Telegram WebApp integration",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your mini app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_request(init_data: str, thread_id: str) -> int:
    """
    Verify that the request is authorized.

    Steps:
    1. Validate Telegram initData signature
    2. Extract user_id from initData
    3. Get chat_id from thread metadata
    4. Verify user is a member of that chat

    Args:
        init_data: Telegram WebApp initData (from X-Telegram-Init-Data header)
        thread_id: LangGraph thread ID

    Returns:
        user_id: Verified Telegram user ID

    Raises:
        HTTPException: If validation fails
    """
    # Step 1: Validate initData signature (using Ed25519 or HMAC-SHA256)
    try:
        user_id = validate_init_data(init_data, BOT_TOKEN)
        logger.info(f"Validated user_id={user_id} from initData")
    except ValueError as e:
        logger.warning(f"Invalid initData: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid Telegram authentication: {e}")

    # Step 2: Get thread metadata to find chat_id
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}")
            response.raise_for_status()
            thread = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch thread {thread_id}: {e}")
        raise HTTPException(status_code=404, detail="Thread not found")

    # Step 3: Extract chat_id from metadata
    metadata = thread.get("metadata", {})
    chat_id = metadata.get("chat_id")

    if not chat_id:
        logger.warning(f"Thread {thread_id} missing chat_id in metadata")
        raise HTTPException(
            status_code=403,
            detail="Thread does not have associated chat_id"
        )

    logger.info(f"Thread {thread_id} belongs to chat {chat_id}")

    # Step 4: Verify user has access to chat
    try:
        await access_validator.validate_or_raise(chat_id, user_id)
        logger.info(f"User {user_id} authorized for chat {chat_id}")
    except PermissionError as e:
        logger.warning(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))

    return user_id


@app.get("/threads/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    x_telegram_init_data: str = Header(None)
):
    """
    Get thread state with authentication.

    This endpoint:
    1. Validates Telegram WebApp initData
    2. Verifies user has access to the chat
    3. Returns thread state from LangGraph API

    Headers:
        X-Telegram-Init-Data: Telegram WebApp initData (required)

    Returns:
        Thread state from LangGraph API
    """
    # Verify authentication
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Telegram-Init-Data header"
        )

    # Verify authorization (validates signature + checks chat membership)
    user_id = await verify_request(x_telegram_init_data, thread_id)

    # Fetch thread state from LangGraph
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/state")
            response.raise_for_status()
            state = response.json()

        logger.info(f"Returned thread state for thread {thread_id} to user {user_id}")
        return state

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch thread state: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch thread state from LangGraph")


@app.get("/threads/{thread_id}/history")
async def get_thread_history(
    thread_id: str,
    x_telegram_init_data: str = Header(None)
):
    """
    Get thread history with authentication.

    Headers:
        X-Telegram-Init-Data: Telegram WebApp initData (required)

    Returns:
        Thread history from LangGraph API
    """
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")

    # Verify authorization
    user_id = await verify_request(x_telegram_init_data, thread_id)

    # Fetch history from LangGraph
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{LANGGRAPH_API_URL}/threads/{thread_id}/history")
            response.raise_for_status()
            history = response.json()

        logger.info(f"Returned thread history for thread {thread_id} to user {user_id}")
        return history

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch thread history: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch thread history from LangGraph")


@app.post("/threads/{thread_id}/runs/wait")
async def create_run(
    thread_id: str,
    request: Request,
    x_telegram_init_data: str = Header(None)
):
    """
    Create a run (send message) with authentication.

    Headers:
        X-Telegram-Init-Data: Telegram WebApp initData (required)

    Returns:
        Run result from LangGraph API
    """
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")

    # Verify authorization
    user_id = await verify_request(x_telegram_init_data, thread_id)

    # Get request body
    body = await request.json()

    # Forward to LangGraph
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{LANGGRAPH_API_URL}/threads/{thread_id}/runs/wait",
                json=body
            )
            response.raise_for_status()
            result = response.json()

        logger.info(f"Created run for thread {thread_id} by user {user_id}")
        return result

    except httpx.HTTPError as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=502, detail="Failed to create run in LangGraph")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "langgraph_url": LANGGRAPH_API_URL,
        "bot_configured": bool(BOT_TOKEN)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
