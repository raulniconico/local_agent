"""Thin per-provider chat completion calls.

This is a stateless pass-through proxy, not an agent: no tool-calling loop,
no conversation memory kept server-side -- each request carries its own full
message history (or a single prompt) and gets one response back. That's
deliberately unlike the sibling ../app/graph.py ReAct agent, which is a
different kind of thing (a local tool-using assistant) built on LangChain.
Talking to provider SDKs directly here avoids pulling in LangChain/LangGraph
for a job that's just "send messages, get text back".
"""

from typing import Optional

import config
from schemas import ChatMessage


class ProviderNotConfiguredError(Exception):
    """Raised when the requested provider has no API key set on this server."""


class ProviderRequestError(Exception):
    """Wraps any upstream SDK/HTTP error so main.py can return a clean 502."""


def _to_pairs(messages: Optional[list[ChatMessage]], prompt: Optional[str]) -> list[dict]:
    if messages is not None:
        return [{"role": m.role, "content": m.content} for m in messages]
    return [{"role": "user", "content": prompt}]


def _split_leading_system(pairs: list[dict], system: Optional[str]) -> tuple[Optional[str], list[dict]]:
    """Anthropic takes `system` as its own field and rejects a "system" role
    inside `messages` -- so if the caller sent an OpenAI-style messages list
    with a leading system message, pull it out instead of erroring."""
    if pairs and pairs[0]["role"] == "system":
        return system or pairs[0]["content"], pairs[1:]
    return system, pairs


def call_anthropic(
    *,
    messages: Optional[list[ChatMessage]],
    prompt: Optional[str],
    system: Optional[str],
    model: Optional[str],
    max_tokens: Optional[int],
) -> tuple[str, str]:
    if not config.ANTHROPIC_API_KEY:
        raise ProviderNotConfiguredError("anthropic is not configured on this server")

    from anthropic import Anthropic

    resolved_system, pairs = _split_leading_system(_to_pairs(messages, prompt), system)
    resolved_model = model or config.ANTHROPIC_MODEL

    # No temperature/top_p: Claude Opus 5 rejects sampling parameters with a 400.
    kwargs = {
        "model": resolved_model,
        "max_tokens": max_tokens or config.ANTHROPIC_MAX_TOKENS,
        "messages": pairs,
    }
    if resolved_system:
        kwargs["system"] = resolved_system

    try:
        response = Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see ProviderRequestError's docstring
        raise ProviderRequestError(str(exc)) from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    return resolved_model, text


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    default_model: str,
    default_max_tokens: int,
    provider_label: str,
    messages: Optional[list[ChatMessage]],
    prompt: Optional[str],
    system: Optional[str],
    model: Optional[str],
    max_tokens: Optional[int],
) -> tuple[str, str]:
    if not api_key:
        raise ProviderNotConfiguredError(f"{provider_label} is not configured on this server")

    from openai import OpenAI

    pairs = _to_pairs(messages, prompt)
    if system and not (pairs and pairs[0]["role"] == "system"):
        pairs = [{"role": "system", "content": system}] + pairs
    resolved_model = model or default_model

    try:
        response = OpenAI(api_key=api_key, base_url=base_url).chat.completions.create(
            model=resolved_model,
            max_tokens=max_tokens or default_max_tokens,
            messages=pairs,
        )
    except Exception as exc:  # noqa: BLE001
        raise ProviderRequestError(str(exc)) from exc

    return resolved_model, response.choices[0].message.content or ""


def call_qwen(**kwargs) -> tuple[str, str]:
    return _call_openai_compatible(
        api_key=config.QWEN_API_KEY,
        base_url=config.QWEN_BASE_URL,
        default_model=config.QWEN_MODEL,
        default_max_tokens=config.QWEN_MAX_TOKENS,
        provider_label="qwen",
        **kwargs,
    )


def call_deepseek(**kwargs) -> tuple[str, str]:
    return _call_openai_compatible(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        default_model=config.DEEPSEEK_MODEL,
        default_max_tokens=config.DEEPSEEK_MAX_TOKENS,
        provider_label="deepseek",
        **kwargs,
    )


_PROVIDER_CALLS = {
    "anthropic": call_anthropic,
    "qwen": call_qwen,
    "deepseek": call_deepseek,
}


def ask(
    provider: str,
    *,
    messages: Optional[list[ChatMessage]],
    prompt: Optional[str],
    system: Optional[str],
    model: Optional[str],
    max_tokens: Optional[int],
) -> tuple[str, str]:
    """Returns (resolved_model, response_text). `provider` is assumed already
    validated against the Literal in schemas.AskRequest."""
    return _PROVIDER_CALLS[provider](
        messages=messages, prompt=prompt, system=system, model=model, max_tokens=max_tokens
    )
