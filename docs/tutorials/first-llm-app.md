# 教程：从零写一个带缓存和结构化输出的大模型应用

本教程带你从空白目录开始，构建一个完整的大模型问答应用。它会用到 `Config`、
`configure_logging`、`create_chat_client` 三个核心模块。

> 学习目标：理解 better-commons 的主链路 —— **配置驱动一切**。

## 第 1 步：搭建项目骨架

```shell
mkdir llm-demo && cd llm-demo
uv venv
uv pip install better-commons
```

创建目录结构：

```text
llm-demo/
├── config/
│   ├── conf-template.xml
│   └── conf-private.xml   # 私有密钥，加入 .gitignore
└── main.py
```

## 第 2 步：编写配置

`config/conf-template.xml`：

```xml
<configurations>
    <property>
        <name>llm.deepseek_v4_flash.api.base</name>
        <value>http://www.yourserver.com/openAi/v1</value>
        <description>替换为你的 API 地址</description>
    </property>
    <property>
        <name>llm.deepseek_v4_flash.model.path</name>
        <value>deepseek-v4-flash</value>
        <description>模型名称</description>
    </property>
    <property>
        <name>llm.deepseek_v4_flash.authorization_key</name>
        <value>sk-xxx</value>
        <description>鉴权密钥</description>
    </property>
</configurations>
```

`config/conf-private.xml`（可选，用于存放不与团队共享的密钥）：

```xml
<configurations>
    <!-- 覆盖模板中的密钥 -->
    <property>
        <name>llm.deepseek_v4_flash.authorization_key</name>
        <value>sk-我的真实密钥</value>
    </property>
</configurations>
```

!!! tip "环境变量也可以覆盖"
    配置键 `llm.deepseek_v4_flash.authorization_key` 对应的环境变量是
    `LLM_DEEPSEEK_V4_FLASH_AUTHORIZATION_KEY`。在 CI/CD 中往往比明文文件更方便。

## 第 3 步：初始化日志与配置

```python
from commons import Config, configure_logging

configure_logging(log_dir="./logs", backup_count=7)
config = Config(
    "./config/conf-template.xml",
    "./config/conf-private.xml",
)
```

`configure_logging` 组装好 structlog 管线：控制台彩色输出 + 按天轮转的文件日志。
`Config` 依次加载两个文件，后者同名配置覆盖前者。

## 第 4 步：创建客户端并对话

```python
import asyncio

from commons import ChatModel, create_chat_client

client = create_chat_client(
    ChatModel.DEEPSEEK_V4_FLASH,
    config=config,
    max_tokens=8192,
    cache_enabled=True,          # 开启 SQLite 响应缓存
)

async def main() -> None:
    response = await client.chat(
        system_prompt="You're a good helper.",
        user_prompt="用一句话介绍你自己",
    )
    print(response)

asyncio.run(main())
```

`create_chat_client` 会从配置中读取 `llm.deepseek_v4_flash.*` 下的 `api.base`、
`model.path`、`authorization_key` 等字段，自动构造 `ChatClient`。

## 第 5 步：加上结构化输出（JSON 模式）

大模型经常用于抽取信息。传 `response_format` 即可让模型输出 JSON：

```python
response = await client.chat(
    system_prompt="你是信息抽取助手，只输出 JSON。",
    user_prompt="张三，28岁，就职于字节跳动。",
    response_format={"type": "json_object"},
)
print(response)
# {"name": "张三", "age": 28, "company": "字节跳动"}
```

## 第 6 步：验证缓存生效

再次运行同样的请求，第一次会真实请求模型；第二次直接命中缓存，速度大幅提升。
打开缓存数据库确认：

```shell
sqlite3 ./data/llm_cache.db "select count(*) from cache;"
```

## 恭喜 🎉

你已经完成了一个带配置管理、日志、缓存和结构化输出的大模型应用。
接下来可以：

- 阅读 [操作指南 · 调用大模型](../how-to/use-llm-client.md) 了解多轮对话与网关转发；
- 阅读 [API 参考 · 大模型](../reference/llm-client.md) 查看每个参数的完整说明。
