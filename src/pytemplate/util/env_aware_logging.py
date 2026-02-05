import logging
from logging.handlers import TimedRotatingFileHandler

import structlog


def setup_env_aware_logging(app_name: str, mode: str = "dev"):
    """
    环境感知的日志配置函数

    功能:
        根据不同的运行模式, 配置日志输出方式和级别。
        开发环境: 详细日志输出到控制台
        测试环境: 信息级别日志输出到控制台和文件
    Args:
        app_name (str): 应用名称
        mode (str): 运行模式, 可选值为 'dev', 'test', 'production'
    """

    # 核心配置：禁用asyncio的DEBUG日志
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # 根据环境设置不同的日志级别
    if mode == "dev":
        log_level = logging.DEBUG  # 开发环境: 详细日志
        console_output = True  # 输出到控制台
        file_output = False  # 不输出到文件
    elif mode == "test":
        log_level = logging.INFO  # 测试环境：信息级别
        console_output = True
        file_output = True
    else:  # production环境
        log_level = logging.WARNING  # 生产环境: 仅警告及以上
        console_output = False  # 不输出到控制台
        file_output = True  # 输出到文件

    # 配置标准logging
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台处理器（开发环境）
    if console_output:
        console_handler = logging.StreamHandler()
        # 单独设置控制台的输出格式, 控制台处理器使用彩色渲染器
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            ],
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    # 文件处理器(测试和生产环境)
    if file_output:
        file_handler = TimedRotatingFileHandler(
            filename=(
                f"{app_name}_{mode}.log"
                if mode != "production"
                else f"{app_name}.log"
            ),
            when="midnight",  # 每天午夜轮转
            interval=1,  # 间隔1天
            backupCount=7,  # 保留7个备份文件
            encoding="utf-8",
        )
        # 单独设置文件的输出格式, 文件处理器使用JSON渲染器
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            ],
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # 配置structlog处理器管道
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # 应用structlog配置
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
