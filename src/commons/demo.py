import asyncio

from commons import (
    ChatModel,
    Config,
    EncryptFile,
    configure_logging,
    create_chat_client,
)


if __name__ == "__main__":
    configure_logging("./logs")
    key = bytes.fromhex("88bed135e2ae528f8f5e4dfd58fa8467")
    config = Config(
        "./config/conf-template.xml",
        EncryptFile(
            "./config/conf-private.xml", "./config/conf-private.enc", key
        ),
    )

    # config demo
    host = config.get_option_str("api.server.host") or "127.0.0.1"

    # 以下语句执行时会报错，因为`api.server2.port`不存在
    # port:int = config.get_int("api.server2.port")
    # 以下语句会返回None
    # port = config.get_option_int("api.server2.port")

    port = config.get_option_int("api.server.port")

    print(host, port)

    client = create_chat_client(
        ChatModel.QWEN3_30B_A3B,
        config=config,
        max_tokens=8192,
        enable_cache=True,
    )
    chat_reply = asyncio.run(
        client.chat(system_prompt="You're a good helper.", user_prompt="hello")
    )
    import rich

    rich.print(chat_reply)
    rich.print(chat_reply.response_id)
    rich.print(chat_reply.text)
