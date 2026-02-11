import os
from quart import Quart, request, jsonify
from messenger_connector.connectorClasses import MessengerConnector, TelegramConnector
from server.config import DEV_ENV
from cron.daily_runner import run_daily


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

        @self.app.route("/cron/daily", methods=["POST", "GET"])
        async def cron_daily():
            # Protected endpoint for schedulers (Heroku Scheduler, GitHub Actions, etc.).
            # Set CRON_SECRET in prod and pass it as X-Cron-Secret header.
            expected = (os.getenv("CRON_SECRET") or "").strip()
            if expected:
                got = (request.headers.get("X-Cron-Secret") or "").strip()
                if got != expected:
                    return jsonify({"error": "forbidden"}), 403

            if request.method == "POST":
                payload = await request.get_json(silent=True) or {}
                if not isinstance(payload, dict):
                    payload = {}
                args = payload
            else:
                args = request.args

            def _b(v, default=False):
                if v is None:
                    return default
                if isinstance(v, bool):
                    return v
                s = str(v).strip().lower()
                if s in ("1", "true", "yes", "y", "on"):
                    return True
                if s in ("0", "false", "no", "n", "off"):
                    return False
                return default

            def _i(v, default: int):
                try:
                    return int(v)
                except Exception:
                    return default

            # Defaults are production-safe:
            # - only_enabled: run only on explicitly enabled threads
            # - bootstrap_enable_n: disabled
            result = await run_daily(
                only_enabled=_b(args.get("only_enabled"), True),
                limit=_i(args.get("limit"), 200),
                force=_b(args.get("force"), False),
                bootstrap_enable_n=_i(args.get("bootstrap_enable_n"), 0),
            )
            return jsonify(result)

    def run(self):
        port = int(os.environ.get("PORT", self.DEFAULT_PORT))
        self.app.run(host=self.DEFAULT_HOST, port=port)
