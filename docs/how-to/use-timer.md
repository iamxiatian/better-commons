# 操作指南：代码计时

`Timer` 提供与 `codetiming.Timer` 核心用法等价的轻量计时能力，支持四种用法：
普通对象、上下文管理器、函数装饰器、多阶段累计报告。计时使用单调高精度时钟
`perf_counter`。

## 基础用法：手动 start / stop

```python
from commons import Timer

timer = Timer(name="load", text="{:.3f} 秒", logger=print)
timer.start("读取文件")
load_data()
timer.stop()

timer.start("解析内容")
parse_data()
timer.stop()

print(timer.report())   # 输出各阶段累计耗时
# {'读取文件': 0.123, '解析内容': 0.456}
```

## 上下文管理器

```python
with Timer("process"):
    run_task()
```

进入 `with` 自动 `start()`，退出自动 `stop()`，不拦截业务异常。

## 函数装饰器

```python
@Timer(text="处理耗时：{:.3f} 秒")
def process() -> None:
    ...

process()   # 函数执行完自动打印耗时
```

## 多阶段累计

同一实例可以多次 `start("阶段名")`，相同阶段名会累加：

```python
timer = Timer(logger=None)   # logger=None 只记录不输出
for i in range(10):
    timer.start("fetch")
    fetch(i)
    timer.stop()
    timer.start("parse")
    parse(i)
    timer.stop()

print(timer.report())
# {'fetch': 0.98, 'parse': 1.21}
```

未命名阶段的耗时归入 `"total"`。

## 全局统计

所有**命名**计时器的累计秒数会同步保存到 `Timer.timers`（类级字典）：

```python
Timer.timers["fetch"]        # 全局 fetch 阶段总耗时
```

## 状态查询

```python
timer.running    # True / False —— 是否正在计时
```

## 参数说明

| 参数 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `name` | `None` | 计时器名称；命名后计入 `Timer.timers` |
| `text` | `"{:.4f} seconds"` | 输出模板，`{}` 处填入秒数 |
| `logger` | `print` | 输出函数；设为 `None` 则静默记录 |

## 完整 API

方法签名与异常见 [API 参考 · 计时 Timer](../reference/timer.md)。
