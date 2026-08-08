# 操作指南：日志与追踪

`configure_logging` 基于 structlog + Python logging 搭建统一的日志管线，
做到：控制台彩色输出、按天轮转的文件日志、异常自动捕获堆栈、自动补 `trace_id`。

## 在应用入口初始化

```python
from commons import configure_logging

configure_logging(log_dir="./logs", backup_count=7)
```

参数说明：

- `log_dir`：日志目录，默认 `./logs`；
- `backup_count`：文件日志保留天数（按天轮转），默认 `7`。

## 在模块中使用

初始化后，各模块直接用 structlog 取 logger：

```python
import structlog

logger = structlog.get_logger(__name__)

def handler() -> None:
    logger.info("收到请求", method="GET", path="/api/user")
    logger.warning("响应偏慢", elapsed_ms=1200, trace_id="req-10086")
```

### 自动捕获异常堆栈

在 `error` / `critical` 级别，如果正处于异常上下文中，无需手写 `exc_info=True`：

```python
try:
    1 / 0
except ZeroDivisionError:
    logger.error("计算异常")   # 自动附带完整堆栈
```

### 上下文变量绑定 trace_id

一条请求贯穿多个函数时，可以用 `contextvars` 绑定，整条调用链共享：

```python
import structlog

structlog.contextvars.bind_contextvars(trace_id="ctx-99999")
logger.info("开始处理用户请求")

# 请求结束清理
structlog.contextvars.unbind_contextvars("trace_id")
```

## 日志格式

控制台与文件统一输出格式：

```text
{时间} - {trace_id} - {级别} - {文件名}:{行号} - {函数名}() - {消息}
{若含异常，下一行附加完整堆栈}
```

示例：

```text
2026-08-06 10:00:00 - INFO - main.py:17 - <module>() - 服务启动成功
2026-08-06 10:00:00 - ctx-99999 - WARNING - app.py:42 - handler() - 响应偏慢
```

## 重复调用不会重复刷日志

`configure_logging` 会清空根 logger 已有的 handlers，多次调用是幂等的，
放心在测试中反复初始化。

## 进阶：自定义格式处理器

better-commons 也导出了底层处理器，可按需组合：

- `ExactFormatterProcessor(use_colors)` —— 按固定模板拼装日志行；
- `add_default_trace_id` —— 补 `trace_id` 默认值；
- `auto_capture_exc_info` —— error/critical 自动捕获异常上下文。

完整签名见 [API 参考 · 日志](../reference/logging.md)。
