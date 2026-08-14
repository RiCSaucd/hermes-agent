"""CLI for Firecrawl Interact — ``hermes firecrawl <subcommand>``.

Subcommands:
  scrape <url>     — start a scrape-bound session (prints scrape_id)
  interact <id>    — run --prompt and/or --code on that session
  stop <id>        — end the session
  run <url>        — one-shot scrape → interact → stop (login/form flows)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from plugins.web.firecrawl import interact as fc_interact


def register_cli(subparser: argparse.ArgumentParser) -> None:
    """Build the ``hermes firecrawl`` argparse tree."""
    subs = subparser.add_subparsers(dest="firecrawl_command")

    scrape_p = subs.add_parser(
        "scrape",
        help="Scrape a URL and open an Interact session (prints scrape_id)",
    )
    scrape_p.add_argument("url", help="https://… page to open")
    scrape_p.add_argument(
        "--profile",
        dest="profile_name",
        default=None,
        help="Named browser profile for persistent cookies/localStorage",
    )
    scrape_p.add_argument(
        "--save-changes",
        dest="profile_save_changes",
        action="store_true",
        default=None,
        help="Save profile changes after this session (use with --profile)",
    )
    scrape_p.add_argument(
        "--no-save-changes",
        dest="profile_save_changes",
        action="store_false",
        help="Load profile without writing changes back",
    )
    scrape_p.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result",
    )

    interact_p = subs.add_parser(
        "interact",
        help="Run a prompt and/or Playwright code on a scrape session",
    )
    interact_p.add_argument("scrape_id", help="scrape_id from `hermes firecrawl scrape`")
    interact_p.add_argument(
        "--prompt",
        default=None,
        help="Natural-language instruction (e.g. fill login form)",
    )
    interact_p.add_argument(
        "--code",
        default=None,
        help="Playwright code (`page` is global). Prefer for precise selectors.",
    )
    interact_p.add_argument(
        "--code-file",
        default=None,
        help="Read Playwright code from a file",
    )
    interact_p.add_argument(
        "--language",
        choices=("node", "python", "bash"),
        default="node",
        help="Code language (default: node)",
    )
    interact_p.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Execution timeout in seconds (1-300)",
    )
    interact_p.add_argument("--json", action="store_true", help="Print full JSON result")

    stop_p = subs.add_parser("stop", help="Stop an Interact session (end billing)")
    stop_p.add_argument("scrape_id", help="scrape_id to stop")
    stop_p.add_argument("--json", action="store_true", help="Print full JSON result")

    run_p = subs.add_parser(
        "run",
        help="One-shot: scrape → interact → stop (login / form convenience)",
    )
    run_p.add_argument("url", help="https://… page to open")
    run_p.add_argument("--prompt", default=None, help="Natural-language instruction")
    run_p.add_argument("--code", default=None, help="Playwright code")
    run_p.add_argument("--code-file", default=None, help="Read Playwright code from a file")
    run_p.add_argument(
        "--language",
        choices=("node", "python", "bash"),
        default="node",
    )
    run_p.add_argument("--profile", dest="profile_name", default=None)
    run_p.add_argument(
        "--save-changes",
        dest="profile_save_changes",
        action="store_true",
        default=None,
    )
    run_p.add_argument(
        "--no-save-changes",
        dest="profile_save_changes",
        action="store_false",
    )
    run_p.add_argument("--timeout", type=int, default=None)
    run_p.add_argument(
        "--keep-open",
        action="store_true",
        help="Do not stop the session after interact (you must stop later)",
    )
    run_p.add_argument("--json", action="store_true", help="Print full JSON result")

    subparser.set_defaults(func=firecrawl_command)


def _load_code(args: argparse.Namespace) -> Optional[str]:
    code = getattr(args, "code", None)
    code_file = getattr(args, "code_file", None)
    if code_file:
        try:
            with open(code_file, encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            print(f"error: cannot read --code-file: {exc}", file=sys.stderr)
            return None
    return code


def _print_result(result: dict[str, Any], *, as_json: bool, human_keys: tuple[str, ...]) -> int:
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        if not result.get("success"):
            print(f"error: {result.get('error', 'unknown failure')}", file=sys.stderr)
        else:
            for key in human_keys:
                if key in result and result[key] is not None:
                    print(f"{key}: {result[key]}")
            # Always surface scrape_id when present
            if "scrape_id" in result and "scrape_id" not in human_keys:
                print(f"scrape_id: {result['scrape_id']}")
    return 0 if result.get("success") else 1


def firecrawl_command(args: argparse.Namespace) -> int:
    """Dispatch ``hermes firecrawl`` subcommands."""
    cmd = getattr(args, "firecrawl_command", None)
    if not cmd:
        print(
            "usage: hermes firecrawl {scrape,interact,stop,run} …\n"
            "Run `hermes firecrawl scrape --help` for details.\n"
            "Requires FIRECRAWL_API_KEY (or Nous managed Firecrawl).",
            file=sys.stderr,
        )
        return 2

    if not fc_interact.check_interact_available():
        from hermes_constants import display_hermes_home

        print(
            "error: Firecrawl is not configured. Set FIRECRAWL_API_KEY in "
            f"{display_hermes_home()}/.env (or enable Nous Subscription via "
            "`hermes tools`).",
            file=sys.stderr,
        )
        return 1

    as_json = bool(getattr(args, "json", False))

    if cmd == "scrape":
        result = fc_interact.start_session(
            args.url,
            profile_name=getattr(args, "profile_name", None),
            profile_save_changes=getattr(args, "profile_save_changes", None),
        )
        return _print_result(
            result,
            as_json=as_json,
            human_keys=("scrape_id", "title", "url", "message"),
        )

    if cmd == "interact":
        code = _load_code(args)
        if getattr(args, "code_file", None) and code is None:
            return 1
        if not args.prompt and not code:
            print("error: provide --prompt and/or --code/--code-file", file=sys.stderr)
            return 2
        result = fc_interact.act(
            args.scrape_id,
            prompt=args.prompt,
            code=code,
            language=args.language,
            timeout=args.timeout,
        )
        return _print_result(
            result,
            as_json=as_json,
            human_keys=("output", "result", "live_view_url", "stderr", "error"),
        )

    if cmd == "stop":
        result = fc_interact.stop_session(args.scrape_id)
        return _print_result(
            result,
            as_json=as_json,
            human_keys=("scrape_id", "credits_billed", "session_duration_ms"),
        )

    if cmd == "run":
        code = _load_code(args)
        if getattr(args, "code_file", None) and code is None:
            return 1
        if not args.prompt and not code:
            print("error: provide --prompt and/or --code/--code-file", file=sys.stderr)
            return 2
        result = fc_interact.run_flow(
            args.url,
            prompt=args.prompt,
            code=code,
            language=args.language,
            profile_name=getattr(args, "profile_name", None),
            profile_save_changes=getattr(args, "profile_save_changes", None),
            timeout=args.timeout,
            stop=not bool(getattr(args, "keep_open", False)),
        )
        return _print_result(
            result,
            as_json=as_json,
            human_keys=("output", "result", "live_view_url", "scrape_id", "error"),
        )

    print(f"error: unknown firecrawl command {cmd!r}", file=sys.stderr)
    return 2
