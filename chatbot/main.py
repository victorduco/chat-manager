# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024 Agent Task Manager Contributors

import logging
import _log_utils.debug_logger
from server.route import ServerApp
import asyncio


logging.basicConfig(level=logging.INFO)


server = ServerApp().app

if __name__ == "__main__":
    server.run()
