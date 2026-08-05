"""
包装器工具集合
================

提供各种包装器（wrapper）函数和装饰器，用于适配不同框架或接口之间的调用约定。

目前已包含的包装器：

- ``async_command`` — 将 async def 函数包装为同步函数，
  用于在 Typer/Click 等同步 CLI 框架中调用异步函数。
  内部通过 ``asyncio.run()`` 驱动事件循环。

使用方式
--------

::

    @app.command()
    @async_command
    async def my_command(text: str):
        await some_async_func(text)
"""

import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any


def async_command(
    func: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., None]:
    """装饰器：将 async def 命令包装为同步函数，供 Typer（底层 Click）调用。"""

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> None:
        asyncio.run(func(*args, **kwargs))

    return sync_wrapper
