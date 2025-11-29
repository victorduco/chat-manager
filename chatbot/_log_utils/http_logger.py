import httpx
import logging
import sys
import os
import uuid
import threading

# === Log file setup ===
LOG_DIR = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "_log_utils/logs")
os.makedirs(LOG_DIR, exist_ok=True)
HTTP_LOG_FILE = os.path.join(LOG_DIR, "http.log")

# === Color formatter for console ===


class ColorFormatter(logging.Formatter):
    BASE_COLORS = [
        "\033[91m",  # Red
        "\033[92m",  # Green
        "\033[93m",  # Yellow
        "\033[94m",  # Blue
        "\033[95m",  # Magenta
        "\033[96m",  # Cyan
    ]
    GRAY = "\033[90m"
    RESET = "\033[0m"

    def color_for_rid(self, msg):
        try:
            blocks = msg.split("] ")
            if len(blocks) >= 2:
                second = blocks[1]  # e.g. '[0f8adb >] Request: ...'
                inner = second.split()[0]  # '[0f8adb'
                rid = inner.strip('[')
                value = int(rid, 16)
                return self.BASE_COLORS[value % len(self.BASE_COLORS)]
        except Exception:
            pass
        return self.GRAY

    def format(self, record):
        msg = record.getMessage()
        if "[HTTP CORE]" in msg:
            color = self.GRAY
        elif msg.startswith("[") and any(key in msg for key in ["Body:", "Headers:", "Request:", "Response:"]):
            color = self.color_for_rid(msg)
        else:
            color = "\033[92m"  # events — green
        return f"{color}{msg}{self.RESET}"

# === Plain formatter for log file ===


class PlainFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()

# === Filter to suppress base httpx messages ===


class SuppressHttpxInfoFilter(logging.Filter):
    def filter(self, record):
        return not (record.name == "httpx" and record.getMessage().startswith("HTTP Request:"))


# === Filtering configuration ===
DISABLE_LABELS = set()
SHOW_CORE = True
SHOW_CONTENT = True

_request_ids = {}
_request_id_map = {}  # maps request id to label + short id
_thread_label_map = {}  # maps thread id to label


def _label_for(url: str) -> str:
    if "api.telegram.org" in url:
        return "HTTP TG"
    elif "langgraph" in url or "langchain" in url:
        return "HTTP LGAPI"
    return "HTTP OTHER"


def _short_id(uid: str) -> str:
    return uid[-6:]

# === Main logger setup ===


def _setup_httpx_loggers():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    console_handler.addFilter(SuppressHttpxInfoFilter())

    file_handler = logging.FileHandler(HTTP_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(PlainFormatter())
    file_handler.addFilter(SuppressHttpxInfoFilter())

    for name in ["httpx"]:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    core_logger = logging.getLogger("httpcore")
    core_logger.handlers.clear()
    core_logger.addHandler(console_handler)
    core_logger.addHandler(file_handler)
    core_logger.setLevel(logging.DEBUG if SHOW_CORE else logging.CRITICAL + 1)
    core_logger.propagate = False

    logging.setLogRecordFactory(_record_factory)

# === LogRecord factory for httpcore events ===


def _record_factory(name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None, **kwargs):
    record = logging.LogRecord(
        name, level, pathname, lineno, msg, args, exc_info, func, sinfo)
    if name == "httpcore":
        raw_msg = msg if isinstance(msg, str) else str(msg)
        thread_id = str(record.thread)[-4:]

        direction = "<"
        if any(kw in raw_msg for kw in ["send_", "start_tls", "connect"]):
            direction = ">"

        label = _thread_label_map.get(record.thread, "HTTP CORE")
        record.msg = f"[{label}] [t{thread_id} {direction}] {raw_msg}"
    return record


# === Monkey-patch AsyncClient ===
_original_init = httpx.AsyncClient.__init__


def _patched_init(self, *args, **kwargs):
    if SHOW_CONTENT:
        old_hooks = kwargs.get("event_hooks", {})
        new_hooks = {
            "request": old_hooks.get("request", []) + [_log_request],
            "response": old_hooks.get("response", []) + [_log_response],
        }
        kwargs["event_hooks"] = new_hooks
    _original_init(self, *args, **kwargs)


async def _log_request(request: httpx.Request):
    label = _label_for(str(request.url))
    rid = str(uuid.uuid4())[:8]
    _request_ids[request] = rid
    _request_id_map[rid] = label
    _thread_label_map[request.extensions.get(
        "thread", threading.get_ident())] = label

    if label in DISABLE_LABELS or not SHOW_CONTENT:
        return

    log = logging.getLogger("httpx")
    short = _short_id(rid)
    prefix = f"[{label}] [{short} >]"
    log.debug(f"{prefix} Request: {request.method} {request.url}")
    log.debug(f"{prefix} Headers: {dict(request.headers)}")
    if request.content:
        try:
            body = request.content.decode() if isinstance(
                request.content, bytes) else str(request.content)
            log.debug(f"{prefix} Body: {body}")
        except Exception:
            log.debug(f"{prefix} Body: <binary>")


async def _log_response(response: httpx.Response):
    request = response.request
    rid = _request_ids.pop(request, "????")
    label = _request_id_map.get(rid, "HTTP OTHER")
    if label in DISABLE_LABELS or not SHOW_CONTENT:
        return
    log = logging.getLogger("httpx")
    short = _short_id(rid)
    prefix = f"[{label}] [{short} <]"
    log.debug(f"{prefix} Response: {response.status_code} {response.url}")
    log.debug(f"{prefix} Headers: {dict(response.headers)}")
    try:
        body = await response.aread()
        decoded = body.decode() if isinstance(body, bytes) else str(body)
        log.debug(f"{prefix} Body: {decoded}")
    except Exception:
        log.debug(f"{prefix} Body: <stream or binary>")

# === Main enable function ===


def enable_http_logging(disable_labels=None, show_core=True, show_content=True):
    global DISABLE_LABELS, SHOW_CORE, SHOW_CONTENT
    DISABLE_LABELS = set(disable_labels or [])
    SHOW_CORE = show_core
    SHOW_CONTENT = show_content
    _setup_httpx_loggers()
    httpx.AsyncClient.__init__ = _patched_init
