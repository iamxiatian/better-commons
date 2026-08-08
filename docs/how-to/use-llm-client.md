# 操作指南：调用大模型

`ChatClient` 封装了对 **OpenAI 兼容 HTTP API**（vLLM、TGI、DeepSeek API 等）的
异步访问，提供续写、多轮对话、网关转发，以及开箱即用的 SQLite 响应缓存。

## 一、创建客户端

### 方式 A：从配置创建（推荐）

```python
import asyncio
from commons import ChatModel, Config, create_chat_client

config = Config("./config/conf-template.xml", "./config/conf-private.xml")

client = create_chat_client(
    ChatModel.DEEPSEEK_V4_FLASH,
    config=config,
    max_tokens=8192,
    cache_enabled=True,
)
```

`create_chat_client` 从配置中读取：

| 配置键 | 含义 |
| ------ | ---- |
| `llm.<model>.api.base` | API 基础地址（必填） |
| `llm.<model>.model.path` | 模型名称（必填） |
| `llm.<model>.authorization_key` | 鉴权密钥 |
| `llm.<model>.authorization_name` | 鉴权请求头名称，默认 `Authorization` |
| `llm.<model>.timeout` | 超时秒数 |
| `llm.default.temperature` | 温度，默认 `0.00001` |
| `llm.default.top_p` | 核采样，默认 `1.0` |
| `llm.default.repetition_penalty` | 重复惩罚，默认 `1.0` |
| `llm.default.n_choices` | 候选回复数，默认 `1` |

### 方式 B：直接构造

```python
from commons import ChatClient

client = ChatClient(
    api_base="http://localhost:8000/v1",
    model="Qwen2.5-7B-Instruct",
    authorization_key="sk-xxx",
    max_tokens=1024,
    timeout=60,
)
```

## 二、三种对话能力

### 简单对话 `chat`

系统指令 + 用户输入两轮对话，最常用：

```python
response = await client.chat(
    system_prompt="你是一个数学助手",
    user_prompt="1+1等于多少？",
)
# "1+1等于2。"
```

### 多轮对话 `chat_with_messages`

需要携带上下文时，直接传完整消息列表：

```python
messages = [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
    {"role": "user", "content": "今天天气如何？"},
]

response = await client.chat_with_messages(messages=messages)
```

### 续写 `complete`

给定一段文本，让模型继续生成：

```python
response = await client.complete("床前明月光")
# "，疑是地上霜。举头望明月，低头思故乡。"
```

## 三、结构化输出（JSON 模式）

传 `response_format` 即可要求模型返回 JSON：

```python
response = await client.chat(
    system_prompt="你是信息抽取助手，只输出 JSON。",
    user_prompt="从这段话中抽取人物和公司：马云创办了阿里巴巴。",
    response_format={"type": "json_object"},
)
```

## 四、开启响应缓存

相同请求（url + payload 完全一致）会命中 SQLite 缓存，直接返回，不重复计费：

```python
client = create_chat_client(
    ChatModel.DEEPSEEK_V4_FLASH,
    config=config,
    max_tokens=8192,
    cache_enabled=True,               # 默认关闭
    cache_path="./data/llm_cache.db", # 缓存文件位置
)
```

!!! note "缓存命中条件"
    缓存键由 URL 与完整 payload 生成。任何参数变化（如温度、max_tokens）都会
    视为不同请求。适合「固定 prompt 的批量处理」场景。

## 五、网关转发 `forward`

透传原始请求，返回 `(响应体 dict, HTTP 状态码)`，用于 API 网关代理：

```python
data, status = await client.forward(
    request_type="chat",
    payload={
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
    },
)
```

## 六、错误处理

所有请求失败都会抛出 `ChatError`，并带一个分类好的 `error_type`：

```python
from commons import ChatError, ChatErrorType  # ChatErrorType 从 commons.llm_client 导入

try:
    response = await client.chat(system_prompt="x", user_prompt="y")
except ChatError as e:
    print("错误类型:", e.error_type)
    print("错误信息:", e.message)

    if e.error_type == ChatErrorType.TIMEOUT:
        # 重试或降级
        ...
    elif e.error_type == ChatErrorType.RATE_LIMIT:
        # 退避等待
        ...
    elif e.error_type == ChatErrorType.SENSITIVE:
        # 提示用户输入违规
        ...
```

> `ChatErrorType` 位于 `commons.llm_client`，包含 `TIMEOUT` / `RATE_LIMIT` /
> `SENSITIVE` / `UNKNOWN` 四类，按错误信息关键词自动分类。

## 七、支持的模型枚举

`ChatModel` 是预置模型的枚举，需在配置中提供对应的 `llm.<value>.*` 配置：

| 枚举值 | 配置名 value |
| ------ | ------------ |
| `ChatModel.QWEN25_7B` | `qwen25_7b` |
| `ChatModel.QWEN3_4B` | `qwen3_4b` |
| `ChatModel.QWEN35_4B` | `qwen35_4b` |
| `ChatModel.QWEN3_30B_A3B` | `qwen3_30b_a3b` |
| `ChatModel.DEEPSEEK_V4_FLASH` | `deepseek_v4_flash` |
| `ChatModel.EXTERNAL` | `external` |
| `ChatModel.QWEN3_30B_A3B_LOCAL` | `qwen3_30b_a3b_local` |

## 完整 API

构造函数所有参数与每个方法的返回类型，见
[API 参考 · 大模型 ChatClient](../reference/llm-client.md)。
