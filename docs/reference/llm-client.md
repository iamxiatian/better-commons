# API 参考：大模型 ChatClient

封装 OpenAI 兼容 HTTP API 的异步客户端。从 `commons` 直接导入
`ChatClient`、`ChatError`、`ChatModel`、`create_chat_client`。

## create_chat_client

工厂函数，从 [`Config`](config.md) 读取配置创建客户端。

::: commons.create_chat_client

## ChatClient

::: commons.ChatClient

## ChatModel

::: commons.ChatModel

## ChatError

::: commons.ChatError

## ChatErrorType

`ChatError` 的 `error_type` 属性类型，定义异常类别。位于 `commons.llm_client`。

::: commons.llm_client.ChatErrorType
