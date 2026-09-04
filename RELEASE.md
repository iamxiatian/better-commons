## [V0.2.1] - 2026-09-04

- 完善llm_client中对异常的处理，如果接口是500，但reponse仍可能包含json信息，则记录并用于LLM错误分类

## [V0.2.0] - 2026-09-04

- logging_config中的configure_logging函数支持传入日志级别level，默认由INFO改为DEBUG
- llm_client中的DEBUG日志级别调整为INFO

## [V0.1.9]

- ChatReply增加response_id属性，方便获取LLM的返回ID
- ChatReply的create_chat_client的model_type支持str和ChatModel两种参数类型，方便扩展


## [V0.1.8]

- ChatReply增加raise_for_exception方法，方便调用直接抛出异常

## [V0.1.7]

- ChatReply增加exception字段，补充导致状态变化的异常信息，方便调用方获取使用

## [V0.1.6]

- ChatReply增加success和sensitive两个属性

## [V0.1.5]

- ChatReply的text属性返回类型为str，如果response_data为None, 则抛出异常

## [V0.1.4]

- ChatClient的返回结果由字符串改为ChatReply对象，记录返回结果，返回状态（如成功、超时、限速等）、模型从请求到返回的整体耗时
- ChatClient调整cache_enabled->enable_cache，增加enable_thinking参数
- ChatModel增加QWEN36_27B
- ChatStatus增加LENGTH_LIMIT，表示因MaxToken限制导致输出被截断
- llm_cache增加状态字段

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
