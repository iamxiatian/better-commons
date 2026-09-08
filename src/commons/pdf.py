"""
PDF的处理。

核心概念
------
图像分辨率（像素尺寸）：指的是图片总共有多少个像素点。比如 1920 x 1080，它描述的是“这张图有多宽、多高”（数字大小）。

DPI（像素密度）：指的是每英寸长度里挤进去了多少个像素点。它描述的是“这张图有多密、多精细”（物理密度）。

图像像素尺寸 = 物理尺寸（英寸） × DPI

PDF 页面是有固定物理尺寸的（比如 A4 纸是 8.27 x 11.69 英寸）。当你提高 DPI（比如从 72 提到 300）时，
PDF 的物理尺寸没变，但你每英寸塞的像素变多了，所以 get_pixmap 输出的图像分辨率（宽度 x 高度）
自然会成倍增加（从 595x842 变成 2480x3508）。
"""

from pathlib import Path

import pymupdf
import structlog
from pymupdf.utils import getColor


logger = structlog.get_logger(__name__)


def merge_pdf_files(pdf_files: list[str | Path], out_file: str | Path) -> None:
    """
    将多个PDF文件按顺序合并为一个新的PDF文件

    参数:
        pdf_files: PDF文件路径列表（按合并顺序排列）
        out_file: 合并后输出PDF的路径

    异常:
        ValueError: 输入PDF列表为空或文件不是合法PDF
        FileNotFoundError: 指定的PDF文件不存在
    """
    # 校验输入列表是否为空
    if not pdf_files:
        raise ValueError("错误：需要合并的PDF文件列表不能为空！")

    # 创建空的目标PDF文档（用于合并）
    merged_pdf: pymupdf.Document = pymupdf.open()

    try:
        for pdf_path in pdf_files:
            # 转换为Path对象，方便文件校验
            pdf_file = Path(pdf_path)

            # 校验文件是否存在
            if not pdf_file.exists():
                raise FileNotFoundError(f"错误：PDF文件不存在 - {pdf_path}")

            # 校验文件是否为PDF（简单后缀校验+格式校验）
            if pdf_file.suffix.lower() != ".pdf":
                raise ValueError(f"错误：不是PDF文件 - {pdf_path}")

            # 打开当前PDF文件
            with pymupdf.open(pdf_path) as current_pdf:
                # 将当前PDF的所有页面插入到合并文档中
                merged_pdf.insert_pdf(current_pdf)  # type: ignore[reportUnknownMemberType]
                print(f"已合并：{pdf_path}")

        # 保存合并后的PDF（开启压缩，减小体积）
        merged_pdf.save(out_file, deflate=True)
        print(f"PDF合并完成！输出路径：{out_file}")

    finally:
        # 确保无论是否出错，都关闭合并文档释放资源
        merged_pdf.close()


def merge_images_to_pdf(image_paths: list[str | Path], out_file: str | Path):
    """
    将多张图片转换为A4大小的PDF，每页一张图片

    参数:
        image_paths: 图片路径列表（按顺序排列）
        output_pdf: 输出PDF的路径
    """
    # 创建新PDF文档
    doc: pymupdf.Document = pymupdf.open()

    # A4尺寸（单位：点，1点=1/72英寸，A4为210mm×297mm）
    a4_width = 595.3  # 210mm对应的点
    a4_height = 841.9  # 297mm对应的点

    for img_path in image_paths:
        # 检查图片文件是否存在
        if not Path(img_path).exists():
            print(f"警告：图片文件不存在 - {img_path}，已跳过")
            continue

        # 插入新页面（A4大小）
        page = doc.new_page(width=a4_width, height=a4_height)

        # 读取图片并获取尺寸
        img = pymupdf.Pixmap(img_path)
        img_bytes = img.tobytes("jpg", jpg_quality=80)

        temp_doc = pymupdf.open("jpg", img_bytes)
        img = temp_doc[0].get_pixmap()  # 从临时文档取第一页的Pixmap
        temp_doc.close()  # 关闭临时文档释放资源

        img_width = img.width
        img_height = img.height

        # 计算图片缩放比例（保持宽高比，适应A4页面）
        scale_width = a4_width / img_width
        scale_height = a4_height / img_height
        scale = min(
            scale_width, scale_height
        )  # 取较小的缩放比例，避免图片超出页面

        # scale = max(
        #     scale_width, scale_height
        # )  # 取较大的缩放比例，保证图片占满页面

        # 计算缩放后的图片尺寸
        new_width = img_width * scale
        new_height = img_height * scale

        # 计算图片在页面中的位置（居中放置）
        x = (a4_width - new_width) / 2
        y = (a4_height - new_height) / 2

        # 将图片插入页面
        page.insert_image(
            rect=pymupdf.Rect(
                x, y, x + new_width, y + new_height
            ),  # 图片位置和大小
            pixmap=img,
            # filename=img_path,
        )
        img = None  # 释放资源

    # 保存PDF
    doc.save(out_file)
    doc.close()
    print(f"PDF已生成：{out_file}")


