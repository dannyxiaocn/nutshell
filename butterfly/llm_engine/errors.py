"""Normalized error taxonomy for LLM providers.

Provider implementations should raise these when the underlying API returns
a recognizable error class. This gives callers (session loop, retry wrappers,
UI) a single `except` tree instead of distinguishing provider-specific types.
"""
from __future__ import annotations


class ProviderError(RuntimeError):
    """Base for all provider-side failures.

    ``str(exc)`` renders ``provider`` and ``status`` alongside the message so
    logs carry full context without callers having to inspect attributes.
    """

    def __init__(self, message: str, *, provider: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status = status

    def __str__(self) -> str:  # noqa: D401
        parts = [self.message]
        tags: list[str] = []
        if self.provider:
            tags.append(f"provider={self.provider}")
        if self.status is not None:
            tags.append(f"status={self.status}")
        if tags:
            parts.append(f"[{' '.join(tags)}]")
        return " ".join(parts)

    def __repr__(self) -> str:  # noqa: D401
        return (
            f"{type(self).__name__}("
            f"{self.message!r}, provider={self.provider!r}, status={self.status!r})"
        )


class AuthError(ProviderError):
    """401/403 — invalid or expired credentials."""


class RateLimitError(ProviderError):
    """429 — quota or rate limit exceeded. May carry a retry_after hint."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        status: int | None = 429,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, provider=provider, status=status)
        self.retry_after = retry_after

    def __str__(self) -> str:  # noqa: D401
        base = super().__str__()
        if self.retry_after is not None:
            return f"{base} [retry_after={self.retry_after}s]"
        return base


class ContextWindowExceededError(ProviderError):
    """Input (or input+output) exceeded the model's context window."""


class ProviderTimeoutError(ProviderError):
    """Request timed out client-side or server-side.

    Renamed from ``TimeoutError`` (shadowed the builtin) in v2.0.4; callers
    that relied on ``isinstance(exc, TimeoutError)`` against the builtin are
    not affected — the old class only shadowed our own name.
    """


class ServerError(ProviderError):
    """5xx / transient server-side failure."""


class BadRequestError(ProviderError):
    """400 — malformed request. Not retryable."""


__all__ = [
    "ProviderError",
    "AuthError",
    "RateLimitError",
    "ContextWindowExceededError",
    "ProviderTimeoutError",
    "ServerError",
    "BadRequestError",
]
