"""
=========================================================
版面标注用的坐标点与区域
=========================================================

定义坐标点、只读区域协议，以及可直接使用的简单区域。
矩形框由 x1、y1、x2、y2 表示，多边形顶点放在 polygon_points 中。

修改历史
--------
2026-11-06: score 与 cls_id 允许为空，与 SimpleRegion 对齐
2026-11-06: 为区域字段补充说明
2026-11-07: label 在左侧，order 在右侧，score 不参与绘制
2026-11-07: 有 order 时写成「1: 标题」，score 用较小字号紧跟标签
"""

from dataclasses import dataclass
from typing import Protocol

from typing_extensions import runtime_checkable


class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)


@runtime_checkable
class RegionLike(Protocol):
    """可视化区域"""

    # 声明为只读（@property）：让 frozen dataclass 等只读实现也能满足该协议

    # 矩形框一个角点的横坐标，与 x2 共同决定水平范围
    @property
    def x1(self) -> float: ...

    # 矩形框一个角点的纵坐标，与 y2 共同决定垂直范围
    @property
    def y1(self) -> float: ...

    # 矩形框对角点的横坐标
    @property
    def x2(self) -> float: ...

    # 矩形框对角点的纵坐标
    @property
    def y2(self) -> float: ...

    # 类别编号。为空时绘制使用默认颜色
    @property
    def cls_id(self) -> int | None: ...

    # 类别名称。有 order 时与序号组成「1: 标题」，绘制在矩形框左上角
    @property
    def label(self) -> str: ...

    # 多边形顶点。为空，或正好是矩形四角时，只画矩形框
    @property
    def polygon_points(self) -> tuple[Point, ...]: ...

    # 置信度。不为空时用主文字 2/3 的字号，紧跟在标签后面
    @property
    def score(self) -> float | None: ...

    # 阅读或排序序号。不为空时写在类别名称前，格式为「1: 标题」
    @property
    def order(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class SimpleRegion:
    """可直接用于标注的区域。"""

    # 矩形框一个角点的横坐标，与 x2 共同决定水平范围
    x1: float
    # 矩形框一个角点的纵坐标，与 y2 共同决定垂直范围
    y1: float
    # 矩形框对角点的横坐标
    x2: float
    # 矩形框对角点的纵坐标
    y2: float
    # 类别编号，对应 cls_color_map 的键
    cls_id: int
    # 类别名称。有 order 时与序号组成「1: 标题」，绘制在矩形框左上角
    label: str
    # 多边形顶点。为空，或正好是矩形四角时，只画矩形框
    polygon_points: tuple[Point, ...] = ()
    # 置信度。不为空时用主文字 2/3 的字号，紧跟在标签后面
    score: float | None = None
    # 阅读或排序序号。不为空时写在类别名称前，格式为「1: 标题」
    order: int | None = None