def convert_pdf_to_images(
    pdf_file: str | Path,
    page_image_file_mapping: dict[int, str | Path],
    *,
    dpi: int = 72,
) -> None:
    """将pdf文件中指定页码的页面保存到对应的图片文件中。页码和图片名称的对应关系由page_name_mapping维持。
    dpi用于设置生成的图片的清晰度，默认值为72，此时PDF中的第一个点正好对应图像的一个像素。

     PDF 是一个“绝对单位”的世界。PDF 内部定义 1 个点（point）= 1/72 英寸，（每英寸 对应72 个像素）。
     所以当你想把 PDF 转成屏幕图片时，1 个 PDF 点就对应屏幕上的 1 个像素，这正好是 72 DPI。



    Args:
        pdf_file: 传入的pdf文件
        page_image_file_mapping: 页码与对应要保存的图片文件的映射，如{1: "1.jpg", 2:"second.png" }
        dpi: Dots Per Inch，每英寸点数
            - 100-150：快速，质量较低
            - 200：平衡（默认）
            - 250-300：高质量，较慢
    """
    if not page_image_file_mapping:
        return
    pdf = PdfFile(pdf_file)
    for page_index, image_file in page_image_file_mapping.items():
        pdf.page_to_image_file(page_index, image_file, dpi=dpi)


