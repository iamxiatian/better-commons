from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path

import pymupdf
import structlog

from commons.cv.annotate import (
    contrast_color,
    get_polygon_points,
    get_system_font_path,
)
from commons.cv.types import Point, RegionLike, SimpleRegion


logger = structlog.get_logger(__name__)


class PdfAnnotator:
    # 添加默认DPI常量(300为基准)
    BASE_DPI = 300

    def __init__(
        self, dpi: int, color_map: dict[str, tuple[int, int, int]] | None = None
    ):
        """
        Args:
            color_map: 根据region的label，获取对应的线框颜色
        """
        # 基于DPI计算字体大小(按比例缩放)
        # self.dpi = dpi
        # scale_factor = self.dpi / self.BASE_DPI
        # self.pdf_font_size = int(40 * scale_factor) # 9

        self.pdf_font_size = 9  # PDF上的框的标题文字大小

        font_path = get_system_font_path()
        self.font = (
            pymupdf.Font(fontfile=str(font_path))
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
            text_x = region.points[0].x + 5  # 左偏移5px
            text_y = (
                region.points[0].y + self.pdf_font_size
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
    pdf_file: Path,  # (页码, PIL图像)
    regions_map: Mapping[int, Sequence[RegionLike]],
    *,
    out_file: Path,
    dpi: int = 144,
    color_map: dict[str, tuple[int, int, int]] | None = None,
):
    annotator = PdfAnnotator(dpi=dpi, color_map=color_map)
    annotator.annot_pdf_file(pdf_file, regions_map, out_file)


if __name__ == "__main__":
    pdf_file = Path("./config/sample.pdf")
    save_file = Path("./config/sample_annot.pdf")
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
        pdf_file, regions_map, out_file=save_file, color_map=color_map
    )
