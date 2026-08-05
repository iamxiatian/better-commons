"""
====================================================
 日志配置 — structlog 管线与输出路由
====================================================

基于 structlog + Python logging 的日志配置模块，提供统一的日志格式化、
输出路由（控制台 / 文件轮转）以及异常信息自动捕获能力。

核心组件
--------

- ``ExactFormatterProcessor`` — 自定义格式化处理器，按固定模板拼装日志行，
  支持终端彩色输出和纯文本文件输出两种模式。
- ``add_default_trace_id`` — 处理器函数，为每条日志补上 ``trace_id`` 默认值，
  避免因缺少该字段导致格式化报错。
- ``auto_capture_exc_info`` — 处理器函数，在 ``error``/``critical`` 级别自动
  捕获当前异常上下文（通过 ``sys.exc_info()``），注入到事件字典中，
  免除调用处手动写 ``exc_info=True``。
- ``configure_logging`` — 主入口函数，组装完整的 structlog 处理器管线，
  注册控制台和轮转文件两个 Handler。

快速使用
--------

在应用入口处（如 ``main.py``）调用一次初始化：::

    from mofang.util.logging_config import configure_logging
    configure_logging(log_dir="./logs", backup_count=7)

然后在各模块中直接使用：::

    import structlog
    logger = structlog.get_logger(__name__)

    # 普通日志
    logger.info("服务启动成功")

    # 异常日志（自动携带堆栈，无需 exc_info=True）
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("计算异常")

日志格式
--------

每条日志输出格式为：::

    {时间} - {trace_id} - {日志级别} - {文件名}:{行号} - {函数名}() - {消息}

若包含异常信息，则在下一行附加完整堆栈。

修改历史
--------
2026-05-30: 新增 ``auto_capture_exc_info`` 处理器，异常日志自动捕获堆栈。（夏天）
2026-05-30: ``trace_id`` 未传入时，输出结果中不用``None`` 占位。（夏天）
"""

import logging
import logging.handlers
import os
import sys
from collections.abc import Callable
from typing import Any

import structlog

# 引入 structlog 的类型提示
from structlog.types import EventDict, WrappedLogger


# ==========================================
# 1. 自定义 Structlog 处理器 (带有类型提示)
# ==========================================


class ExactFormatterProcessor:
    """
    自定义格式化处理器：严格按照用户要求的格式拼接字符串
    支持终端彩色输出和纯文本文件输出分离
    """

    def __init__(self, use_colors: bool = False) -> None:
        self.use_colors: bool = use_colors
        self.reset: str = "\x1b[0m"
        # ANSI 颜色映射表
        self.colors: dict[str, str] = {
            "debug": "\x1b[36m",  # 青色
            "info": "\x1b[32m",  # 绿色
            "warning": "\x1b[33m",  # 黄色
            "error": "\x1b[31m",  # 红色
            "critical": "\x1b[1;31m",  # 粗体红色
        }

    def __call__(
        self, logger: WrappedLogger, name: str, event_dict: EventDict
    ) -> str:
        # 提取各个字段，进行类型安全的获取
        asctime: str = str(event_dict.get("asctime", ""))
        trace_id: str = str(event_dict.get("trace_id", "None"))
        levelname: str = str(event_dict.get("level", "info")).upper()
        filename: str = str(event_dict.get("filename", "unknown"))
        lineno: int = int(event_dict.get("lineno", 0))
        funcName: str = str(event_dict.get("func_name", "unknown"))
        message: str = str(event_dict.get("event", ""))

        # 严格按照要求拼接格式
        log_str: str = f"{asctime} - {trace_id} - {levelname} - {filename}:{lineno} - {funcName}() - {message}"
        if trace_id is None or trace_id == "None":
            log_str = f"{asctime} - {levelname} - {filename}:{lineno} - {funcName}() - {message}"

        # 挂载异常信息（如果有的话）
        exc_info: str = str(event_dict.get("exception", ""))
        if exc_info and exc_info != "None" and exc_info != "":
            log_str += f"\n{exc_info}"

        # 颜色渲染
        if self.use_colors:
            color: str = self.colors.get(levelname.lower(), self.reset)
            return f"{color}{log_str}{self.reset}"

        return log_str


def add_default_trace_id(
    logger: WrappedLogger, name: str, event_dict: EventDict
) -> EventDict:
    """确保上下文中如果没有传入 trace_id，则默认为 'None'"""
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = "None"
    return event_dict


def auto_capture_exc_info(
    logger: WrappedLogger, name: str, event_dict: EventDict
) -> EventDict:
    """在 error/critical 级别自动捕获当前异常上下文（若有），避免每次手动写 exc_info=True。"""
    level = event_dict.get("level", "")
    if level in ("error", "critical") and "exception" not in event_dict:
        exc_info = sys.exc_info()
        if exc_info and exc_info[0] is not None:
            event_dict["exc_info"] = exc_info
    return event_dict


# ==========================================
# 2. 封装配置方法
# ==========================================


def configure_logging(log_dir: str = "./logs", backup_count: int = 7) -> None:
    """
    配置系统级日志，设置 Structlog 渲染管线及 Python 基础 Logging 路由。

    Args:
        log_dir (str): 日志文件存储的目录路径. Defaults to "./logs".
        backup_count (int): 日志文件保留的天数(个数). Defaults to 7.
    """
    os.makedirs(log_dir, exist_ok=True)

    # 1. 定义 Structlog 处理管线
    structlog_processors: list[Callable[..., Any]] = [
        structlog.contextvars.merge_contextvars,
        add_default_trace_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(
            fmt="%Y-%m-%d %H:%M:%S", key="asctime"
        ),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
        auto_capture_exc_info,
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # 2. 配置 Structlog
    structlog.configure(
        processors=structlog_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 3. 配置 Python 原生 logging (路由与分发)
    # 控制台 Handler (开启颜色)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=ExactFormatterProcessor(use_colors=True)
    )
    console_handler.setFormatter(console_formatter)

    # 文件 Handler (严格纯文本，按要求的轮转策略)
    file_path: str = os.path.join(log_dir, "root.log")
    file_handler = logging.handlers.TimedRotatingFileHandler(
        file_path,
        when="D",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=ExactFormatterProcessor(use_colors=False)
    )
    file_handler.setFormatter(file_formatter)

    # 4. 注册到根 Logger
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清理可能存在的旧 Handlers，防止重复调用此函数时输出重复日志
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


# ==========================================
# 3. 测试与使用示例
# ==========================================
if __name__ == "__main__":
    # 执行配置初始化
    configure_logging(log_dir="./logs", backup_count=7)

    # 获取日志实例
    logger: structlog.stdlib.BoundLogger = structlog.get_logger()

    def test_func() -> None:
        # 测试 1: 走兜底默认值
        logger.info("系统初始化完毕")

        # 测试 2: 局部 kwargs 传递
        logger.debug("这是一个DEBUG信息", trace_id="req-10086")
        logger.warning("发现潜在问题", trace_id="req-10086")

        # 测试 3: 上下文变量绑定
        structlog.contextvars.bind_contextvars(trace_id="ctx-99999")
        logger.info("开始处理用户请求")

        # 测试 4: 异常捕捉输出
        try:
            a = 1 / 0
            print(a)
        except ZeroDivisionError:
            logger.error("计算发生了严重的异常", trace_id=None)

    test_func()
