import asyncio
import base64

from commons import (
    ChatModel,
    Config,
    annot_image_file,
    annot_pdf_file,
    configure_logging,
    convert_pdf_to_images,
    create_chat_client,
)
from commons.cv.types import Point, SimpleRegion


configure_logging()
config = Config(
    "./config/conf-template.xml",
    "./config/conf-private.xml",
)


def llm_cmd():
    client = create_chat_client(
        ChatModel.QWEN36_27B,
        config=config,
        max_tokens=8192,
        enable_cache=True,
    )
    print("测试语言模型")
    # query = '请按照json格式，输出中国历史上的所有朝代，示例格式为:{"name":"夏", ...}'
    # query = "hello"
    # chat_reply = asyncio.run(client.chat(user_prompt=query))
    # print(chat_reply)

    print("测试视觉模型")
    # 1. 读取本地图像文件并编码为 Base64
    image_path = "./config/sample.png"  # 替换为你的实际路径

    with open(image_path, "rb") as image_file:
        # 编码为 Base64 并解码为 UTF-8 字符串
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    # 2. 构建 Data URL
    # 根据你的图片类型，将下面的 'image/png' 替换为 'image/jpeg' 或 'image/webp' 等
    data_url = f"data:image/png;base64,{base64_image}"
    user_input = "请详细描述这张图片中的文档内容。对于每一个识别出的文本块、表格或图片，请先提供其内容，然后以 [x1, y1, x2, y2] 的格式（使用0-1000的归一化坐标）给出其边界框位置。最终结果请以清晰的Markdown格式输出。"
    user_input = "请将这份文档解析为 Qwenvl Markdown 格式。"
    user_input = "请将这份文档解析为 Qwenvl HTML 格式。"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": user_input},
            ],
        }
    ]

    chat_reply = asyncio.run(client.chat_messages(messages=messages))
    print(chat_reply)
    print(chat_reply.text)


def annotate_cmd():

    dpi = 72 * 3
    convert_pdf_to_images(
        "./config/sample.pdf", {0: "./config/sample.png"}, dpi=72 * 3
    )

    # 一个版面元素：矩形框；多边形与矩形四角不同时会额外绘制
    region1 = SimpleRegion(
        x1=150,
        y1=100,
        x2=300,
        y2=300,
        cls_id=0,
        label="标题",
        score=0.92,
        order=1,
    )
    region2 = SimpleRegion(
        x1=200,
        y1=350,
        x2=450,
        y2=600,
        cls_id=1,
        label="text",
        polygon_points=(
            Point(220, 360),
            Point(400, 380),
            Point(430, 560),
            Point(250, 540),
            Point(210, 450),
        ),
        score=0.81,
        order=2,
    )

    cls_color_map = {0: (200, 100, 0), 1: (0, 200, 200)}

    # 在图像上标注，按 cls_id 指定线框颜色
    annot_image_file(
        "./config/sample.png",
        regions=[region1, region2],
        cls_color_map=cls_color_map,
        out_file="./config/sample_annot.png",
    )

    # 在 PDF 上标注（页码 -> 区域列表），输出新文件
    # 为对齐，需要设置PDF生成图片时使用的dpi
    annot_pdf_file(
        "./config/sample.pdf",
        {0: [region1, region2], 1: [region1, region2]},
        out_file="./config/sample_annot.pdf",
        cls_color_map=cls_color_map,
        image_dpi=dpi,
    )


if __name__ == "__main__":
    annotate_cmd()
    # llm_cmd()
