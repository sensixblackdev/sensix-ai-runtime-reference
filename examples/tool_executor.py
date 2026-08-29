"""Minimal local-tool executor for an OpenAI tool-call loop.

Keep this process private to the operator's machine/pod.  The model sees only
tool schemas and sanitized tool results; it never receives environment values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1] / "workspace"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_workspace_files",
            "description": "List non-secret files under the configured workspace.",
            "parameters": {
                "type": "object",
                "properties": {"suffix": {"type": "string", "description": "Optional filename suffix, e.g. .py"}},
                "additionalProperties": False,
            },
        },
    }
]


def execute(name: str, arguments: str) -> dict[str, Any]:
    """Return a bounded, scrubbed result. Never interpolate into a shell command."""
    if name != "list_workspace_files":
        return {"ok": False, "error": "unsupported_tool"}

    try:
        suffix = str(json.loads(arguments or "{}").get("suffix", ""))
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_arguments"}

    if not WORKSPACE.exists():
        return {"ok": False, "error": "workspace_not_found"}

    blocked = {".env", ".pem", ".key"}
    files = [
        path.relative_to(WORKSPACE).as_posix()
        for path in WORKSPACE.rglob("*")
        if path.is_file() and not any(path.name.endswith(extension) for extension in blocked)
        and (not suffix or path.name.endswith(suffix))
    ]
    return {"ok": True, "files": files[:100], "truncated": len(files) > 100}
