"""
Structured JSON logging for production.

用法：
    ENV=production 时自动启用 JSON 格式输出（供 ELK/Datadog 等 log aggregator 消费）。
    开发环境保持原有文本格式。
"""

import json
import logging
import sys
from typing import Any

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """将日志记录格式化为 JSON 行。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 包含异常追溯（如有）
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 包含 extra 字段
        for key, value in record.__dict__.items():
            if key not in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            ):
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """配置日志系统。生产环境输出 JSON，开发环境输出文本。"""
    is_production = settings.ENVIRONMENT == "production"

    handler = logging.StreamHandler(sys.stdout)

    if is_production:
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    # 重置根日志器
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)

    # 抑制 noisy 三方库
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
