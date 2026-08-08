# better-commons

**开箱即用的 Python 基础库**，把日常开发中反复出现的「配置加载、日志、大模型调用、文件加密、性能计时、文档标注」等能力，收敛为一个个小而美的工具模块。

![Python Version](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![Version](https://img.shields.io/badge/version-0.1.2-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 为什么用它

- **少写样板代码**：Hadoop 风格 XML 配置 + 环境变量覆盖，一套代码在本地 / 生产无缝切换；
- **LLM 开箱即用**：对齐 OpenAI 兼容接口，内置多轮对话、续写、网关转发和 SQLite 响应缓存；
- **安全发布**：`EncryptFile` 开发时读写明文、发布时只保留密文，密钥由你自己掌控；
- **可观测性**：structlog 统一日志管线，异常自动捕获堆栈、自动补 `trace_id`；
- **类型安全**：全量类型注解，pyright / basedpyright 严格模式下 0 错误。

## 包含的模块

| 模块 | 导出接口 | 一句话说明 |
| ---- | -------- | ---------- |
| 配置 | `Config` / `ConfigError` | 加载 XML 配置，支持环境变量覆盖与加密配置文件 |
| 大模型 | `ChatClient` / `ChatModel` / `ChatError` / `create_chat_client` | 调用 OpenAI 兼容的 LLM API，支持缓存 |
| 加密 | `EncryptFile` | 类 `pathlib.Path` 的透明加解密文件 |
| 日志 | `configure_logging` | 一键配置 structlog 控制台 + 文件轮转日志 |
| 标注 | `annot_pdf_file` / `annot_image_file` | 在 PDF / 图像上绘制版面元素框 |
| 计时 | `Timer` / `TimerError` | 上下文管理器 / 装饰器 / 多阶段计时 |

## 30 秒快速上手

=== "配置与 LLM"

    ```python
    import asyncio

    from commons import Config, configure_logging, create_chat_client, ChatModel

    configure_logging()

    config = Config("./config/conf-template.xml", "./config/conf-private.xml")
    client = create_chat_client(
        ChatModel.DEEPSEEK_V4_FLASH,
        config=config,
        max_tokens=8192,
        cache_enabled=True,
    )

    response = asyncio.run(
        client.chat(system_prompt="You're a good helper.", user_prompt="hello")
    )
    print(response)
    ```

=== "日志"

    ```python
    import structlog
    from commons import configure_logging

    # 在应用入口初始化一次：控制台彩色 + 按天轮转的文件日志
    configure_logging(log_dir="./logs", backup_count=7)

    logger = structlog.get_logger(__name__)

    logger.info("服务启动成功", trace_id="req-10086")

    try:
        1 / 0
    except ZeroDivisionError:
        logger.error("计算异常")   # error 级别自动附带完整堆栈，无需 exc_info=True
    ```

=== "PDF / 图像标注"

    ```python
    from commons import annot_image_file, annot_pdf_file
    from commons.cv.types import Point, SimpleRegion

    # 一个版面元素：类别标签 + 坐标点
    region = SimpleRegion("text", [Point(100, 100), Point(300, 300)])

    # 在 PDF 上标注（页码 -> 区域列表），输出新文件
    annot_pdf_file(
        "./config/sample.pdf",
        {0: [region], 1: [region]},
        out_file="./config/sample_annot.pdf",
    )

    # 在图像上标注，按 label 指定线框颜色
    annot_image_file(
        "./config/test.jpg",
        regions=[region],
        color_map={"text": (200, 0, 0)},
        out_file="./config/test_annot.jpg",
    )
    ```

??? question "还没有配置文件？"
    参考 [快速开始](getting-started.md) 中的 XML 模板，或者直接使用
    [`Config`](reference/config.md) 手动写入配置项。

## 文档导航

这套文档遵循 **Diátaxis** 框架组织，按使用场景分为四类：

- 📚 **[教程 (Tutorials)](tutorials/first-llm-app.md)** —— 跟着做，从零写起你的第一个 LLM 应用；
- 🛠️ **[操作指南 (How-to)](getting-started.md)** —— 遇到具体问题，找到对应的解决步骤；
- 📖 **[API 参考 (Reference)](reference/config.md)** —— 每个类的完整签名、参数与返回值；
- 💡 **[解释 (Explanation)](explanation/design.md)** —— 为什么要这样设计，背后的取舍。

## 安装

```shell
# 推荐：使用 uv
uv pip install better-commons

# 或使用 pip
pip install better-commons
```

源码与示例见 [GitHub 仓库](https://github.com/iamxiatian/better-commons)。
