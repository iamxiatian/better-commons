"""
=========================================================
 LLM 客户端封装 — ChatCompletionClient
=========================================================

封装了对 OpenAI 兼容 HTTP API（如 vLLM、DeepSeek API 等）的异步访问，
提供续写（completion）和多轮对话（chat）功能。

快速上手
--------

    from commons.llm_client import ModelType, create_chat_client

    client = create_chat_client(ModelType.DEEPSEEK_V4_FLASH, max_tokens=1024)
    chat_reply = await client.chat(user_prompt="你是一个助手", "介绍一下自己")
    print(chat_reply)


基础概念
--------

- **续写** (`complete`): 给定一段文本，让模型继续生成后续内容。
- **对话** (`chat`): 系统指令 + 用户输入，适用于问答场景。
- **多轮对话** (`chat_with_messages`): 传入完整的消息列表，支撑多轮上下文。
- **转发** (`forward`): 透传原始请求 / 响应，用于 API 网关代理场景。
- **工厂函数** (`create_client`): 从 ``openkb.config`` 中读取配置创建客户端。

修改历史
--------
2026-05-30: chat相关方法中设置seed和do_sample两个参数，提高可复现能力
2026-05-31: 将reponse_format_type修改为response_format，可以传入dict，方便支持结构化输出的复杂情况
2026-06-01: 设置enable_thinking=False
2026-06-22: 支持cache
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx
import structlog
from httpx import Timeout

from commons.conf import Config
from commons.json_codec import dumps, loads
from commons.llm_cache import LLMCache


logger = structlog.get_logger(__name__)


def _classify_status(
    message: str, error: Exception | None = None
) -> ChatStatus:
    """依据错误信息字符串进行对话状态的分类。"""
    # 合并所有可用的文本信息并转为小写，提高匹配成功率
    error_text = f"{message} {str(error) if error else ''}".lower()

    # 1. 匹配超时（网络层面）
    timeout_keywords = [
        "readtimeout",
        "timeout",
        "timed out",
        "connection reset",
        "connect fail",
        "超时",
    ]
    if any(kw in error_text for kw in timeout_keywords):
        return ChatStatus.TIMEOUT

    # 2. 匹配并发/限流（状态码或特定描述）
    rate_limit_keywords = [
        "rate limit",
        "too many requests",
        "concurrent",
        "too many requests",
        "request limit",
        "429",
        "限流",
        "并发",
    ]
    if any(kw in error_text for kw in rate_limit_keywords):
        return ChatStatus.RATE_LIMIT

    # 3. 匹配敏感内容（审核拦截）
    sensitive_keywords = [
        "inappropriate content",
        "content filter",
        "sensitive",
        "content policy",
        "violation",
        "illegal",
        "blocked",
        "敏感",
        "违规",
    ]
    if any(kw in error_text for kw in sensitive_keywords):
        return ChatStatus.SENSITIVE

    # 4. 兜底
    return ChatStatus.UNKNOWN


class ChatStatus(Enum):
    """对话状态，成功应为SUCCESS，其他则选择。"""

    SUCCESS = "success"  # 正常输出结果
    TIMEOUT = "timeout"  # 连接超时
    RATE_LIMIT = "rate_limit"  # 超过并发/频率限制
    SENSITIVE = "sensitive_content"  # 含有敏感内容
    UNKNOWN = "unknown"  # 未能识别的其他异常
    LENGTH_LIMIT = "length_limit"  # 超过了设置的最大长度（max tokens)


class ChatModel(Enum):
    """支持的模型类型。

    这些模型需要在配置项中对应具体的 ``llm.<name>.*``配置项，否则会读取不到导致异常
    """

    QWEN25_7B = "qwen25_7b"
    QWEN3_4B = "qwen3_4b"
    QWEN35_4B = "qwen35_4b"
    QWEN3_30B_A3B = "qwen3_30b_a3b"
    QWEN36_27B = "qwen36_27b"
    DEEPSEEK_V4_FLASH = "deepseek_v4_flash"
    EXTERNAL = "external"
    QWEN3_30B_A3B_LOCAL = "qwen3_30b_a3b_local"


@dataclass
class ChatReply:
    """大模型调用的返回结果。

    Attributes:
        response_data: 大模型返回的完整输出。成功时为响应体的 JSON 字符串，
            失败时为原始错误信息。
        status: 对话状态，参考 :class:`ChatStatus`。
        duration_ms: 本次 LLM 请求耗时（毫秒）；缓存命中时为原始请求耗时。
        cache_hit: 本次结果是否直接来自缓存。
    """

    response_data: str | None = None
    status: ChatStatus = ChatStatus.SUCCESS
    duration_ms: int = 0
    cache_hit: bool = False

    @property
    def text(self) -> str | None:
        """从 ``response_data`` 中提取主要文本内容。

        该属性为只读派生值，**不会写入数据库**：数据库仅保存 ``response_data``
        完整输出，需要文本时按需解析提取，以节省存储空间。解析失败时原样返回
        ``response_data``。
        """
        if not self.response_data:
            return None
        try:
            data = loads(self.response_data)
            if not isinstance(data, dict):
                return self.response_data
            choice = data["choices"][0]
            if "message" in choice:
                return str(choice["message"]["content"]).strip()
            return str(choice["text"]).strip()
        except (KeyError, IndexError, TypeError, ValueError):
            return self.response_data


def _elapsed_ms(start: float) -> int:
    """计算自 ``start``（perf_counter 时刻）以来经过的毫秒数。"""
    return int((perf_counter() - start) * 1000)


class ChatClient:
    """大语言模型对话客户端，支持续写和多轮对话。

    与 OpenAI-compatible HTTP API（如 vLLM、TGI、DeepSeek API）交互。

    Examples::

        >>> client = ChatCompletionClient("http://localhost:8000/v1", model="Qwen2.5-7B-Instruct")
        >>> # 续写
        >>> response = await client.complete("床前明月光")
        >>> # 简单对话
        >>> chat_reply = await client.chat(user_prompt="你好")
        >>> # 多轮对话
        >>> messages = [
        ...     {"role": "system", "content": "你是一个助手"},
        ...     {"role": "user", "content": "你好"},
        ...     {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
        ...     {"role": "user", "content": "今天天气如何？"},
        ... ]
        >>> chat_reply = await client.chat_with_messages(messages)
    """

    def __init__(
        self,
        api_base: str,
        model: str,
        *,
        authorization_name: str = "Authorization",
        authorization_key: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.00001,
        enable_thinking: bool = False,
        top_p: float = 1.0,
        n_choices: int = 1,
        repetition_penalty: float = 1.0,
        timeout: int = 60,
        request_headers: dict[str, str] | None = None,
        enable_cache: bool = False,
        cache_path: str = "./data/llm_cache.db",
    ) -> None:
        """初始化聊天机器人。

        Args:
            api_base: API 基础地址，例如 ``"http://localhost:8000/v1"``
            model: 模型名称
            authorization_name: 鉴权密钥在 HTTP 请求头中的名称，默认为 ``"Authorization"``
            authorization_key: 鉴权密钥值。为 ``None`` 时不添加鉴权头
            max_tokens: 单次生成的最大 token 数
            temperature: 温度参数，控制生成随机性
            enable_thinking: 是否启用思考模式
            top_p: 核采样（nucleus sampling）参数
            n_choices: 一次请求生成的候选回复数
            repetition_penalty: 重复惩罚系数
            timeout: 单次 HTTP 请求超时时间（秒）
            request_headers: 请求大模型时，传入的请求头，默认为None
            enable_cache: 是否启用 SQLite 响应缓存（默认关闭）
            cache_path: 启用缓存时，缓存文件的存放路径
        """
        base = api_base.rstrip("/")
        self.api_base = base
        self.completion_url = f"{base}/completions"
        self.chat_url = f"{base}/chat/completions"
        self.model = model
        self.authorization_name = authorization_name
        self.authorization_key = authorization_key

        self.max_tokens = max_tokens
        self.temperature = temperature
        self.thinking_enabled = enable_thinking
        self.top_p = top_p
        self.n_choices = n_choices
        self.repetition_penalty = repetition_penalty
        self.timeout = timeout
        self.cache_enabled = enable_cache
        self._cache: LLMCache | None = None
        if self.cache_enabled:
            db_path = Path(cache_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache = LLMCache.open(db_path)

        # HTTP 请求头
        self.request_headers: dict[str, str] = (
            {"Content-Type": "application/json"}
            if request_headers is None
            else request_headers
        )

        if self.authorization_key:
            self.request_headers[self.authorization_name] = (
                self.authorization_key
            )

    def _prepare_payload(self) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "n": self.n_choices,
            "best_of": self.n_choices,
            "use_beam_search": self.n_choices > 1,
            "repetition_penalty": self.repetition_penalty,
            "seed": 42,
            "do_sample": False,
            "stream": False,
        }

        if self.thinking_enabled:
            return payload  # 启用思考模式直接返回

        # 根据模型差异关闭思考模式
        if "deepseek" in self.model.lower():
            payload["thinking"] = {"type": "disabled"}
            payload["reasoning"] = {"effort": "none"}
        else:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    # ---- 续写 ----

    async def complete(
        self,
        prompt: str,
        *,
        use_beam_search: bool = False,
        skip_special_tokens: bool = True,
        trace_id: str | None = None,
    ) -> ChatReply:
        """续写文本：给定 ``prompt``，让模型继续生成后续内容。

        Args:
            prompt: 输入提示文本
            use_beam_search: 是否使用 beam search 搜索
            skip_special_tokens: 是否跳过输出中的特殊 token
            trace_id: 追踪id

        Returns:
            模型续写的文本内容

        Examples::

            >>> response = await client.complete("床前明月光")
            >>> response
            "，疑是地上霜。举头望明月，低头思故乡。"
        """
        payload = self._prepare_payload()
        payload["prompt"] = prompt
        payload["use_beam_search"] = use_beam_search
        payload["skip_special_tokens"] = skip_special_tokens

        return await self._cached_or_post(
            self.completion_url, payload, trace_id=trace_id
        )

    # ---- 对话 ----

    async def chat(
        self,
        *,
        user_prompt: str,
        system_prompt: str = "你是一个专业友好的AI助手，回答简洁准确，逻辑清晰，不编造虚假信息，如实回答不知道的内容。",
        skip_special_tokens: bool = True,
        response_format: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> ChatReply:
        """简单对话（系统指令 + 用户指令）。

        Args:
            system_prompt: 系统提示词，定义助手角色和行为
            user_prompt: 用户输入
            skip_special_tokens: 是否跳过输出中的特殊 token
            response_format: 返回格式要求，deepseek可参考
                https://api-docs.deepseek.com/zh-cn/guides/json_mode
            trace_id: 追踪id

        Returns:
            ``ChatReply`` 对象，包含 ``text``（输出内容）与 ``status``（对话状态）

        Examples::

            >>> reply = await client.chat(user_prompt="1+1等于多少？")
            >>> reply.text
            "1+1等于2。"
            >>> reply.status
            <ChatStatus.SUCCESS: 'success'>
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.chat_messages(
            messages=messages,
            skip_special_tokens=skip_special_tokens,
            response_format=response_format,
            trace_id=trace_id,
        )

    async def chat_messages(
        self,
        *,
        messages: list[dict[str, Any]],
        skip_special_tokens: bool = True,
        response_format: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> ChatReply:
        """多轮对话：传入完整的消息列表进行对话。

        Args:
            messages: 消息列表，每条消息包含 ``role`` 和 ``content`` 字段
            skip_special_tokens: 是否跳过输出中的特殊 token
            response_format: 返回格式

        Returns:
            ``ChatReply`` 对象，包含 ``text``（输出内容）与 ``status``（对话状态）

        Examples::

            >>> messages = [
            ...     {"role": "system", "content": "你是一个助手"},
            ...     {"role": "user", "content": "你好"},
            ...     {"role": "assistant", "content": "你好！"},
            ...     {"role": "user", "content": "你叫什么名字？"},
            ... ]
            >>> response = await client.chat_with_messages(messages)
            >>> response
            "我叫助手。"
        """
        payload = self._prepare_payload()
        payload["messages"] = messages
        payload["skip_special_tokens"] = skip_special_tokens
        if response_format:
            payload["response_format"] = response_format

        return await self._cached_or_post(self.chat_url, payload, trace_id)

    # ---- 底层请求 ----

    def _try_cache(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> tuple[str | None, tuple[str, ChatStatus, int] | None]:
        """返回 (cache_key, cached_text, cached_status, cached_duration_ms)；
        未启用或未命中时后三者均为 None。"""
        if not self.cache_enabled or self._cache is None:
            return None, None
        cache_key = self._cache.make_key(url, payload)
        cached = self._cache.get(cache_key)
        if cached is None:
            return cache_key, None
        data, status, duration_ms = cached
        return cache_key, (data, ChatStatus(status), duration_ms)

    async def _cached_or_post(
        self,
        url: str,
        payload: dict[str, Any],
        trace_id: str | None,
    ) -> ChatReply:
        """带缓存请求：命中返回缓存的 ``ChatReply``，未命中则请求并写入缓存。"""
        cache_key, cached_value = self._try_cache(url, payload)
        if cached_value is not None:
            cached_data, cached_status, cached_duration_ms = cached_value
            return ChatReply(
                response_data=cached_data,
                status=cached_status,
                duration_ms=cached_duration_ms,
                cache_hit=True,
            )
        chat_reply = await self._post_and_parse(url, payload, trace_id)
        # 只缓存成功或者提示有敏感信息的情况
        if chat_reply.status in (ChatStatus.SUCCESS, ChatStatus.SENSITIVE):
            self._store_cache(cache_key, url, payload, chat_reply)
        return chat_reply

    def _store_cache(
        self,
        cache_key: str | None,
        url: str,
        payload: dict[str, Any],
        chat_reply: ChatReply,
    ) -> None:
        if cache_key and self.cache_enabled and self._cache is not None:
            self._cache.put(
                cache_key,
                url=url,
                payload=payload,
                response_data=chat_reply.response_data or "",
                response_status=chat_reply.status.value,
                duration_ms=chat_reply.duration_ms,
                model=self.model,
            )

    async def _post_and_parse(
        self,
        url: str,
        payload: dict[str, Any],
        trace_id: str | None,
    ) -> ChatReply:
        start_time = perf_counter()
        async with httpx.AsyncClient(timeout=Timeout(self.timeout)) as client:
            response_data: Any = None
            try:
                response = await client.post(
                    url, headers=self.request_headers, json=payload
                )
                duration_ms = _elapsed_ms(start_time)
                logger.debug(f"response: {response}")
                response.raise_for_status()
                response_data = response.json()
                logger.debug(
                    f"LLM response：url={url}, model={self.model}, response={response_data}",
                    trace_id=trace_id,
                )

                chat_status = ChatStatus.SUCCESS
                if response_data["choices"][0].get("finish_reason") == "length":
                    chat_status = ChatStatus.LENGTH_LIMIT

                return ChatReply(
                    response_data=dumps(response_data, indent=False),
                    status=chat_status,
                    duration_ms=duration_ms,
                )
            except httpx.HTTPError as e:
                logger.error(
                    f"HTTP request failed, url: {url}", trace_id=trace_id
                )
                logger.error(
                    f"payload: {dumps(payload, indent=True)}",
                    trace_id=trace_id,
                )
                return ChatReply(
                    response_data=None,
                    status=_classify_status(str(e)),
                    duration_ms=_elapsed_ms(start_time),
                )
            except (KeyError, json.JSONDecodeError, TypeError) as e:
                error_message = "unknown error"
                if response_data is not None:
                    error_message = f"{response_data}"
                if isinstance(response_data, dict):
                    error = response_data.get("error")
                    if isinstance(error, dict) and error.get("message"):
                        error_message = str(error["message"])

                error_message = f"{e}{error_message}"
                if "limit" in error_message:
                    logger.error(
                        f"请求超过LLM API限制：{error_message}",
                        trace_id=trace_id,
                    )
                logger.error(
                    f"Failed to parse response: {error_message}",
                    trace_id=trace_id,
                )
                return ChatReply(
                    response_data=dumps(response_data, indent=False)
                    if isinstance(response_data, dict)
                    else None,
                    status=_classify_status(error_message),
                    duration_ms=_elapsed_ms(start_time),
                )

    async def forward(
        self,
        request_type: Literal["chat", "completions"],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], int]:
        """转发原始 HTTP 请求，透传模型的原始响应。

        用于 API 网关代理场景：外部请求到达魔方接口后，直接转发给底层 LLM。

        Args:
            request_type: 请求类型，``"chat"`` 或 ``"completions"``
            payload: 请求体数据

        Returns:
            ``(响应体 dict, HTTP 状态码)`` 的二元组
        """
        url = self.chat_url if request_type == "chat" else self.completion_url

        if "model" not in payload:
            logger.debug("模型未指定，使用默认模型：%s", self.model)
            payload["model"] = self.model
        elif payload["model"] != self.model:
            logger.warning(
                "传入模型 (%s) 与默认模型 (%s) 不一致，已切换为默认模型",
                payload["model"],
                self.model,
            )
            payload["model"] = self.model

        async with httpx.AsyncClient(timeout=Timeout(self.timeout)) as client:
            response = await client.post(
                url, headers=self.request_headers, json=payload
            )
            response.raise_for_status()

            data = response.json()
            logger.debug("LLM response received", url=url, model=self.model)

            return data, response.status_code


# =========================================================
# 工厂函数
# =========================================================
def create_chat_client(
    model_type: ChatModel,
    *,
    config: Config,
    max_tokens: int,
    timeout: int | None = None,
    request_headers: dict[str, str] | None = None,
    enable_thinking: bool | None = None,
    enable_cache: bool = False,
    cache_path: str = "./data/llm_cache.db",
) -> ChatClient:
    """从配置文件创建 ``ChatClient``。

    Args:
        model_type: 模型类型枚举值
        max_tokens: 单次生成的最大 token 数
        enable_thinking: 是否启用思考模式，如果没有设置，则从配置文件中读取
        enable_cache: 是否启用 SQLite 响应缓存（默认启用）
        request_headers: 请求头
    """
    llm_name = model_type.value
    auth_key = config.get_option_str(f"llm.{llm_name}.authorization_key")
    auth_name = (
        config.get_option_str(f"llm.{llm_name}.authorization_name")
        or "Authorization"
    )
    api_base = config.get_str(f"llm.{llm_name}.api.base")
    model = config.get_str(f"llm.{llm_name}.model.path")
    temperature = config.get_option_float("llm.default.temperature") or 0.00001

    if enable_thinking is None:
        thinking = config.get_option_bool(f"llm.{llm_name}.thinking") or False
    else:
        logger.info(
            f"使用用户指定的思考模式参数覆盖配置文件中的配置，enable_thinking={enable_thinking}"
        )
        thinking = enable_thinking

    top_p = config.get_option_float("llm.default.top_p") or 1.0
    repetition_penalty = (
        config.get_option_float("llm.default.repetition_penalty") or 1.0
    )
    n_choices = config.get_option_int("llm.default.n_choices") or 1
    # 如果函数参数指定了数值，则优先使用，否则用配置，否则是60
    timeout = timeout or config.get_option_int(f"llm.{llm_name}.timeout") or 60

    return ChatClient(
        api_base,
        model,
        authorization_name=auth_name,
        authorization_key=auth_key,
        max_tokens=max_tokens,
        temperature=temperature,
        enable_thinking=thinking,
        top_p=top_p,
        n_choices=n_choices,
        repetition_penalty=repetition_penalty,
        timeout=timeout,
        request_headers=request_headers,
        enable_cache=enable_cache,
        cache_path=cache_path,
    )
