# Python Better Commons(better-commons)

Python版本的基础库，方便开发复用.

## 基础功能

### 仿照Hadoop格式的XML配置

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

### 封装OpenAI格式的大模型API调用，并支持自动缓存大模型输出结果，重复内容的调用直接从缓存中获取结果。

示例代码如下：

```python
import asyncio
from commons import ChatModel, Config, configure_logging, create_chat_client

configure_logging()
# 参考./config/conf-template.xml，设置具体的DEEPSEEK_V4_FLASH的值
config = Config("./config/conf-template.xml", "./config/conf-private.xml")
client = create_chat_client(
    ChatModel.DEEPSEEK_V4_FLASH, config=config, max_tokens=8192, cache_enabled=True
)
response = asyncio.run(
    client.chat(system_prompt="You're a good helper.", user_prompt="hello")
)
print(response)
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
