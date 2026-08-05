import asyncio

from commons import ChatModel, Config, configure_logging, create_chat_client


if __name__ == "__main__":
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
