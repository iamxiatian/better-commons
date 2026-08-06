from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from commons.cv.annotate import (
    contrast_color,
    get_polygon_points,
    get_system_font_path,
)

from .types import Point, RegionLike


class ImageAnnotator:
    def __init__(
        self,
        font_size: int = 12,
        color_map: dict[str, tuple[int, int, int]] | None = None,
    ):
        self.font_size = font_size
        # 图片字体
        self.label_image_font = self._get_image_font(font_size)
        self.color_map: dict[str, tuple[int, int, int]] = color_map or {}

    def _get_image_font(self, font_size: int) -> ImageFont.BaseImageFont:
        font_path: Path | None = get_system_font_path()
        if font_path:
            return ImageFont.truetype(str(font_path), font_size)
        else:
            # 回退到默认字体
            return ImageFont.load_default()

    def _draw_element(
        self,
        image: Image.Image,
        label: str,
        points: list[Point],
        color: tuple[int, int, int],
    ) -> Image.Image:
        """
        在图像上标注元素
        Args:
            image: PIL图像对象
            label: 元素标签
            points: 元素边界框坐标列表, 顺序为左上、右上、右下、左下,
            color_map: 保存有
        """
        # 创建可绘制对象
        draw = ImageDraw.Draw(image, mode="RGBA")  # 启用alpha通道支持透明度
        # 1. 绘制边框(与PDF的rectangle保持同色同宽)
        draw.polygon(
            [p.as_tuple() for p in points],
            outline=color,
            width=2,
        )
        # print(image.width, image.height)
        # 2. 绘制文字背景
        # 文字框左上角与大框左上角对齐(核心:x=x1, y=y1)
        text_x, text_y = points[0].x, points[0].y

        # 1. 计算文字的实际边界框(基于当前字体和位置)
        text_bbox = draw.textbbox(
            (text_x, text_y),
            label,
            font=self.label_image_font,
        )

        # 2. 扩展文字背景框(保留边距, 让背景比文字稍大)
        # 上下左右各加5像素边距(可根据需要调整)
        label_padding = 5
        label_rect = (
            text_x,  # 左边界
            text_y,  # 上边界(向上扩展)
            text_bbox[2] + label_padding * 2,  # 右边界(向右扩展)
            text_bbox[3] + label_padding,  # 下边界(向下扩展)
        )

        # 3. 绘制背景框(从左上角开始, 与大框紧密贴合)
        draw.rectangle(
            label_rect,
            fill=(*color, 175),  # 带透明度的背景色
            outline=None,
        )

        # 4. 绘制文字(在背景框内居中微调, 避免贴边)

        text_color = contrast_color(
            (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
        )
        #  转换为0-255整数供ImageDraw使用
        text_color = tuple(int(c * 255) for c in text_color)
        draw.text(
            (text_x + label_padding, text_y),  # 文字左上角与大框左上角对齐
            label,
            font=self.label_image_font,
            fill=text_color,
        )

        return image

    def annot_image_file(
        self,
        image_file: Path,
        *,
        regions: list[RegionLike],
        save_file: Path,
    ) -> None:
        """在图片上绘制版面元素区域，用于EvaHan2026版面元素的可视化验证。
        Args:
            image_path (Path): 图片路径
            regions (list[EvahanRegion]): 版面元素区域列表
            color_map(dict[str, tuple[int, int, int]]): 元素名称和对应RGB的映射关系
            save_file (str): 输出图片路径
        """
        image: Image.Image = Image.open(image_file).convert("RGB")
        for region in regions:
            color = self.color_map.get(region.label) or (200, 0, 0)
            image = self._draw_element(
                image=image,
                label=region.label,
                points=get_polygon_points(region.points, close=False),
                color=color,
            )

        if not save_file.parent.exists():
            save_file.parent.mkdir(parents=True, exist_ok=True)

        image.save(save_file)


def annot_image_file(
    image_file: Path,
    *,
    regions: list[RegionLike],
    out_file: Path,
    color_map: dict[str, tuple[int, int, int]] | None = None,
    font_size: int = 12,
):
    """
    对image_file根据regions进行标记，保存到out_file中
    """
    # 创建输出目录
    out_file.parent.mkdir(parents=True, exist_ok=True)
    annotator = ImageAnnotator(font_size=font_size, color_map=color_map)
    annotator.annot_image_file(image_file, regions=regions, save_file=out_file)


if __name__ == "__main__":
    from commons.cv.types import SimpleRegion

    image_file = Path("./config/test.jpg")
    save_file = Path("./config/test_annot.jpg")
    region = SimpleRegion(
        label="text", points=[Point(100, 100), Point(300, 300)]
    )
    region2 = SimpleRegion(
        label="参考文献", points=[Point(350, 120), Point(500, 350)]
    )

    color_map = {"text": (200, 100, 0), "参考文献": (100, 200, 50)}
    annot_image_file(
        image_file,
        regions=[region, region2],
        out_file=save_file,
        color_map=color_map,
    )
