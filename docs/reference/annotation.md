# API 参考：标注 Annotation

在 PDF 页面 / 图像上绘制版面元素框。从 `commons` 直接导入
`annot_pdf_file`、`annot_image_file`；类型定义位于 `commons.cv.types`。

## annot_pdf_file

在 PDF 的多个页面上标注版面元素，输出新 PDF 文件。

::: commons.annot_pdf_file

## annot_image_file

在图像上标注版面元素，输出带框的新图像。

::: commons.annot_image_file

## PdfAnnotator

可复用的 PDF 标注器。

::: commons.cv.annotate_pdf.PdfAnnotator

## 版面元素类型

::: commons.cv.types.Point
::: commons.cv.types.SimpleRegion
::: commons.cv.types.RegionLike
