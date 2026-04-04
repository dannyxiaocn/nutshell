from __future__ import annotations
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from nutshell.core.types import AgentResult

# Hook type aliases for Agent.run() extension points.
# All hooks are optional (None = no-op). All are synchronous callables.

OnTextChunk = Callable[[str], None]             # streamed text fragment
OnToolCall  = Callable[[str, dict], None]        # (name, input)          — before execution
OnToolDone  = Callable[[str, dict, str], None]   # (name, input, result)  — after execution
OnLoopStart = Callable[[str], None]              # (input)                — before loop begins
OnLoopEnd   = Callable[["AgentResult"], None]    # (result)               — after loop ends
