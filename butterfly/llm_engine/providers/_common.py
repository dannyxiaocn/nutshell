from __future__ import annotations
import json
from typing import Any


def _parse_json_args(args_str: str) -> dict[str, Any]:
    """Safely parse a JSON string into a dict; return {} on any failure."""
    if not args_str:
        return {}
    try:
        parsed = json.loads(args_str)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