class PdfFile:
    def __init__(self, pdf_file: str | Path):
        self.pdf_file = Path(pdf_file)
        logger.info(f"open pdf file: {pdf_file}")
        self.doc: pymupdf.Document = pymupdf.open(pdf_file)
        self.page_count: int = self.doc.page_count
        logger.info(f"metadata of {pdf_file}: {self.doc.metadata} ")

    def page_to_image_file(
        self, page_index: int, image_file: str | Path, *, dpi: int = 72
    ):
        """
        读取一个PDF文件，并将指定页码转换为图片文件
        Args:
            page_index: 页码
            image_file: 图片文件路径
        Returns:
            None
        """
        if page_index < 0 or page_index >= self.page_count:
            raise ValueError(f"Page number {page_index} is out of range")

        page = self.doc[page_index]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False, annots=True)
        # width, height = pixmap.width, pixmap.height
        pixmap.save(image_file)

    def to_image_files(self, out_dir: Path | str, *, dpi: int = 72):
        """
        读取一个PDF文件，并且将其转换为图片文件
        Args:
            out_dir: 图片文件保存目录
        Returns:
            None
        """
        output_dir = Path(out_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True)

        for page_index in range(self.page_count):
            self.page_to_image_file(
                page_index, f"{output_dir}/page_{page_index + 1}.png", dpi=dpi
            )

    def remove_page(self, page_index: int):
        """
         删除指定页, 数值可以是负数，-1表示最后一页，-2表示倒数第二页，以此类推。第一页的页码为0。
        Args:
            page_index: 页码，可以是负数，-1表示最后一页
        Returns:
            None
        """
        if page_index < 0:
            abs_index = self.page_count + page_index
        else:
            abs_index = page_index
        if abs_index < 0 or abs_index >= self.page_count:
            raise ValueError(f"Page number {page_index} is out of range")
        self.doc.delete_page(abs_index)
        self.page_count -= 1

    def remove_by_indexes(self, page_indexes: list[int]):
        """
        删除一组指定页, 列表中的每个数值可以是负数，-1表示最后一页，-2表示倒数第二页，以此类推。第一页的页码为0。
        Args:
            page_indexes(list[int]): 要删除的页码列表
        Returns:
            None
        """
        indexes = []
        for index in page_indexes:
            if index < 0:
                abs_index = self.page_count + index
            else:
                abs_index = index
            if abs_index < 0 or abs_index >= self.page_count:
                raise ValueError(f"Page number {index} is out of range")
            indexes.append(abs_index)

        # 降序排序逐个删除，避免删除后索引变化
        for page_num in sorted(indexes, reverse=True):
            self.doc.delete_page(page_num)
            self.page_count -= 1

    def remove_by_range(self, start: int, end: int = -1):
        """
        删除指定范围内的页, 列表中的每个数值可以是负数，-1表示最后一页，-2表示倒数第二页，以此类推。第一页的页码为0。
        Args:
            start: 起始页码，包含start页
            end: 结束页码,包含end页，默认为-1，表示最后一页
        Returns:
            None
        """
        if start < 0:
            start = self.page_count + start
        if end < 0:
            end = self.page_count + end
        if start < 0 or start >= self.page_count:
            raise ValueError(f"Start page number {start} is out of range")
        if end < 0 or end >= self.page_count:
            raise ValueError(f"End page number {end} is out of range")
        if start > end:
            raise ValueError(
                f"Start page number {start} is greater than end page number {end}"
            )

        for page_num in range(end, start - 1, -1):
            self.doc.delete_page(page_num)
            self.page_count -= 1

    def keeponly_by_indexes(self, page_indexes: list[int]):
        """保留指定页码的页面，删除其他页面。"""
        for idx in reversed(range(self.page_count)):
            if idx not in page_indexes:
                self.doc.delete_page(idx)
                self.page_count -= 1

    def draw_rect(
        self,
        page_index: int,
        title: str,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        color_name: str = "black",
        line_width: float = 1.0,
    ):
        """
        绘制矩形
        Args:
            page_index: 页码，从0开始编号
            title: 标题
            x0: 矩形左上角的x坐标
            y0: 矩形左上角的y坐标
            x1: 矩形右下角的x坐标
            y1: 矩形右下角的y坐标
            color_name: 矩形的颜色
            line_width: 矩形的线宽
        Returns:
            None
        """
        if page_index < 0 or page_index >= self.page_count:
            raise ValueError(f"Page number {page_index} is out of range")

        page = self.doc[page_index]
        color: tuple = getColor(color_name)
        page.draw_rect(
            pymupdf.Rect(x0, y0, x1, y1), color=color, width=line_width
        )  # type: ignore[reportUnknownMemberType]

        # 添加”标题”标签（位置在矩形上方左偏右5像素）
        page.draw_rect(  # type: ignore[reportUnknownMemberType]
            pymupdf.Rect(x0 + 5, y0 - 15, x0 + 55, y0),
            color=color,
            fill=(1, 0.9, 0.9),  # 浅红色填充
            width=line_width,
        )
        # 绘制“标题”文字
        page.insert_text(
            (x0 + 15, y0 - 2),  # 文字位置（基准点为左下角）
            title,
            fontsize=12,  # 字体大小
            color=(1, 0, 0),
        )

    def extract_text_by_rect(
        self, page_index: int, x0: int, y0: int, x1: int, y1: int
    ) -> str:
        """
        提取指定页的指定矩形区域的文字
        Args:
            page_index: 页码
            rect: 矩形区域
        Returns:
            文字内容
        """
        if page_index < 0 or page_index >= self.page_count:
            raise ValueError(f"Page number {page_index} is out of range")
        page = self.doc[page_index]
        rect = pymupdf.Rect(x0, y0, x1, y1)
        text = page.get_textbox(rect)
        return text

    def add_text_watermark(
        self,
        text: str = "hello world",
        fontsize: int = 10,
        opacity: float = 0.5,
        color: tuple[int, int, int] = (0, 0, 0),
    ):  # 距底边 50 pt
        """
        把文字写到每一页固定位置
        """

        for page in self.doc:  # 逐页处理
            # 获取页面矩形
            rect = page.rect
            x = 10
            y = 10
            # 创建 TextWriter（支持透明度）
            tw = pymupdf.TextWriter(rect)
            _ = tw.append(
                pymupdf.Point(x, y + fontsize),  # 基线坐标
                text,
                font=pymupdf.Font("helv"),
                fontsize=fontsize,
            )
            tw.write_text(page)  # 真正写入页面

    def extract_text_by_index(self, page_index: int) -> str:
        """
        读取PDF指定页面的文本内容
        """
        page = self.doc[page_index]

        return str(page.get_text())

    def extract_text_by_range(self, start_page: int, end_page: int) -> str:
        """
        读取PDF指定页面的文本内容
        """
        text = ""
        if end_page < 0:
            end_page = self.page_count + end_page
        for page_number in range(start_page, end_page):
            page = self.doc[page_number]
            text += str(page.get_text())
        return text

    def _crop_page(self, page_index: int, x0: int, y0: int, x1: int, y1: int):
        """
        裁剪指定页的指定矩形区域
        Args:
            page_num: 页码
            rect: 矩形区域
        Returns:
            None
        """
        if page_index < 0 or page_index >= self.page_count:
            raise ValueError(f"Page number {page_index} is out of range")
        page = self.doc[page_index]
        rect = pymupdf.Rect(x0, y0, x1, y1)
        page.set_cropbox(rect)

    def crop_pages(
        self,
        page_indexes: list[int] | None = None,
        margins: tuple[float, float, float, float] = (0.08, 0.0, 0.01, 0.01),
    ) -> None:
        """
        裁剪PDF文件的指定页, 每一页按照上、下、左、右的顺序，相对于高宽的指定比例大小进行裁剪。
        例如，(0.1, 0.15, 0.2, 0.05)表示裁剪掉上侧10%、下侧15%、左侧20%、右侧5%。
        Args:
            page_indexes: 页码列表（0‑based索引），为None时裁剪所有页面
            margins: (上, 下, 左, 右) 四个方向的裁剪比例，取值范围 [0,1)
        Returns:
            None
        """
        doc: pymupdf.Document = self.doc
        # 验证比例
        top_ratio, bottom_ratio, left_ratio, right_ratio = margins
        for ratio in (top_ratio, bottom_ratio, left_ratio, right_ratio):
            if not 0 <= ratio < 1:
                raise ValueError(f"裁剪比例必须在 [0,1) 范围内，当前为 {ratio}")

        # 确定要处理的页面索引
        if page_indexes is None:
            pages_to_crop = range(len(doc))
        else:
            # 去重并排序，同时验证索引有效性
            unique_indexes = sorted(set(page_indexes))
            if any(i < 0 or i >= len(doc) for i in unique_indexes):
                raise IndexError("存在无效的页码索引")
            pages_to_crop = unique_indexes

        for page_num in pages_to_crop:
            page = doc[page_num]
            # 获取页面原始媒体框（通常也是裁剪框的初始值）
            original_rect = page.rect  # 或 page.mediabox
            width = original_rect.width
            height = original_rect.height

            # 计算新裁剪框的边界（坐标系：左下角为原点，向右为X+，向上为Y+）
            new_left = original_rect.x0 + left_ratio * width
            new_right = original_rect.x1 - right_ratio * width
            new_bottom = (
                original_rect.y0 + top_ratio * height
            )  # 注意：下侧从底部开始
            new_top = original_rect.y1 - bottom_ratio * height

            # 确保新矩形有效（若比例导致负宽度/高度，则抛出错误）
            if new_left >= new_right or new_bottom >= new_top:
                raise RuntimeError(
                    f"第{page_num}页裁剪后矩形无效，裁剪比例导致宽度或高度为负"
                )

            new_rect = pymupdf.Rect(new_left, new_bottom, new_right, new_top)
            # 设置裁剪框
            page.set_cropbox(new_rect)

    def save_as(self, out_file: str) -> None:
        """保存pdf文件"""
        self.doc.save(out_file)

    def save_text(self, out_file: str) -> None:
        """保存pdf文件的文本内容"""
        text = self.extract_text_by_range(0, self.page_count)

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)

    def close(self):
        """关闭pdf文件"""
        self.doc.close()

def main():
    pass
