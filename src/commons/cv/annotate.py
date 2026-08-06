import platform
from collections.abc import Sequence
from pathlib import Path

import structlog

from commons.cv.types import Point


logger = structlog.get_logger(__name__)


def contrast_color(
    rgb: tuple[float, float, float],
) -> tuple[float, float, float]:
    """
    获取跟传入的颜色不一样、能够突出显示的对比颜色。
    考虑多种对比度因素的改进算法, rgb的颜色值是0-1之间的浮点数, 返回值也是0-1之间的浮点数
    """
    # 将0-1范围的rgb转回0-255
    r, g, b = (int(c * 255) for c in rgb)
    # 基于0-255计算亮度(更符合人眼感知)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # 亮度归一化到0-1
    luminance /= 255.0
    contrast_with_black = luminance
    contrast_with_white = 1 - luminance

    text_color: tuple[float, float, float] = (
        (0, 0, 0) if contrast_with_black > contrast_with_white else (1, 1, 1)
    )
    # 在调用contrast_color前添加
    # print(f"背景色(RGB 0-1): {rgb} → 转换为0-255: {[c*255 for c in rgb]}")
    # print(f"计算出的文字色: {text_color}")

    return text_color


def get_system_font_path() -> Path | None:
    """返回当前操作系统下的一个常用中文字体文件路径"""
    system = platform.system()
    if system == "Windows":
        # 优先使用微软雅黑（支持中文）
        fonts = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"]
    elif system == "Darwin":  # macOS
        # 苹方字体
        fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:  # Linux / Unix
        # 文泉驿微米黑（常见中文字体）
        fonts = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ]
    for f in fonts:
        if Path(f).exists():
            return Path(f)
    return None


def get_polygon_points(
    points: Sequence[Point], close: bool = True
) -> list[Point]:
    """转换为多边形坐标，如果原来是2点坐标，会自动转换成4点坐标，其他情况保留原来的坐标数量
    Args:
        points: 原坐标点
        close: 是否封闭，如果封闭，则把开始的点加入到最后

    """
    if not points:
        logger.error("get_polygon_points：传入的点的数量为空.")
        return []

    polygon_points: list[Point] = []
    if len(points) == 2:
        # 两点坐标，扩展成四点坐标
        p1, p3 = points[0], points[1]
        p2 = Point(x=p3.x, y=p1.y)
        p4 = Point(x=p1.x, y=p3.y)
        polygon_points = [p1, p2, p3, p4]
    else:
        polygon_points = list(points)

    if close:
        polygon_points.append(polygon_points[0])

    return polygon_points
