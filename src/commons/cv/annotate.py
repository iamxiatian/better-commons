"""
=========================================================
标注绘图的颜色、字体与区域标签
=========================================================

提供图像和 PDF 标注共用的字体查找、对比色和矩形边界。

修改历史
--------
2026-11-06: 按矩形框、多边形和 score、order 生成绘制信息
2026-11-06: 仅当四个顶点与矩形四角重合时才跳过多边形
2026-11-06: 按类别编号 cls_id 选取边框颜色
2026-11-07: 标签只保留类别名称，序号改到矩形右侧
"""

import platform
from collections.abc import Mapping, Sequence
from pathlib import Path

import structlog

from commons.cv.types import Point, RegionLike


logger = structlog.get_logger(__name__)

# 类别编号没有对应颜色时使用的边框颜色
DEFAULT_REGION_RGB: tuple[int, int, int] = (200, 0, 0)


def region_rgb(
    region: RegionLike,
    cls_color_map: Mapping[int, tuple[int, int, int]],
) -> tuple[int, int, int]:
    """按类别编号取边框颜色。

    Args:
        region: 待标注区域。
        cls_color_map: 类别编号到 RGB 的映射，键为 `cls_id`。

    Returns:
        该类别的颜色。编号为空或未配置时返回默认红色。
    """
    if region.cls_id is None:
        return DEFAULT_REGION_RGB
    return cls_color_map.get(region.cls_id, DEFAULT_REGION_RGB)


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


def get_font_path() -> Path | None:
    """
    如果config目录下存在文源圆体`LXGWWenKaiMonoLite-Regular.ttf`，则优先使用该字体，
    否则返回当前操作系统下的一个常用中文字体文件路径
    """
    specified_font = Path("./config/WenYuanRoundedSC-Regular.ttf")
    if specified_font.exists():
        return specified_font
    else:
        logger.warning(
            "PDF或者图片标记使用的指定字体不存在，请下载开源字体文源圆体并保存到'./config/WenYuanRoundedSC-Regular.ttf'"
        )

    system = platform.system()
    if system == "Windows":
        # 优先使用微软雅黑（支持中文）
        fonts = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"]
    elif system == "Darwin":  # macOS
        # 苹方字体
        fonts = [
            # "/System/Library/Fonts/PingFang.ttc",
            # "/System/Library/Fonts/Supplemental/Songti.ttc",
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


def region_box(region: RegionLike) -> tuple[float, float, float, float]:
    """返回矩形框的左、上、右、下边界。"""
    return (
        min(region.x1, region.x2),
        min(region.y1, region.y2),
        max(region.x1, region.x2),
        max(region.y1, region.y2),
    )


def should_draw_polygon(region: RegionLike) -> bool:
    """判断是否要在矩形框之外再绘制多边形。

    顶点少于 3 个时无法围成多边形。四个顶点若就是矩形框的四个角，
    与 x1、y1、x2、y2 重复，不再另画。梯形等其他四点形状仍会绘制。

    Args:
        region: 待标注的区域。

    Returns:
        需要绘制多边形时返回 True。
    """
    vertices = _open_polygon(region.polygon_points)
    if len(vertices) < 3:
        return False
    return not _is_bbox_corners(vertices, region)


def _open_polygon(points: Sequence[Point]) -> Sequence[Point]:
    """去掉与起点重合的闭合点。"""
    if (
        len(points) >= 2
        and points[0].x == points[-1].x
        and points[0].y == points[-1].y
    ):
        return points[:-1]
    return points


def _is_bbox_corners(points: Sequence[Point], region: RegionLike) -> bool:
    """四个顶点是否与矩形框四角重合，允许 1 像素误差。"""
    if len(points) != 4:
        return False
    pending = [
        (region.x1, region.y1),
        (region.x2, region.y1),
        (region.x2, region.y2),
        (region.x1, region.y2),
    ]
    for point in points:
        for index, (x, y) in enumerate(pending):
            if abs(point.x - x) <= 1 and abs(point.y - y) <= 1:
                pending.pop(index)
                break
        else:
            return False
    return not pending
