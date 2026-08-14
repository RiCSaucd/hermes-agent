"""Agent-facing Firecrawl Interact tool.

Single multi-action tool (``firecrawl_interact``) to keep schema footprint
small. Gated by ``check_interact_available`` — zero cost when Firecrawl is
not configured.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.web.firecrawl import interact as fc_interact

FIRECRAWL_INTERACT_SCHEMA: Dict[str, Any] = {
    "name": "firecrawl_interact",
    "description": (
        "Drive a Firecrawl scrape-bound browser session for logins, form fills, "
        "and multi-step page flows. Actions: start (scrape URL → scrape_id), "
        "act (natural-language prompt and/or Playwright code on that session), "
        "stop (end session — always call when done), run (one-shot "
        "start→act→stop). Sessions persist between act calls. Optional "
        "profile_name persists cookies across runs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "act", "stop", "run"],
                "description": (
                    "start: open a scrape session. act: prompt/code on scrape_id. "
                    "stop: end the session. run: one-shot start+act+stop."
                ),
            },
            "url": {
                "type": "string",
                "description": "Target URL (required for start and run).",
            },
            "scrape_id": {
                "type": "string",
                "description": "Scrape session id from start (required for act and stop).",
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Natural-language browser instruction, e.g. "
                    "'Click login and fill email with test@example.com'."
                ),
            },
            "code": {
                "type": "string",
                "description": (
                    "Playwright code to run in the session. `page` is available "
                    "globally. Prefer for precise selectors; use prompt for open-ended flows."
                ),
            },
            "language": {
                "type": "string",
                "enum": ["node", "python", "bash"],
                "description": "Language for code execution (default: node).",
            },
            "profile_name": {
                "type": "string",
                "description": (
                    "Named Firecrawl browser profile to load/save cookies and "
                    "localStorage (login reuse)."
                ),
            },
            "profile_save_changes": {
                "type": "boolean",
                "description": (
                    "When using profile_name, save session changes back to the "
                    "profile (default true on start/run when profile_name is set)."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "Interact execution timeout in seconds (1-300).",
            },
            "stop_after": {
                "type": "boolean",
                "description": "For action=run only: stop the session after act (default true).",
            },
        },
        "required": ["action"],
    },
}


def check_interact_requirements() -> bool:
    return fc_interact.check_interact_available()


def handle_firecrawl_interact(args: Dict[str, Any], **kwargs: Any) -> str:
    """Dispatch ``firecrawl_interact`` actions; always returns a JSON string."""
    del kwargs  # unused — registry passes task_id etc.
    action = (args.get("action") or "").strip().lower()

    try:
        if action == "start":
            result = fc_interact.start_session(
                args.get("url") or "",
                profile_name=args.get("profile_name"),
                profile_save_changes=args.get("profile_save_changes"),
            )
        elif action == "act":
            result = fc_interact.act(
                args.get("scrape_id") or "",
                prompt=args.get("prompt"),
                code=args.get("code"),
                language=args.get("language") or "node",
                timeout=args.get("timeout"),
            )
        elif action == "stop":
            result = fc_interact.stop_session(args.get("scrape_id") or "")
        elif action == "run":
            stop_after = args.get("stop_after")
            result = fc_interact.run_flow(
                args.get("url") or "",
                prompt=args.get("prompt"),
                code=args.get("code"),
                language=args.get("language") or "node",
                profile_name=args.get("profile_name"),
                profile_save_changes=args.get("profile_save_changes"),
                timeout=args.get("timeout"),
                stop=True if stop_after is None else bool(stop_after),
            )
        else:
            result = {
                "success": False,
                "error": "action must be one of: start, act, stop, run",
            }
    except Exception as exc:  # noqa: BLE001 — surface to the agent as JSON
        result = {"success": False, "error": f"firecrawl_interact failed: {exc}"}

    return json.dumps(result)
