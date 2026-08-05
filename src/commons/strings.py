"""
=========================================================
字符串处理工具
=========================================================

提供跨模块复用的轻量字符串清理函数。

修改历史
--------
2026-07-05: 新增 Markdown 行内标记清理工具
"""

from __future__ import annotations

import re


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_UNDER = re.compile(r"_(.+?)_")
_MD_CODE = re.compile(r"`(.+?)`")


def remove_leading_whitespace(multi_line_str: str) -> str:
    """删除每一行开始的空白。
    Examples:
    >>> remove_leading_whitespace("  a\n  b\n c")
    "a\nb\nc"
    """
    lines = multi_line_str.splitlines()
    stripped_lines = [line.lstrip() for line in lines]
    return "\n".join(stripped_lines)


def strip_markdown_inline(text: str) -> str:
    """去掉常见行内 Markdown 强调/代码标记。"""
    cleaned = text.strip()
    for _ in range(4):
        previous = cleaned
        cleaned = _MD_BOLD.sub(r"\1", cleaned)
        cleaned = _MD_ITALIC.sub(r"\1", cleaned)
        cleaned = _MD_UNDER.sub(r"\1", cleaned)
        cleaned = _MD_CODE.sub(r"\1", cleaned)
        if cleaned == previous:
            break
    return cleaned.strip("*_` ")
