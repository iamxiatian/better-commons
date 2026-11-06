"""
=========================================================
在 PDF 页面上绘制版面区域
=========================================================

默认绘制矩形框。多边形与矩形四角不一致时同时绘制多边形。
类别名称在矩形左侧，order 不为空时在右侧。

修改历史
--------
2026-11-06: 按 RegionLike 的矩形框、多边形和 score、order 绘制
2026-11-06: 梯形等四点多边形与矩形四角不同时仍绘制
2026-11-06: 边框颜色改为按 cls_id 从 cls_color_map 查找
2026-11-07: label 画在左侧，order 画在右侧
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path

import pymupdf
import structlog

from commons.cv.annotate import (
    contrast_color,
    get_font_path,
    region_box,
    region_rgb,
    should_draw_polygon,
)
from commons.cv.types import Point, RegionLike, SimpleRegion


logger = structlog.get_logger(__name__)


class PdfAnnotator:
    def __init__(
        self,
        *,
        cls_color_map: dict[int, tuple[int, int, int]] | None = None,
        scaling_factor: float = 1.0,
    ):
        """
        初始化 PDF 标注器。

        在将 PDF 页面转为高分辨率图片（如用于目标检测）时，检测算法得到的区域坐标是基于放大后的图像的。
        为将这些坐标正确映射回原始 PDF 页面，需要根据图片的缩放比例对坐标进行反向缩放。

        Args:
            cls_color_map: 可选，类别编号到 RGB 颜色的映射，键为区域的 `cls_id`。
            scaling_factor: 坐标缩放因子，用于将检测到的区域坐标转换到 PDF 页面的原始坐标系。
                通常取值为“渲染图片时的缩放倍数”的倒数。例如，若渲染图片时缩放倍数为 2（即设置dpi=72*2），
                则此处应设为 0.5（即72/(72*2)），以对齐位置。
        """
        self.scaling_factor = scaling_factor
        self.pdf_font_size = 9  # PDF上的框的标题文字大小

        font_path = get_font_path()
        self.font = (
            pymupdf.Font(fontfile=str(font_path), language="zh-Hans")
            if font_path
            else pymupdf.Font("china-s")
        )
        self.stroke_width = 3  # 边框线宽(与PDF的width=1对齐)
        self.pdf_stroke_opacity = 0.6  # PDF线条和标题背景色的不透明度
        self.image_bg_opacity = int(255 * self.pdf_stroke_opacity)
        self.cls_color_map: dict[int, tuple[int, int, int]] = (
            cls_color_map or {}
        )

    def _scale(self, x: float, y: float) -> tuple[float, float]:
        """把图像坐标换算到 PDF 页面坐标。"""
        factor = self.scaling_factor
        return (x * factor, y * factor)

    def annot_pdf_page(
        self,
        page: pymupdf.Page,
        regions: Sequence[RegionLike],
    ) -> None:
        """
        在PDF的页面上上标注版面元素
        Args:
            page: 原始PDF页面
            regions: 版面元素列表(来自DocLayNetYoloAnalyzer的输出)
            cls_color_map: 根据 region.cls_id 获取对应的线框颜色
        """
        # 开始绘制(获取页面绘图上下文)
        for region in regions:
            color = region_rgb(region, self.cls_color_map)
            normalized_color = (
                color[0] / 255.0,
                color[1] / 255.0,
                color[2] / 255.0,
            )
            # 1. 创建一个与页面关联的 Shape 对象
            polygon_shape: pymupdf.Shape = page.new_shape()
            left, top, right, bottom = region_box(region)
            sx1, sy1 = self._scale(left, top)
            sx2, sy2 = self._scale(right, bottom)
            polygon_shape.draw_rect(pymupdf.Rect(sx1, sy1, sx2, sy2))
            if should_draw_polygon(region):
                poly = [self._scale(p.x, p.y) for p in region.polygon_points]
                if poly[0] != poly[-1]:
                    poly.append(poly[0])
                polygon_shape.draw_polyline(poly)

            # 4. 完成绘制，并应用样式 (颜色、线宽等)
            polygon_shape.finish(
                color=normalized_color,  # 边框颜色
                width=1,  # 边框宽度
                stroke_opacity=self.pdf_stroke_opacity,  # 0=全透, 1=不透
                # fill_opacity=0.4,  # 没 fill 时此项可省
                # fill=fill_color  # 如果需要填充，可以在此指定
            )

            baseline = sy1 + self.pdf_font_size
            if region.label:
                self._draw_tag(
                    page, region.label, sx1, baseline, normalized_color
                )
            if region.order is not None:
                self._draw_tag(
                    page,
                    str(region.order),
                    sx2,
                    baseline,
                    normalized_color,
                    align_right=True,
                )
            polygon_shape.commit()

    def _draw_tag(
        self,
        page: pymupdf.Page,
        text: str,
        x: float,
        y: float,
        color: tuple[float, float, float],
        *,
        align_right: bool = False,
    ) -> None:
        """绘制带底色的文字。

        Args:
            page: PDF 页面。
            text: 要绘制的文字。
            x: 左对齐时为矩形左边界，右对齐时为矩形右边界。
            y: 文字基线的纵坐标。
            color: 背景色，取值为 0 到 1。
            align_right: 为 True 时文字靠 x 的左侧排列。
        """
        probe = pymupdf.TextWriter(page.rect)
        probe.append(
            pymupdf.Point(0, y),
            text,
            font=self.font,
            fontsize=self.pdf_font_size,
        )
        ink = probe.text_rect
        # 右对齐时让文字右边缘贴住矩形右边界，左对齐时贴住左边界
        text_x = x - ink.x1 if align_right else x - ink.x0
        writer = pymupdf.TextWriter(page.rect)
        writer.append(
            pymupdf.Point(text_x, y),
            text,
            font=self.font,
            fontsize=self.pdf_font_size,
        )
        label_box = page.new_shape()
        rect = deepcopy(writer.text_rect)
        rect.y0 += 2
        label_box.draw_rect(rect)
        label_box.finish(
            fill=color,
            stroke_opacity=0,
            fill_opacity=self.pdf_stroke_opacity,
        )
        label_box.commit()
        writer.write_text(page, color=contrast_color(color))

    def annot_pdf_file(
        self,
        pdf_file: Path,  # (页码, PIL图像)
        regions_map: Mapping[int, Sequence[RegionLike]],
        out_file: Path,
    ) -> None:
        """
        对pdf_file根据regions进行标记，保存到out_file中
        """
        # 创建输出目录
        out_file.parent.mkdir(parents=True, exist_ok=True)

        doc: pymupdf.Document = pymupdf.open(pdf_file)

        # 处理每页
        for page_num, regions in regions_map.items():
            page: pymupdf.Page = doc[page_num]
            self.annot_pdf_page(page, regions)

        doc.save(out_file)


def annot_pdf_file(
    pdf_file: Path | str,  # (页码, PIL图像)
    regions_map: Mapping[int, Sequence[RegionLike]],
    *,
    out_file: Path | str,
    cls_color_map: dict[int, tuple[int, int, int]] | None = None,
    image_dpi: int = 72,
) -> None:
    """
    对 PDF 文件的指定页面进行区域标注，并保存标注后的 PDF。

    该函数会读取输入的 PDF 文件，根据提供的区域信息（如来自目标检测模型），
    在对应的页面上绘制多边形边框和标签文本，最终生成带有标注的 PDF 文件。

    Args:
        pdf_file: 输入 PDF 文件的路径。
        regions_map: 一个映射，键为页码（从 0 开始计数），值为该页面上所有区域的列表。
            每个区域需符合 `RegionLike` 协议。默认绘制矩形框；
            `polygon_points` 能围成多边形、且不是矩形框四角时同时绘制多边形。
        out_file: 标注后 PDF 的输出路径。
        cls_color_map: 可选，类别编号到 RGB 颜色的映射，键为 `cls_id`。
            例如：`{0: (255, 0, 0), 1: (0, 255, 0)}`。
            若未提供或某编号未在映射中，则使用默认红色。
        image_dpi: PDF转换为图片时使用的dpi。图片的坐标与PDF的坐标存在缩放关系，需要根据该dpi坐标缩放因子。
        将坐标缩放回PDF 原始坐标系。缩放因子为72/image_dpi

    Returns:
        None

    Raises:
        FileNotFoundError: 当 `pdf_file` 不存在时抛出。
        ValueError: 当 `regions_map` 中包含无效页码或区域数据格式错误时抛出。

    Example:
        >>> from pathlib import Path
        >>> regions = {0: [SimpleRegion(x1=10, y1=10, x2=100, y2=50, cls_id=0, label="title")]}
        >>> annot_pdf_file("input.pdf", regions, out_file="output.pdf", image_dpi=144)
    """
    scaling_factor = 72.0 / image_dpi
    annotator = PdfAnnotator(
        cls_color_map=cls_color_map, scaling_factor=scaling_factor
    )
    annotator.annot_pdf_file(Path(pdf_file), regions_map, Path(out_file))


if __name__ == "__main__":
    pdf_file = Path("./config/sample.pdf")
    out_file = Path("./config/sample_annot.pdf")
    region = SimpleRegion(
        label="text",
        x1=100,
        y1=100,
        x2=300,
        y2=300,
        cls_id=0,
        score=0.93,
        order=1,
    )
    region2 = SimpleRegion(
        cls_id=1,
        label="参考文献",
        x1=350,
        y1=120,
        x2=500,
        y2=350,
        polygon_points=(
            Point(360, 150),
            Point(480, 130),
            Point(490, 300),
            Point(400, 340),
            Point(355, 220),
        ),
        order=2,
    )
    regions_map: dict[int, Sequence[SimpleRegion]] = {
        0: (region,),
        1: (region, region2),
        2: (region2,),
    }
    cls_color_map = {0: (200, 100, 0), 1: (100, 200, 50)}
    annot_pdf_file(
        pdf_file,
        regions_map,
        out_file=out_file,
        cls_color_map=cls_color_map,
        image_dpi=72,
    )
