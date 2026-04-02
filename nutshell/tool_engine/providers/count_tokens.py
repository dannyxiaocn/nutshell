from __future__ import annotations

import asyncio
import os


def _estimate_tokens(text: str, ratio: float) -> int:
    return max(1 if text else 0, round(len(text) / ratio))


def _is_claude_model(model: str) -> bool:
    m = (model or '').lower()
    return 'claude' in m or 'anthropic' in m


def _is_openai_model(model: str) -> bool:
    m = (model or '').lower()
    return (
        m.startswith('gpt')
        or m.startswith('o1')
        or m.startswith('o3')
        or m.startswith('o4')
        or 'openai' in m
    )


def _is_kimi_model(model: str) -> bool:
    m = (model or '').lower()
    return 'kimi' in m or 'moonshot' in m


def _count_claude_tokens_sync(text: str, model: str) -> int:
    try:
        import anthropic  # type: ignore
    except Exception as exc:
        raise RuntimeError(f'anthropic import unavailable: {exc}') from exc

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set')

    client = anthropic.Anthropic(api_key=api_key)

    beta_messages = getattr(getattr(client, 'beta', None), 'messages', None)
    if beta_messages is not None and hasattr(beta_messages, 'count_tokens'):
        resp = beta_messages.count_tokens(
            model=model,
            messages=[{'role': 'user', 'content': text}],
        )
        count = getattr(resp, 'input_tokens', None)
        if isinstance(count, int):
            return count

    if hasattr(client, 'count_tokens'):
        count = client.count_tokens(text)
        if isinstance(count, int):
            return count

    raise RuntimeError('anthropic tokenizer API unavailable')


def _count_openai_tokens_sync(text: str, model: str) -> int:
    try:
        import tiktoken  # type: ignore
    except Exception as exc:
        raise RuntimeError(f'tiktoken import unavailable: {exc}') from exc

    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding('cl100k_base')
    return len(encoding.encode(text))


async def count_tokens(text: str, model: str = 'claude-sonnet-4-6') -> str:
    char_count = len(text)
    token_count: int
    method = 'estimated'

    if _is_claude_model(model):
        try:
            token_count = await asyncio.to_thread(_count_claude_tokens_sync, text, model)
            method = 'exact'
        except Exception:
            token_count = _estimate_tokens(text, 4.0)
    elif _is_openai_model(model):
        try:
            token_count = await asyncio.to_thread(_count_openai_tokens_sync, text, model)
            method = 'exact'
        except Exception:
            token_count = _estimate_tokens(text, 4.0)
    elif _is_kimi_model(model):
        token_count = _estimate_tokens(text, 3.5)
    else:
        token_count = _estimate_tokens(text, 4.0)

    suffix = '' if method == 'exact' else ' (estimated)'
    return f'text: {char_count} chars → {token_count} tokens{suffix} (model: {model})'
