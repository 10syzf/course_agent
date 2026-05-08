"""日志配置：封装 loguru."""

from __future__ import annotations

import sys

from loguru import logger

from course_agent.config import get_config

_configured = False


def setup_logger() -> None:
    """初始化日志输出（只执行一次）."""
    global _configured
    if _configured:
        return

    cfg = get_config()
    logger.remove()
    logger.add(
        sys.stderr,
        level=cfg.logging.level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    _configured = True


def get_logger(name: str | None = None):
    """获取 logger 实例."""
    setup_logger()
    return logger.bind(name=name) if name else logger


__all__ = ["get_logger", "setup_logger"]
