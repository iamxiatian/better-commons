# better-commons

**开箱即用的 Python 基础库**，把日常开发中反复出现的「配置加载、日志、大模型调用、文件加密、性能计时、文档标注」等能力，收敛为一个个小而美的工具模块。

![Python Version](https://img.shields.io/badge/python-%E2%89%A53.10-blue)
![Version](https://img.shields.io/badge/version-0.1.2-green)
![License](https://img.shields.io/badge/license-MIT-orange)

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

### 配置与 LLM

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

### 日志

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

### PDF / 图像标注

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

## 安装

```shell
# 推荐：使用 uv
uv pip install better-commons

# 或使用 pip
pip install better-commons
```

## 帮助文档

完整的帮助文档托管在 GitHub Pages（由 DeepSeek 生成），按 **Diátaxis** 框架组织：

> 🔗 **入口地址：https://iamxiatian.github.io/better-commons/**

- 📚 **[教程 (Tutorials)](https://iamxiatian.github.io/better-commons/tutorials/first-llm-app/)** —— 跟着做，从零写起你的第一个 LLM 应用；
- 🛠️ **[操作指南 (How-to)](https://iamxiatian.github.io/better-commons/how-to/use-config/)** —— 遇到具体问题，找到对应的解决步骤；
- 📖 **[API 参考 (Reference)](https://iamxiatian.github.io/better-commons/reference/config/)** —— 每个类的完整签名、参数与返回值；
- 💡 **[解释 (Explanation)](https://iamxiatian.github.io/better-commons/explanation/design/)** —— 为什么要这样设计，背后的取舍。

## 基础功能

### 仿照 Hadoop 格式的 XML 配置

配置文件的格式示例：

```xml
<configurations>
    <!--  配置模板  -->
    <property>
        <name>api.server.host</name>
        <value>0.0.0.0</value>
        <description>API服务器地址</description>
    </property>

    <property>
        <name>api.server.port</name>
        <value>8080</value>
        <description>API服务端口</description>
    </property>
</configurations>
```

使用示例

```python
import asyncio
from commons import Config, configure_logging

configure_logging()
config = Config("./config/conf-template.xml", "./config/conf-private.xml")

# config demo
host = config.get_option_str("api.server.host") or "127.0.0.1"

# 以下语句执行时会报错，因为`api.server2.port`不存在
# port:int = config.get_int("api.server2.port")
# 以下语句会返回None
# port = config.get_option_int("api.server2.port")

port = config.get_option_int("api.server.port")

print(host, port)
```

## 日常开发

运行以下脚本，可以自动格式化代码，并发现类型错误。

```shell
make fine
```

## 开发环境设置

1. 安装uv

   ```shell
   curl -fsSL https://get.uv.dev | bash
   # 或者通过pip安装
   pip install uv
   ```

2. 可编辑安装本项目

   ```shell
   #创建虚拟环境
   uv venv
   uv pip install -e .
   ```

3. 通过uv运行脚本main.py示例

   ```shell
   uv run -m commons.main
   ```

4. 代码格式化

  ```shell
  uv run ruff check --fix src
  #或者
  make fmt
  ```

5. git设置

避免中文文件名称乱码：

```shell
git config --global core.quotepath false # 让 Git 不要将非 ASCII 字符的文件名用引号括起来
```
