"""
=========================================================
轻量代码计时器
=========================================================

提供与 codetiming.Timer 核心用法等价的计时工具，支持显式调用、上下文管理器、
函数装饰器、命名累计和自定义输出。

快速上手
--------
```python
timer = Timer(name="load", text="{:.3f} 秒", logger=rich.print)
timer.start("读取文件")
load_data()
timer.stop()
timer.start("解析内容")
parse_data()
timer.stop()
timings = timer.report()

with Timer("load"):
    load_data()

@Timer(text="处理耗时：{:.3f} 秒")
def process() -> None:
    ...
```

基础概念
--------
计时使用单调高精度时钟 ``perf_counter``。同一实例可以多次计时，并通过
``start("阶段名")`` 分阶段累计；``report()`` 返回各阶段耗时。所有命名计时器
的累计秒数同时保存在 ``Timer.timers``；将 ``logger`` 设为 ``None`` 可以只
记录而不输出。

修改历史
--------
2026-08-04: 新增轻量 Timer 实现
2026-08-04: 支持多阶段计时和汇总报告
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ContextDecorator
from dataclasses import dataclass, field
from time import perf_counter
from typing import ClassVar


class TimerError(RuntimeError):
    """计时器使用状态错误。"""


@dataclass
class Timer(ContextDecorator):
    """测量代码耗时，可作为普通对象、上下文管理器或装饰器使用。"""

    timers: ClassVar[dict[str, float]] = {}

    name: str | None = None
    text: str = "{:.4f} seconds"
    logger: Callable[[str], object] | None = print
    _start_time: float | None = field(default=None, init=False, repr=False)
    _active_name: str | None = field(default=None, init=False, repr=False)
    _elapsed_by_name: dict[str, float] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """初始化命名计时器的累计值。"""
        if self.name:
            self.timers.setdefault(self.name, 0.0)

    @property
    def running(self) -> bool:
        """返回计时器当前是否正在运行。"""
        return self._start_time is not None

    def start(self, name: str | None = None) -> None:
        """开始一次计时。

        Args:
            name: 本阶段名称；未提供时使用实例的默认名称。

        Raises:
            TimerError: 计时器已经启动。
        """
        if self.running:
            self.stop()

        self._active_name = name.strip() if name and name.strip() else self.name
        if self._active_name:
            self.timers.setdefault(self._active_name, 0.0)
        self._start_time = perf_counter()

    def stop(self, show_time: bool = True) -> float:
        """停止计时、记录结果并返回经过的秒数。

        Returns:
            本次计时经过的秒数。

        Raises:
            TimerError: 计时器尚未启动。
        """
        if self._start_time is None:
            raise TimerError("Timer is not running. Use .start() to start it")

        elapsed = perf_counter() - self._start_time
        active_name = self._active_name
        self._start_time = None
        self._active_name = None
        report_name = active_name or "total"
        self._elapsed_by_name[report_name] = (
            self._elapsed_by_name.get(report_name, 0.0) + elapsed
        )
        if active_name:
            self.timers[active_name] += elapsed
        if show_time and self.logger is not None:
            message = self.text.format(elapsed)
            self.logger(f"{active_name}: {message}" if active_name else message)
        return elapsed

    def report(self) -> dict[str, float]:
        """输出并返回当前实例各阶段的累计耗时。

        Returns:
            阶段名称到累计秒数的副本。未命名计时归入 ``total``。
        """
        if self.running:
            self.stop()
        timings = dict(self._elapsed_by_name)
        if self.logger is not None:
            for name, elapsed in timings.items():
                self.logger(f"{name}: {self.text.format(elapsed)}")
        return timings

    def __enter__(self) -> Timer:
        """进入上下文时开始计时。"""
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """退出上下文时停止计时，不拦截业务异常。"""
        del exc_info
        self.stop()
