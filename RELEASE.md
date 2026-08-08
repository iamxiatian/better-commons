## [V0.1.3] - 2026-08-07

- annot_image_file和annot_image_file接收的文件的参数支持Path和str两种方式
- 支持pdf转换为图片，以及图片和pdf的坐标，基于dpi进行转换的处理。

## [V0.1.2] - 2026-08-06

- 新增`annot_image_file`, `annot_image_file`，实现对在图片和PDF文件上画区域和标记
- 新增 `EncryptFile`：Path 风格透明加解密文件，构造为 `EncryptFile(明文路径, 密文路径, key)`（有明文读明文并自动同步密文，无明文则解密密文）
- 新增 `generate_key()`：随机生成 AES 密钥（16/24/32 字节）
- 新增依赖 `cryptography`（AES-CBC 文件加解密）

## [V0.1.1] - 2026-08-05

- Python降低到3.10
- 去掉pypinyin的无用依赖
