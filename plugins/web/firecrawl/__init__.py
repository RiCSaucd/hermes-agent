"""Firecrawl web search + extract + Interact plugin — bundled, auto-loaded.

Largest single plugin in this PR. Captures everything the previous
inline implementation in tools/web_tools.py did:

  - Lazy import of the firecrawl SDK (~200ms cold-start cost) via a
    callable proxy that defers the actual import to first use.
  - Dual client paths: direct (FIRECRAWL_API_KEY / FIRECRAWL_API_URL)
    OR Nous-hosted tool-gateway routing for subscribers, with
    web.use_gateway as the tie-breaker.
  - Per-URL scrape loop with 60s timeout, SSRF re-check after redirect,
    website-policy gating, and format-aware content selection.
  - Robust response shape normalization across SDK / direct API /
    gateway variants (search returns differ by transport).
  - Interact (scrape → prompt/Playwright → stop) for login/form flows,
    exposed as the ``firecrawl_interact`` tool and ``hermes firecrawl`` CLI.

The plugin re-exports ``Firecrawl`` (the lazy proxy) and
``check_firecrawl_api_key`` for backward-compatibility with tests and
external code that imports those names from ``tools.web_tools``.
"""

from __future__ import annotations

from pathlib import Path

from plugins.web.firecrawl.cli import firecrawl_command, register_cli as _register_firecrawl_cli
from plugins.web.firecrawl.provider import FirecrawlWebSearchProvider
from plugins.web.firecrawl.tools import (
    FIRECRAWL_INTERACT_SCHEMA,
    check_interact_requirements,
    handle_firecrawl_interact,
)

_SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"


def register(ctx) -> None:
    """Register the Firecrawl provider, Interact tool, CLI, and skill."""
    ctx.register_web_search_provider(FirecrawlWebSearchProvider())

    ctx.register_tool(
        name="firecrawl_interact",
        toolset="firecrawl_interact",
        schema=FIRECRAWL_INTERACT_SCHEMA,
        handler=handle_firecrawl_interact,
        check_fn=check_interact_requirements,
        emoji="🕸️",
        description=(
            "Firecrawl Interact — scrape-bound browser sessions for logins, "
            "forms, and multi-step flows (prompt or Playwright)."
        ),
    )

    ctx.register_cli_command(
        name="firecrawl",
        help="Firecrawl Interact (scrape, interact, stop, run)",
        setup_fn=_register_firecrawl_cli,
        handler_fn=firecrawl_command,
        description=(
            "Drive Firecrawl scrape-bound browser sessions: login flows, "
            "form fills, Playwright code, and named profiles. "
            "See: hermes firecrawl scrape --help"
        ),
    )

    if _SKILL_PATH.exists():
        ctx.register_skill(
            name="firecrawl-interact",
            path=_SKILL_PATH,
            description="Drive scrape sessions for logins and form fills.",
        )
