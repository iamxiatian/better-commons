# 操作指南：PDF 与图像标注

`annot_pdf_file` / `annot_image_file` 在 PDF 页面或图像上绘制版面元素框（label + 多边形），
常用于文档版面分析（如 DocLayNet）结果的可视化验证。

## 版面元素模型

标注对象是一个「区域」：包含类别标签 `label` 和一个坐标点列表 `points`。

```python
from commons.cv.types import Point, SimpleRegion

region = SimpleRegion(
    label="text",
    points=[Point(100, 100), Point(300, 300)],
)
```

- `Point(x, y)` —— 一个坐标点；
- `SimpleRegion(label, points)` —— 最常用的实现，`frozen` 数据类；
- `RegionLike` —— 协议（`label: str` + `points: Sequence[Point]`），任何满足该结构
  的类（含你自己的实现）都可以传入标注函数。

## 在 PDF 上标注

```python
from pathlib import Path
from commons import annot_pdf_file
from commons.cv.types import Point, SimpleRegion

pdf_file = Path("./config/sample.pdf")
save_file = Path("./config/sample_annot.pdf")

region = SimpleRegion(
    label="text",
    points=[Point(100, 100), Point(300, 300)],
)

# 页码 → 该页的区域列表；同一区域可以出现在多页
regions_map = {0: [region], 1: [region]}

annot_pdf_file(
    pdf_file,
    regions_map,
    save_file=save_file,
    dpi=144,                              # 渲染分辨率，默认 144
    color_map={"text": (200, 0, 0)},      # 按 label 指定线框颜色，可选
)
```

### 自定义颜色

`color_map` 把 `label` 映射为 RGB 颜色；未配置的 label 使用默认红色 `(200, 0, 0)`：

```python
color_map = {
    "text": (30, 120, 200),
    "title": (220, 80, 0),
    "table": (0, 150, 80),
}
```

### 直接使用 PdfAnnotator

需要批量或复用实例时，直接用 `PdfAnnotator`：

```python
from commons.cv.annotate_pdf import PdfAnnotator

annotator = PdfAnnotator(dpi=300, color_map=color_map)
annotator.annot_pdf_file(pdf_file, regions_map, save_file)
```

## 在图像上标注

```python
from commons import annot_image_file
from commons.cv.types import Point, SimpleRegion

annot_image_file(
    "./config/test.jpg",
    regions=[
        SimpleRegion("text", [Point(100, 100), Point(300, 300)]),
        SimpleRegion("title", [Point(50, 20), Point(200, 60)]),
    ],
    color_map={"text": (200, 0, 0), "title": (0, 0, 200)},
    save_file="./config/test_annot.jpg",
)
```

## 注意事项

- `points` 的坐标使用**页面/图像像素坐标**，注意与 PDF 渲染 DPI 匹配；
- 同一区域若出现在多个页面，需要为每个页码重复加入 `regions_map`；
- PDF 标注会生成带注释的**新文件**，不会修改原文件。

## 完整 API

`Point` / `SimpleRegion` / `RegionLike` / `PdfAnnotator` 的完整签名见
[API 参考 · 标注](../reference/annotation.md)。
