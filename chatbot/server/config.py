import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='/workspaces/agent-taskmanager/.env')

DEV_ENV = False if os.getenv("HEROKU_APP_NAME") else True

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


if DEV_ENV:
    LANGGRAPH_API_URL = "http://localhost:2024"

else:
    LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL")
    HEROKU_APP_NAME = os.getenv("HEROKU_APP_NAME")
    TELEGRAM_WEBHOOK_URL = f"https://{HEROKU_APP_NAME}.herokuapp.com/{TELEGRAM_TOKEN}"
