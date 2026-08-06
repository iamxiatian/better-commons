from collections.abc import Sequence
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
    @property
    def label(self) -> str: ...

    @property
    def points(self) -> Sequence[Point]: ...


@dataclass(frozen=True, slots=True)
class SimpleRegion:
    label: str
    points: Sequence[Point]
