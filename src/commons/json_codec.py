"""
=========================================================
高性能 JSON 编解码
=========================================================

基于 orjson 统一处理项目中的 JSON 字符串和字节载荷。

修改历史
--------
2026-07-25: 新增高性能 JSON 编解码工具
"""

from __future__ import annotations

from typing import Any

import orjson


def dumps(
    value: object,
    *,
    indent: bool = False,
    sort_keys: bool = False,
) -> str:
    """将对象序列化为 JSON 字符串。"""
    return dumps_bytes(
        value,
        indent=indent,
        sort_keys=sort_keys,
    ).decode("utf-8")


def dumps_bytes(
    value: object,
    *,
    indent: bool = False,
    sort_keys: bool = False,
) -> bytes:
    """将对象序列化为 UTF-8 JSON 字节。"""
    option = orjson.OPT_NON_STR_KEYS
    if indent:
        option |= orjson.OPT_INDENT_2
    if sort_keys:
        option |= orjson.OPT_SORT_KEYS
    return orjson.dumps(value, option=option)


def loads(value: str | bytes | bytearray | memoryview) -> Any:
    """反序列化 JSON 字符串或字节载荷。"""
    return orjson.loads(value)
