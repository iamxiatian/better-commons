"""
=========================================================
在图像上绘制版面区域
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

from pathlib import Path

import structlog
from PIL import Image, ImageDraw, ImageFont

from commons.cv.annotate import (
    contrast_color,
    get_font_path,
    region_box,
    region_rgb,
    should_draw_polygon,
)

from .types import Point, RegionLike


logger = structlog.get_logger(__name__)


class ImageAnnotator:
    def __init__(
        self,
        font_size: int = 12,
        cls_color_map: dict[int, tuple[int, int, int]] | None = None,
    ):
        """
        Args:
            font_size: 标签字号。
            cls_color_map: 类别编号到 RGB 的映射，键为区域的 `cls_id`。
        """
        self.font_size = font_size
        # 图片字体
        self.label_image_font = self._get_image_font(font_size)
        self.cls_color_map: dict[int, tuple[int, int, int]] = (
            cls_color_map or {}
        )

    def _get_image_font(self, font_size: int) -> ImageFont.BaseImageFont:
        font_path: Path | None = get_font_path()
        if font_path:
            return ImageFont.truetype(str(font_path), font_size)
        else:
            # 回退到默认字体
            return ImageFont.load_default()

    def _draw_element(
        self,
        image: Image.Image,
        region: RegionLike,
        color: tuple[int, int, int],
    ) -> Image.Image:
        """在图像上绘制矩形框、可选多边形和标签。

        Args:
            image: PIL 图像对象。
            region: 待标注区域。
            color: 边框和标签背景的 RGB 颜色。
        """
        draw = ImageDraw.Draw(image, mode="RGBA")
        draw.rectangle(
            (region.x1, region.y1, region.x2, region.y2),
            outline=color,
            width=2,
        )
        if should_draw_polygon(region):
            draw.polygon(
                [p.as_tuple() for p in region.polygon_points],
                outline=color,
                width=2,
            )

        left, top, right, _bottom = region_box(region)
        if region.label:
            self._draw_tag(draw, region.label, left, top, color)
        if region.order is not None:
            self._draw_tag(
                draw,
                str(region.order),
                right,
                top,
                color,
                align_right=True,
            )

        return image

    def _draw_tag(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int],
        *,
        align_right: bool = False,
    ) -> None:
        """绘制带底色的文字。

        Args:
            draw: PIL 绘图对象。
            text: 要绘制的文字。
            x: 左对齐时为背景左边界，右对齐时为背景右边界。
            y: 背景上边界。
            color: 背景 RGB 颜色。
            align_right: 为 True 时文字靠 x 的左侧排列。
        """
        padding = 5
        probe = draw.textbbox((0, y), text, font=self.label_image_font)
        text_w = probe[2] - probe[0]
        if align_right:
            bg_right = x
            bg_left = x - text_w - padding * 2
        else:
            bg_left = x
            bg_right = x + text_w + padding * 2
        text_rgb = contrast_color(
            (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
        )
        text_fill = tuple(int(channel * 255) for channel in text_rgb)
        draw.rectangle(
            (bg_left, y, bg_right, probe[3] + padding),
            fill=(*color, 175),
            outline=None,
        )
        draw.text(
            (bg_left + padding, y),
            text,
            font=self.label_image_font,
            fill=text_fill,
        )

    def annot_image_file(
        self,
        image_file: Path,
        *,
        regions: list[RegionLike],
        out_file: Path,
    ) -> None:
        """在图片上绘制版面元素区域，用于EvaHan2026版面元素的可视化验证。
        Args:
            image_path (Path): 图片路径
            regions (list[EvahanRegion]): 版面元素区域列表
            cls_color_map: 类别编号 cls_id 到 RGB 的映射
            out_file (Path): 输出图片路径
        """
        image: Image.Image = Image.open(image_file).convert("RGB")
        logger.info(
            f"annotate {image.width} x {image.height} image: {image_file}"
        )
        for region in regions:
            color = region_rgb(region, self.cls_color_map)
            image = self._draw_element(
                image=image,
                region=region,
                color=color,
            )

        if not out_file.parent.exists():
            out_file.parent.mkdir(parents=True, exist_ok=True)

        image.save(out_file)


def annot_image_file(
    image_file: Path | str,
    *,
    regions: list[RegionLike],
    out_file: Path | str,
    cls_color_map: dict[int, tuple[int, int, int]] | None = None,
    font_size: int = 12,
) -> None:
    """按区域在图像上绘制矩形框并保存。

    默认绘制 x1、y1、x2、y2 确定的矩形。polygon_points 能围成多边形，
    且不是矩形框的四个角时，同时绘制多边形。类别名称在左侧，
    order 不为空时在右侧单独绘制。

    Args:
        image_file: 输入图像路径。
        regions: 待标注区域。
        out_file: 输出图像路径。
        cls_color_map: 类别编号到 RGB 颜色的映射，键为 `cls_id`。
        font_size: 标签字号。
    """
    # 创建输出目录
    annotator = ImageAnnotator(font_size=font_size, cls_color_map=cls_color_map)
    annotator.annot_image_file(
        Path(image_file), regions=regions, out_file=Path(out_file)
    )


if __name__ == "__main__":
    from commons.cv.types import SimpleRegion

    image_file = Path("./config/sample.jpg")
    out_file = Path("./config/sample_annot.jpg")
    region = SimpleRegion(
        x1=100,
        y1=100,
        x2=300,
        y2=300,
        cls_id=0,
        label="text",
        score=0.93,
        order=1,
    )
    region2 = SimpleRegion(
        x1=350,
        y1=120,
        x2=500,
        y2=350,
        cls_id=1,
        label="参考文献",
        polygon_points=(
            Point(360, 150),
            Point(480, 130),
            Point(490, 300),
            Point(400, 340),
            Point(355, 220),
        ),
        score=0.81,
        order=2,
    )

    cls_color_map = {0: (200, 100, 0), 1: (100, 200, 50)}
    annot_image_file(
        image_file,
        regions=[region, region2],
        out_file=out_file,
        cls_color_map=cls_color_map,
    )
