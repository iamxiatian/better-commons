## [V0.3.5]- 2026-11-08

- 将config的save方法改成set方法
- Config.merge 可将另一个配置合并到当前对象，同名项以传入配置为准

## [V0.3.4]- 2026-11-08

- ChatClient 的字符串表示输出模型、地址和主要生成参数，不包含鉴权信息

## [V0.3.3] - 2026-11-06

- 调整图像和PDF标注绘制的标签

## [V0.3.2] - 2026-11-06

- 图像和PDF标注默认绘制 RegionLike 的矩形框（x1, y1, x2, y2）
- polygon_points 能围成多边形，且顶点不是矩形框四角时，同时绘制该多边形
- 有 order 时标签为「1: 标题」；有 score 时用主文字 2/3 字号紧跟在后面
- 标注颜色改为按类别编号 cls_id 从 cls_color_map 取值

## [V0.3.1] - 2026-10-27

- 修复conf读取xml元素值的错误，只要存在value_elem，则值可以是空字符串，但不能是None

## [V0.3.0] - 2026-10-15

- llm_client可以根据finish_reason判断是否被过滤

## [V0.2.9] - 2026-10-13

- llm_client返回text时，采用json的dumps方式，而不是直接强制转换为str

## [V0.2.8] - 2026-10-08

- Config的load方法增加clear参数，可以控制是否清空掉读取过的配置信息

## [V0.2.7] - 2026-09-22

- llm_client 增加 http_max_connections 和 http_max_keepalive_connections 参数，支持自定义连接池大小

## [V0.2.6] - 2026-09-12

- llm_client 增加 extra_body 参数，支持对不同模型进行个性化参数设置
- llm_cache 修复多线程/多进程并发问题：连接按线程隔离、open() 加锁保证单例、启用 WAL，
  避免共享同一 sqlite 连接导致事务状态错乱与写入静默丢失
- llm_cache 的 get() 改为纯读操作（命中计数改为内存累加、批量落盘），
  消除每次缓存命中都要写库带来的写锁竞争
- llm_client 的缓存读写改由线程池执行，避免同步 sqlite 调用阻塞事件循环
- ChatClient 复用 httpx 连接池（不再每次请求新建），新增 aclose() 与 async with 支持
- 修复超时状态分类：httpx 超时异常 str() 为空导致被归类为 UNKNOWN，
  现把异常类名纳入匹配，可正确识别为 TIMEOUT
- llm_cache增加异常捕获，避免缓存写入失败导致程序异常

## [V0.2.4] - 2026-09-11

- ChatClient增加custom_timeout参数，支持自定义超时时间

## [V0.2.3] - 2026-09-09

- PDF增加close方法，支持手动关闭pdf文件

## [V0.2.2] - 2026-09-04

- 完善llm_client，将ChatReply中的response_data由字符串类型改为字典类型

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
