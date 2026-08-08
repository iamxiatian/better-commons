from commons import annot_image_file, annot_pdf_file, convert_pdf_to_images
from commons.cv.types import Point, SimpleRegion


if __name__ == "__main__":
    from commons import annot_image_file, annot_pdf_file
    from commons.cv.types import Point, SimpleRegion

    dpi = 72 * 3
    convert_pdf_to_images(
        "./config/sample.pdf", {0: "./config/sample.jpg"}, dpi=72 * 3
    )

    # 一个版面元素：类别标签 + 坐标点
    region1 = SimpleRegion("标题", [Point(150, 100), Point(300, 300)])
    region2 = SimpleRegion("text", [Point(200, 350), Point(450, 600)])

    color_map = {"标题": (200, 100, 0), "text": (0, 200, 200)}

    # 在图像上标注，按 label 指定线框颜色
    annot_image_file(
        "./config/sample.jpg",
        regions=[region1, region2],
        color_map=color_map,
        out_file="./config/sample_annot.jpg",
    )

    # 在 PDF 上标注（页码 -> 区域列表），输出新文件
    # 为对齐，需要设置PDF生成图片时使用的dpi
    annot_pdf_file(
        "./config/sample.pdf",
        {0: [region1, region2], 1: [region1, region2]},
        out_file="./config/sample_annot.pdf",
        color_map=color_map,
        image_dpi=dpi,
    )
