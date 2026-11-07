"""
=========================================================
在图像上绘制版面区域
=========================================================

默认绘制矩形框。多边形与矩形四角不一致时同时绘制多边形。
有 order 时标签为「1: 标题」，score 用较小字号紧跟其后。

修改历史
--------
2026-11-06: 按 RegionLike 的矩形框、多边形和 score、order 绘制
2026-11-06: 梯形等四点多边形与矩形四角不同时仍绘制
2026-11-06: 边框颜色改为按 cls_id 从 cls_color_map 查找
2026-11-07: label 画在左侧，order 画在右侧
2026-11-07: 有 order 时标签为「1: 标题」，score 用较小字号紧跟其后
2026-11-07: 图片字体类型改为 ImageFont 或 FreeTypeFont
"""

from __future__ import annotations

from pathlib import Path

import structlog
from PIL import Image, ImageDraw, ImageFont

from commons.cv.annotate import (
    contrast_color,
    get_font_path,
    region_box,
    region_caption,
    region_rgb,
    region_score_text,
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
        # 图片字体。score 使用主文字 2/3 的字号
        self.label_image_font = self._get_image_font(font_size)
        self.score_font_size = max(1, round(font_size * 2 / 3))
        self.score_image_font = self._get_image_font(self.score_font_size)
        self.cls_color_map: dict[int, tuple[int, int, int]] = (
            cls_color_map or {}
        )

    def _get_image_font(
        self, font_size: int
    ) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
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

        left, top, _right, _bottom = region_box(region)
        caption = region_caption(region)
        score = region_score_text(region)
        if caption or score:
            self._draw_tag(draw, caption, left, top, color, score=score)

        return image

    def _text_size(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    ) -> tuple[float, float]:
        """返回文字宽高。"""
        box = draw.textbbox((0, 0), text, font=font)
        return (box[2] - box[0], box[3] - box[1])

    def _draw_tag(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: float,
        y: float,
        color: tuple[int, int, int],
        *,
        score: str | None = None,
    ) -> None:
        """在矩形左上角绘制主文字，score 紧跟其后。

        Args:
            draw: PIL 绘图对象。
            text: 主文字，有 order 时已包含 ``1: 标题``。
            x: 背景左边界。
            y: 背景上边界。
            color: 背景 RGB 颜色。
            score: 置信度文本。不为空时用较小字号画在主文字后面。
        """
        padding = 5
        gap = 2 if text and score else 0
        label_w, label_h = (
            self._text_size(draw, text, self.label_image_font)
            if text
            else (0.0, 0.0)
        )
        score_w, score_h = (
            self._text_size(draw, score, self.score_image_font)
            if score
            else (0.0, 0.0)
        )
        content_h = max(label_h, score_h)
        bg_right = x + padding * 2 + label_w + gap + score_w
        text_rgb = contrast_color(
            (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
        )
        text_fill = tuple(int(channel * 255) for channel in text_rgb)
        draw.rectangle(
            (x, y, bg_right, y + content_h + padding),
            fill=(*color, 175),
            outline=None,
        )
        cursor = x + padding
        if text:
            draw.text(
                (cursor, y + content_h - label_h),
                text,
                font=self.label_image_font,
                fill=text_fill,
            )
            cursor += label_w + gap
        if score:
            draw.text(
                (cursor, y + content_h - score_h),
                score,
                font=self.score_image_font,
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
    且不是矩形框的四个角时，同时绘制多边形。有 order 时标签为
    「1: 标题」，score 用主文字 2/3 的字号紧跟在后面。

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
