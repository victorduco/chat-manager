import os
from quart import Quart, request, jsonify
from messenger_connector.connectorClasses import MessengerConnector, TelegramConnector
from server.config import DEV_ENV


class ServerApp:
    app: Quart
    messenger_connector: MessengerConnector
    DEFAULT_PORT = 5000
    DEFAULT_HOST = "0.0.0.0"

    def __init__(self):
        self.app = Quart(__name__)
        self.messenger_connector = TelegramConnector()

        self._setup_routes()

    def _setup_routes(self):

        @self.app.route("/")
        async def index():
            if DEV_ENV:
                return f"dev_env"
            else:
                return f"prod_env"

        @self.app.route(self.messenger_connector.get_webhook_path(), methods=["POST"])
        async def telegram_webhook():
            data = await request.get_json()
            result = await self.messenger_connector.process_update(data)

            if "error" in result:
                return jsonify(result), 500
            return jsonify(result)

        @self.app.before_serving
        async def startup():
            await self.messenger_connector.initialize()

        @self.app.after_serving
        async def shutdown():
            await self.messenger_connector.shutdown()

    def run(self):
        port = int(os.environ.get("PORT", self.DEFAULT_PORT))
        self.app.run(host=self.DEFAULT_HOST, port=port)
