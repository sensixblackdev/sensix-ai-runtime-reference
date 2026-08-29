"""Bounded JSON validation and a single, explicit repair pass."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ValidationError


class JsonRepairError(ValueError):
    """Returned when a structured response is still invalid after one repair."""


async def validate_or_repair(
    raw: str,
    schema: type[BaseModel],
    regenerate: Callable[[str], Awaitable[str]],
) -> dict[str, Any]:
    """Parse schema output and ask the model for exactly one corrective response.

    `regenerate` must use temperature 0 and a strict JSON schema. Never pass secrets,
    tool output, or an unbounded raw response into the repair prompt.
    """
    try:
        return schema.model_validate(json.loads(raw)).model_dump(mode="json")
    except (json.JSONDecodeError, ValidationError) as first_error:
        excerpt = raw[:16_000]
        repair_instruction = (
            "Return only valid JSON matching the requested schema. Do not use markdown. "
            f"Validation error: {str(first_error)[:800]}. Candidate JSON: {excerpt}"
        )
        repaired = await regenerate(repair_instruction)
        try:
            return schema.model_validate(json.loads(repaired)).model_dump(mode="json")
        except (json.JSONDecodeError, ValidationError) as second_error:
            raise JsonRepairError("structured output remained invalid after one repair") from second_error
