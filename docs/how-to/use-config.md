# 操作指南：配置管理

`Config` 从 XML 文件加载配置，并允许同名环境变量覆盖。它与 Hadoop 的配置风格一致，
适合需要「模板 + 私有覆盖 + 环境变量」三明治式管理的场景。

## 配置文件的格式

```xml
<configurations>
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

每个 `<property>` 包含 `<name>`（配置键）和 `<value>`（配置值），
`<description>` 仅作说明，不影响解析。

## 加载配置文件

```python
from commons import Config

# 单个文件
config = Config("./config/conf-template.xml")

# 多个文件：后者覆盖前者的同名配置
config = Config("./config/conf-template.xml", "./config/conf-private.xml")

# 空构造后手动加载
config = Config()
config.load("./config/conf-template.xml")
```

`Config.load()` 会先清空现有配置再重新加载，可随时热更新。

### 参数类型

`Config` / `Config.load` 接受 `*conf_files`，每个参数可以是：

- `str` —— 路径字符串
- `Path` —— `pathlib.Path`
- `EncryptFile` —— 透明读取明/密文配置（见下方）

```python
from pathlib import Path
from commons import Config, EncryptFile

config = Config(
    Path("./config/conf-template.xml"),
    EncryptFile("./config/secret.xml", "./config/secret.dat", key),
)
```

!!! tip "加密配置"
    使用 `EncryptFile` 时，即使明文 `secret.xml` 被删除，只要 `secret.dat`
    密文存在，配置依然可以正常加载。详见 [文件加密](use-encryption.md)。

## 环境变量覆盖

配置键转大写、`.` 转 `_` 后即为环境变量名：

| 配置键 | 环境变量 |
| ------ | -------- |
| `my.api.port` | `MY_API_PORT` |
| `llm.deepseek_v4_flash.authorization_key` | `LLM_DEEPSEEK_V4_FLASH_AUTHORIZATION_KEY` |

```shell
export API_SERVER_PORT=9090
```

```python
config.get_int("api.server.port")  # 返回 9090，而不是 8080
```

## 读取配置值

`Config` 提供一组类型安全的 getter，`get_*` 找不到键时抛 `ConfigError`，
`get_option_*` 找不到键时返回 `None`：

| 方法 | 找不到时 | 说明 |
| ---- | -------- | ---- |
| `get_str(key)` | 抛异常 | 字符串 |
| `get_option_str(key)` | `None` | 可选字符串 |
| `get_int(key)` | 抛异常 | 整数 |
| `get_option_int(key)` | `None` | 可选整数 |
| `get_float(key)` | 抛异常 | 浮点数 |
| `get_option_float(key)` | `None` | 可选浮点数 |
| `get_bool(key)` | 抛异常 | 布尔 |
| `get_option_bool(key)` | `None` | 可选布尔 |
| `get_list(key)` | 抛异常 | 逗号分隔的字符串列表 |

布尔值支持 `true/false`、`1/0`、`yes/no`、`on/off`（不区分大小写）。

```python
host = config.get_option_str("api.server.host") or "127.0.0.1"
port = config.get_option_int("api.server.port") or 8080
debug = config.get_option_bool("app.debug") or False
hosts = config.get_list("app.hosts")          # ["a.com", "b.com"]
```

### 处理缺失配置

```python
from commons import ConfigError

try:
    port = config.get_int("api.server2.port")   # 键不存在
except ConfigError as e:
    print("配置缺失:", e)
```

## 写入与查看配置

```python
config.save("app.mode", "prod")          # 运行时写入
if config.has_key("app.mode"):
    ...

# 导出全部配置（可跳过敏感项）
config.show_config(skip_keys=["llm.deepseek_v4_flash.authorization_key"])
```

!!! warning "save 不写回文件"
    `save()` 只修改内存中的字典，不会持久化到 XML 文件，适合运行时注入。

## 完整 API

所有方法签名与异常见 [API 参考 · 配置 Config](../reference/config.md)。
