from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path

import pymupdf
import structlog

from commons.cv.annotate import (
    contrast_color,
    get_font_path,
    get_polygon_points,
)
from commons.cv.types import Point, RegionLike, SimpleRegion


logger = structlog.get_logger(__name__)


class PdfAnnotator:
    def __init__(
        self,
        *,
        color_map: dict[str, tuple[int, int, int]] | None = None,
        scaling_factor: float = 1.0,
    ):
        """
        初始化 PDF 标注器。

        在将 PDF 页面转为高分辨率图片（如用于目标检测）时，检测算法得到的区域坐标是基于放大后的图像的。
        为将这些坐标正确映射回原始 PDF 页面，需要根据图片的缩放比例对坐标进行反向缩放。

        Args:
            color_map: 可选，标签到 RGB 颜色元组的映射，用于为不同区域指定边框颜色。
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
        self.color_map: dict[str, tuple[int, int, int]] = color_map or {}

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
            color_map: 根据region的label，获取对应的线框颜色
        """
        # 开始绘制(获取页面绘图上下文)
        for region in regions:
            color = self.color_map.get(region.label) or (200, 0, 0)
            normalized_color = (
                color[0] / 255.0,
                color[1] / 255.0,
                color[2] / 255.0,
            )
            # 1. 创建一个与页面关联的 Shape 对象
            polygon_shape: pymupdf.Shape = page.new_shape()

            # 2. 定义多边形的四个顶点 (p1, p2, p3, p4 是 fitz.Point 对象)
            points: list[tuple[int, int]] = [
                p.as_tuple()
                for p in get_polygon_points(region.points, close=True)
            ]

            # 缩放坐标
            points = [
                (int(x * self.scaling_factor), int(y * self.scaling_factor))
                for x, y in points
            ]

            # 3. 绘制多边形
            polygon_shape.draw_polyline(points)

            # 4. 完成绘制，并应用样式 (颜色、线宽等)
            polygon_shape.finish(
                color=normalized_color,  # 边框颜色
                width=1,  # 边框宽度
                stroke_opacity=self.pdf_stroke_opacity,  # 0=全透, 1=不透
                # fill_opacity=0.4,  # 没 fill 时此项可省
                # fill=fill_color  # 如果需要填充，可以在此指定
            )

            # 2. 绘制元素类型文字(在矩形框上方左侧)
            # 计算文字位置(确保在页面范围内)
            text_x = points[0][0] + 7  # 偏移10px
            text_y = (
                points[0][1] + self.pdf_font_size
            )  # 上偏移(文字大小+2px间距)

            point = pymupdf.Point(
                text_x, text_y
            )  # 12 是字体基线下降距离, 可再调

            # 2.1 先量一下文字占多大地方
            label_writer = pymupdf.TextWriter(
                page.rect
            )  # 临时对象, 仅用来测尺寸
            label_writer.append(
                point, region.label, font=self.font, fontsize=self.pdf_font_size
            )

            # 新建一个图形层, 设 80 % 不透明度, 画反色矩形
            label_box = page.new_shape()
            rect = deepcopy(label_writer.text_rect)
            rect.y0 += 2  # 顶部适度下移
            label_box.draw_rect(rect)
            label_box.finish(
                fill=normalized_color,  # 背景色
                stroke_opacity=0,  # 不要边框
                fill_opacity=self.pdf_stroke_opacity,  # 关键:设置不透明度
            )
            label_box.commit()
            label_writer.write_text(
                page, color=contrast_color(normalized_color)
            )  # 将文字写入页面
            polygon_shape.commit()

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
    color_map: dict[str, tuple[int, int, int]] | None = None,
    image_dpi: int = 72,
):
    """
    对 PDF 文件的指定页面进行区域标注，并保存标注后的 PDF。

    该函数会读取输入的 PDF 文件，根据提供的区域信息（如来自目标检测模型），
    在对应的页面上绘制多边形边框和标签文本，最终生成带有标注的 PDF 文件。

    Args:
        pdf_file: 输入 PDF 文件的路径。
        regions_map: 一个映射，键为页码（从 0 开始计数），值为该页面上所有区域的列表。
            每个区域需符合 `RegionLike` 协议（包含 `points`、`label` 等属性）。
        out_file: 标注后 PDF 的输出路径。
        color_map: 可选，标签到 RGB 颜色元组的映射，用于为不同标签的区域指定边框颜色。
            例如：`{"title": (255, 0, 0), "text": (0, 255, 0)}`。
            若未提供或某标签未在映射中，则使用默认颜色（如红色）。
        image_dpi: PDF转换为图片时使用的dpi。图片的坐标与PDF的坐标存在缩放关系，需要根据该dpi坐标缩放因子。
        将坐标缩放回PDF 原始坐标系。缩放因子为72/image_dpi

    Returns:
        None

    Raises:
        FileNotFoundError: 当 `pdf_file` 不存在时抛出。
        ValueError: 当 `regions_map` 中包含无效页码或区域数据格式错误时抛出。

    Example:
        >>> from pathlib import Path
        >>> regions = {0: [Region(points=[(10,10),(100,10),(100,50),(10,50)], label="title")]}
        >>> annot_pdf_file("input.pdf", regions, out_file="output.pdf", scaling_factor=0.5)
    """
    scaling_factor = 72.0 / image_dpi
    annotator = PdfAnnotator(color_map=color_map, scaling_factor=scaling_factor)
    annotator.annot_pdf_file(Path(pdf_file), regions_map, Path(out_file))


if __name__ == "__main__":
    pdf_file = Path("./config/sample.pdf")
    out_file = Path("./config/sample_annot.pdf")
    region = SimpleRegion(
        label="text", points=[Point(100, 100), Point(300, 300)]
    )
    region2 = SimpleRegion(
        label="参考文献", points=[Point(350, 120), Point(500, 350)]
    )
    regions_map: dict[int, Sequence[SimpleRegion]] = {
        0: [region],
        1: [region, region2],
        2: [region2],
    }
    color_map = {"text": (200, 100, 0), "参考文献": (100, 200, 50)}
    annot_pdf_file(
        pdf_file,
        regions_map,
        out_file=out_file,
        color_map=color_map,
        image_dpi=72,
    )
