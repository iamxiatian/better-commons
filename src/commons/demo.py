import asyncio

from commons import ChatModel, Config, configure_logging, create_chat_client


if __name__ == "__main__":
    configure_logging()
    config = Config("./config/conf-template.xml", "./config/conf-private.xml")
    client = create_chat_client(
        ChatModel.DEEPSEEK_V4_FLASH, config=config, max_tokens=8192, cache_enabled=True
    )
    response = asyncio.run(
        client.chat(system_prompt="You're a good helper.", user_prompt="hello")
    )
    print(response)
