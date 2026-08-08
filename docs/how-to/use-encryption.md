# 操作指南：文件加密

`EncryptFile` 是一个行为类似 `pathlib.Path` 的**透明加解密文件**：开发时读写明文，
发布时只保留密文。加密基于 AES-CBC 模式（PKCS7 填充），密钥由调用方掌控。

## 密钥管理

密钥为 16 / 24 / 32 字节（对应 AES-128/192/256）。用 `generate_key` 生成，
用 `.hex()` 持久化：

```python
from commons.encrypt import generate_key

key = generate_key()          # 16 字节随机密钥
print(key.hex())              # 持久化保存，例如写入环境变量
```

恢复密钥：

```python
key = bytes.fromhex("88bed135e2ae528f8f5e4dfd58fa8467")
```

!!! warning "密钥丢失 = 密文丢失"
    密文无法在没有密钥的情况下解密。请把密钥放到安全的地方
    （环境变量 / 密钥管理系统），不要写进代码仓库。

## 创建 EncryptFile

`EncryptFile` 同时管理一对文件：明文路径 + 密文路径 + 密钥。

```python
from commons import EncryptFile

f = EncryptFile("plain.txt", "1234.dat", key)
```

## 读写（Path 风格）

```python
# 写入：写明文，并强制同步生成/更新密文
f.write_text('{"a": 1}')

# 读取：有明文读明文，否则解密密文
text = f.read_text()

# 字节读写同样支持
data = f.read_bytes()
```

## 发布流程：只保留密文

开发时明文在仓库里方便调试；发布时删除明文，只打包密文：

```shell
# 部署机
rm plain.txt
```

删除明文后，`EncryptFile` 会自动从密文解密：

```python
print(f.exists())      # True —— 明文或密文任一存在即为 True
print(f.read_text())   # 透明解密，返回原文
```

## 打开文件对象 `open`

`open` 接口对齐 `Path.open`：

```python
with f.open("r", encoding="utf-8") as fp:
    content = fp.read()

with f.open("w", encoding="utf-8") as fp:
    fp.write("hello")
```

- 读模式：有明文打开明文；仅有密文时返回内存中的解密流；
- 写模式：打开明文文件，关闭后自动同步密文。

## 手动同步密文

`sync()` 按需把明文加密到密文路径；`force=True` 强制重新加密：

```python
f.sync(force=True)
```

内部判定规则：

1. 明文缺失但密文存在 → 不处理（读时解密即可）；
2. 明文存在但无密文 → 自动加密；
3. 明文 mtime 不新于密文 → 跳过；
4. 否则解密密文与明文逐字节比对，不同才重新加密。

## 底层 API

不使用 `EncryptFile` 时，也可以用函数式 API 直接加解密：

```python
from commons.encrypt import (
    encrypt_file,
    decrypt_file,
    decrypt_file_to_bytes,
    decrypt_file_to_memory,
    decrypt_file_to_str,
)

encrypt_file("明文.txt", "密文.bin", key)
data = decrypt_file_to_bytes("密文.bin", key)
text = decrypt_file_to_str("密文.bin", key, encoding="utf-8")
mem = decrypt_file_to_memory("密文.bin", key)
```

### 密文文件格式

```text
[16 字节 IV] + [AES-CBC 密文]
```

## 实际场景：加密配置文件

结合 `Config`，可以用密文发布配置文件，密钥不落盘：

```python
from commons import Config, EncryptFile

key = bytes.fromhex(os.environ["CONFIG_KEY"])

config = Config(
    "./config/conf-template.xml",
    EncryptFile("./config/conf-private.xml", "./config/conf-private.enc", key),
)
```

## 完整 API

所有方法签名与属性见 [API 参考 · 文件加密 EncryptFile](../reference/encryption.md)。
