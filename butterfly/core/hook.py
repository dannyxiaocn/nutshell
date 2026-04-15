from __future__ import annotations
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from butterfly.core.types import AgentResult

# Hook type aliases for Agent.run() extension points.
# All hooks are optional (None = no-op). All are synchronous callables.

OnTextChunk = Callable[[str], None]             # streamed text fragment (assistant text only; NEVER thinking)
OnToolCall  = Callable[[str, dict], None]        # (name, input)          — before execution
OnToolDone  = Callable[[str, dict, str], None]   # (name, input, result)  — after execution
OnLoopStart = Callable[[str], None]              # (input)                — before loop begins
OnLoopEnd   = Callable[["AgentResult"], None]    # (result)               — after loop ends

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
