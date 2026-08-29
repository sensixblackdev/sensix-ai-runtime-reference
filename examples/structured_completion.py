"""Bounded JSON recovery for OpenAI-compatible Chat Completions responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from docker.gateway.json_guard import validate_or_repair


async def require_json(
    message: str,
    schema: type[BaseModel],
    regenerate: Callable[[str], Awaitable[str]],
) -> dict:
    """Parse model output, allowing exactly one bounded repair attempt."""
    return await validate_or_repair(message, schema, regenerate)


REPAIR_PROMPT = """Your last response was not valid JSON. Return only a JSON object
that matches the requested schema. Do not add markdown fences or commentary."""
