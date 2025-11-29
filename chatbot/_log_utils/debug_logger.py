import os
import builtins
from datetime import datetime
import inspect

# Path to log file
LOG_DIR = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "_log_utils/logs")
os.makedirs(LOG_DIR, exist_ok=True)
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "debug.log")


class DebugLogger:
    _counter = 0

    @staticmethod
    def debug_log(msg: str = None):
        DebugLogger._counter += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Get caller location
        frame = inspect.currentframe().f_back
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        function = frame.f_code.co_name
        location = f"{os.path.basename(filename)}:{lineno} in {function}"

        # If no message provided, use default message with counter
        if msg is None:
            msg = f"Debug #{DebugLogger._counter}"

        full_msg = f"[{timestamp}] [DEBUG] [{location}] {msg}"

        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")


# Register globally
if not hasattr(builtins, "debug_log"):
    builtins.debug_log = DebugLogger.debug_log

# Export for direct use
debug_log = DebugLogger.debug_log
