"""
=========================================================
大模型输出结果的 JSON 字符串解析器
=========================================================

从大模型输出中提取 JSON 块并解析为 Python 对象。若原始输出不符合 JSON 语法，则调用大模型
对文本进行修复，然后再次解析。

修改历史
--------
2026-08-04: 修正包内导入路径
"""

import re
from typing import Any

import orjson
import structlog

from commons.json_codec import loads
from commons.llm_client import ChatClient


logger = structlog.get_logger(__name__)


def _extract_first_json_structure(text: str) -> str | None:  # noqa: C901
    """尝试从文本中提取第一个完整的 JSON 对象或数组。

    通过括号匹配定位 JSON 结构的起始（{ 或 [）和结束位置。
    注意：此方法基于简单的括号计数，可能无法处理字符串内包含括号等复杂情况，
    但对于常见的 LLM 输出场景足够有效。

    Args:
        text: 待提取的原始文本

    Returns:
        提取出的 JSON 文本字符串，若未找到有效结构则返回 None。
    """
    # 寻找第一个 '{' 或 '['
    start_idx = -1
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            start_idx = i
            break

    if start_idx == -1:
        return None

    # 括号计数，找到匹配的结束位置
    stack: list[str] = []
    end_idx = None
    for i, ch in enumerate(text[start_idx:], start=start_idx):
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
        if not stack:
            end_idx = i + 1  # 包含结束字符
            break

    if end_idx is None:
        return None

    return text[start_idx:end_idx].strip()


def _extract_json_text(raw_output: str) -> str:
    """从 LLM 原始输出中提取 JSON 文本。

    处理以下情况：
    - 被 Markdown 代码块包裹（```json ... ``` 或 ``` ... ```）
    - 未被包裹但包含 JSON 片段（尝试提取第一个完整的 JSON 对象/数组）

    Args:
        raw_output: 大模型的原始输出字符串

    Returns:
        提取出的 JSON 文本字符串。若未找到有效 JSON，返回原始字符串的清理版本。
    """
    text = raw_output.strip()
    if not text:
        return "[]"

    # 1. 优先处理 Markdown 代码块
    code_block_pattern = r"```(?:json)?\s*\n(.*?)\n```"
    match = re.search(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 2. 尝试提取第一个完整的 JSON 结构（降低圈复杂度：调用独立函数）
    json_candidate = _extract_first_json_structure(text)
    if json_candidate is not None:
        return json_candidate

    # 3. 降级：返回清理后的原始文本（移除注释行等）
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "//")):
            lines.append(line)
    return "\n".join(lines).strip()


async def parse(
    llm_client: ChatClient, raw_output: str, fix_attempts: int = 1
) -> Any:
    """解析大模型输出为 JSON 对象。

    先尝试直接提取并解析；若失败，则使用 LLM 修复输出（最多重试 `fix_attempts` 次），
    再提取解析。若最终仍失败，抛出 `ValueError`。

    Args:
        llm_client: 支持异步 `chat` 方法的大模型客户端
        raw_output: 待解析的原始文本
        fix_attempts: 修复重试次数（默认为 1，若为 0 则禁止修复）

    Returns:
        解析得到的 Python 对象（字典或列表）

    Raises:
        ValueError: 当原始输出无法解析且修复失败时抛出
    """
    # 第一次尝试：直接提取并解析
    try:
        json_text = _extract_json_text(raw_output)
        return loads(json_text)
    except orjson.JSONDecodeError as e:
        logger.warning(
            "Initial JSON parsing failed",
            error=str(e),
            raw_snippet=raw_output[:200],
        )

    # 准备修复提示
    system_prompt = (
        "You are a JSON formatting assistant. "
        "The user will provide a text that contains a malformed JSON. "
        "Your task is to fix the JSON syntax errors and output ONLY the corrected JSON. "
        "Do NOT include any explanations, markdown formatting, or additional text. "
        "Ensure the output is a valid JSON object or array."
    )

    current_output = raw_output
    for attempt in range(fix_attempts):
        logger.info(
            "Attempting JSON repair via LLM",
            attempt=attempt + 1,
            max_attempts=fix_attempts,
        )
        try:
            # 调用大模型修复
            repaired_output = await llm_client.chat(
                system_prompt=system_prompt, user_prompt=current_output
            )
            # chat 返回 ChatReply；修复失败（text 为 None）时保留原文本以便下次重试
            current_output = repaired_output.text or current_output
            # 提取修复后的 JSON 文本
            json_text = _extract_json_text(current_output)
            result = loads(json_text)
            logger.info("Successfully repaired JSON", attempt=attempt + 1)
            return result
        except orjson.JSONDecodeError as e:
            logger.error(
                "Repaired output still invalid JSON",
                attempt=attempt + 1,
                error=str(e),
                repaired_snippet=current_output[:200],
            )

    # 重复修正失败，抛出异常
    raise ValueError("Unable to parse or repair JSON output")
