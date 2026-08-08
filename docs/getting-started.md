# 快速开始

本页带你从零搭建一个可运行的 better-commons 环境，并跑通「加载配置 → 初始化日志 → 调用大模型」的最小链路。

## 1. 环境要求

- Python **3.10+**
- 建议使用 [`uv`](https://docs.astral.sh/uv/) 管理虚拟环境与依赖

## 2. 安装

```shell
# 创建虚拟环境
uv venv

# 安装项目（可编辑模式，方便开发调试）
uv pip install -e .

# 或者直接作为依赖安装
uv pip install better-commons
```

## 3. 准备配置文件

better-commons 使用 Hadoop 风格的 XML 配置。新建 `config/conf-template.xml`：

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

    <!--  LLM 接口配置  -->
    <property>
        <name>llm.deepseek_v4_flash.api.base</name>
        <value>http://www.yourserver.com/openAi/v1</value>
        <description>LLM 的 API 访问路径，替换为真实地址</description>
    </property>

    <property>
        <name>llm.deepseek_v4_flash.model.path</name>
        <value>deepseek-v4-flash</value>
        <description>模型名称</description>
    </property>

    <property>
        <name>llm.deepseek_v4_flash.authorization_key</name>
        <value>your_key</value>
        <description>Authorization 的值</description>
    </property>
</configurations>
```

!!! tip "私有配置不进版本库"
    把包含密钥的配置单独放一个文件（如 `conf-private.xml`），并加入 `.gitignore`。
    `Config` 支持同时加载多个文件，后面的文件可以覆盖前面文件中的同名配置项。

## 4. 第一个可运行示例

```python
import asyncio

from commons import (
    ChatModel,
    Config,
    configure_logging,
    create_chat_client,
)

configure_logging()  # 初始化日志：控制台彩色 + 文件轮转

config = Config(
    "./config/conf-template.xml",
    "./config/conf-private.xml",
)

host = config.get_option_str("api.server.host") or "127.0.0.1"
port = config.get_option_int("api.server.port")
print(f"api server: {host}:{port}")

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

运行：

```shell
uv run python main.py
```

你会在终端看到类似输出：

```
2026-08-06 10:00:00 - INFO - main.py:17 - <module>() - api server: 0.0.0.0:8080
2026-08-06 10:00:00 - INFO - main.py:26 - <module>() - load conf: ./config/conf-template.xml
2026-08-06 10:00:00 - INFO - main.py:26 - <module>() - load conf: ./config/conf-private.xml
你好！有什么可以帮助你的？
```

## 5. 接下来做什么

- 想深入某个模块？按需阅读对应的 **操作指南**；
- 需要完整的接口签名？查阅 **API 参考**；
- 想知道每个模块为什么这么设计？阅读 **设计理念**。
