from __future__ import annotations
import inspect
from typing import Any, Callable, get_type_hints


_BACKGROUNDABLE_DESC_SUFFIX = (
    "\n\nThis tool supports non-blocking execution. Set `run_in_background=true` "
    "to start the call and receive a placeholder result immediately; the real "
    "output arrives later as a notification in your context, and you can fetch "
    "it anytime with `tool_output(task_id=...)`. A stall watchdog notifies you "
    "if no output appears for 5 minutes. Progress and status are also visible "
    "in the session panel."
)


def _python_type_to_json_schema(annotation: Any) -> dict:
    """Convert a Python type annotation to a JSON Schema type."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return {"type": "string"}
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # Handle Optional[X] -> {"type": X_type}
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json_schema(non_none[0])
    mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    return mapping.get(annotation, {"type": "string"})


def _build_schema_from_func(func: Callable) -> dict:
    """Build a JSON Schema object from a function's type annotations."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    props: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        props[name] = _python_type_to_json_schema(hints.get(name))
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def _inject_backgroundable_fields(schema: dict) -> dict:
    """Add run_in_background + polling_interval to a tool's schema."""
    merged = dict(schema)
    props = dict(merged.get("properties", {}))
    props["run_in_background"] = {
        "type": "boolean",
        "description": (
            "If true, the tool starts and returns a placeholder result with a "
            "task_id immediately; full output is delivered later. Use for "
            "commands expected to run > 30s, or when you want to continue "
            "working while it runs."
        ),
    }
    props["polling_interval"] = {
        "type": ["integer", "null"],
        "description": (
            "Optional. Seconds between heartbeat deliveries of incremental "
            "(delta) output while the task runs. Omit to use stall-watchdog "
            "only (recommended default)."
        ),
    }
    merged["properties"] = props
    # Not required — both default to not-set.
    return merged


class Tool:
    """An external action that an agent can call."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        schema: dict | None = None,
        backgroundable: bool = False,
    ) -> None:
        self.name = name
        self.backgroundable = backgroundable
        base_schema = schema or _build_schema_from_func(func)
        if backgroundable:
            self.schema = _inject_backgroundable_fields(base_schema)
            self.description = description + _BACKGROUNDABLE_DESC_SUFFIX
        else:
            self.schema = base_schema
            self.description = description
        self._func = func

    async def execute(self, **kwargs: Any) -> str:
        result = self._func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return str(result)

    def to_api_dict(self) -> dict:
        """Format for LLM API tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema,
        }


def tool(
    name: str | None = None,
    description: str | None = None,
    schema: dict | None = None,
    backgroundable: bool = False,
) -> Callable:
    """Decorator to define a Tool from a function.

    Usage:
        @tool(description="Search the web for a query")
        async def search(query: str) -> str:
            return "results..."

        @tool  # also works without parentheses
        def add(a: int, b: int) -> int:
            return a + b
    """
    def decorator(func: Callable) -> Tool:
        _name = name or func.__name__
        _desc = description or (inspect.getdoc(func) or _name)
        return Tool(
            name=_name,
            description=_desc,
            func=func,
            schema=schema,
            backgroundable=backgroundable,
        )

    # Support @tool without parentheses
    if callable(name):
        func, name = name, None
        return decorator(func)

    return decorator
