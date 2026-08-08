# API 参考：日志 Logging

基于 structlog + Python logging 的统一日志管线。从 `commons` 直接导入
`configure_logging`；底层处理器位于 `commons.logging_config`。

## configure_logging

主入口：组装 structlog 管线，注册控制台与轮转文件 Handler。

::: commons.configure_logging

## 底层处理器

按需复用的自定义处理器。

::: commons.logging_config.ExactFormatterProcessor
::: commons.logging_config.add_default_trace_id
::: commons.logging_config.auto_capture_exc_info
