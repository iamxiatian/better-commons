# API 参考：文件加密 EncryptFile

AES-CBC 文件加解密。从 `commons` 直接导入 `EncryptFile`；底层函数位于
`commons.encrypt`。

## EncryptFile

行为类似 `pathlib.Path` 的透明加解密文件。

::: commons.EncryptFile

## generate_key

生成随机 AES 密钥。

::: commons.encrypt.generate_key

## 底层加解密函数

::: commons.encrypt.encrypt_file
::: commons.encrypt.decrypt_file
::: commons.encrypt.decrypt_file_to_bytes
::: commons.encrypt.decrypt_file_to_memory
::: commons.encrypt.decrypt_file_to_str
