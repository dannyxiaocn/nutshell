from __future__ import annotations
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from butterfly.core.types import AgentResult, TokenUsage

# Hook type aliases for Agent.run() extension points.
# All hooks are optional (None = no-op). All are synchronous callables.

OnTextChunk = Callable[[str], None]             # streamed text fragment (assistant text only; NEVER thinking)
# (name, input, tool_use_id) — before execution. v2.0.19 added tool_use_id
# as the 3rd arg so Session can pair tool_call/tool_done across concurrent
# gather()'d calls (same tool invoked twice in one iteration). External hooks
# registered via ``Session(on_tool_call=...)`` are still invoked with 2 args
# for back-compat; this signature describes the internal Agent→hook contract
# that composed Session callbacks receive.
OnToolCall  = Callable[[str, dict, str], None]
# (name, input, result, tool_use_id)    — after execution (see OnToolCall note)
OnToolDone  = Callable[[str, dict, str, str], None]
OnLoopStart = Callable[[str], None]              # (input)                — before loop begins
OnLoopEnd   = Callable[["AgentResult"], None]    # (result)               — after loop ends

# Per-LLM-call hook (v2.0.19). Fires once per completed ``provider.complete()``
# inside the Agent loop, AFTER ``total_usage += turn_usage``. Carries the usage
# of the single call just finished plus wall-clock duration so HUD can compute
# current context size (input + cache_read + cache_write + output) and tokens/s
# (output / duration). ``iteration`` is 1-based and matches the iteration count
# the loop reports at ``loop_end``.
#
#   on_llm_call_end(usage, duration_ms, iteration)
OnLLMCallEnd = Callable[["TokenUsage", int, int], None]

# Thinking block lifecycle. Providers call these when a thinking / reasoning
# block opens and closes. We do NOT stream thinking deltas to the UI (per
# v2.0.9 UX requirement: thinking renders as a tool-like cell that shows
# ``Thinking…`` while running and the collected body on close). Providers are
# responsible for internally buffering deltas until on_thinking_end fires.
#
#   on_thinking_start()           — a new thinking block has begun
#   on_thinking_end(text)         — block closed; ``text`` is the full body
#                                   (may be empty when the provider returns
#                                   encrypted / opaque reasoning — the UI still
#                                   shows the "thought for Xs" pill).
OnThinkingStart = Callable[[], None]
OnThinkingEnd   = Callable[[str], None]
