#!/usr/bin/env python3
"""Fetch Puter.js documentation pages as Markdown.

Usage:
  python3 fetch_puter_docs.py index
  python3 fetch_puter_docs.py get AI/chat
  python3 fetch_puter_docs.py get FS/write --raw

Defaults to https://docs.puter.com/. Override with PUTER_DOCS_BASE.
No API key required. Network-only helper — tests mock urllib.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_BASE = "https://docs.puter.com"
USER_AGENT = "hermes-puter-skill/1.0 (+https://github.com/NousResearch/hermes-agent)"


def docs_base() -> str:
    return (os.environ.get("PUTER_DOCS_BASE") or DEFAULT_BASE).rstrip("/")


def fetch_text(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def fetch_index(base: Optional[str] = None) -> str:
    root = (base or docs_base()).rstrip("/")
    return fetch_text(f"{root}/llms.txt")


def fetch_page(path: str, base: Optional[str] = None) -> str:
    """Fetch a docs page. Accepts 'AI/chat', '/AI/chat/', or full URLs."""
    root = (base or docs_base()).rstrip("/")
    p = path.strip()
    if p.startswith("http://") or p.startswith("https://"):
        url = p
        if url.endswith("/"):
            url = url + "index.md"
        elif not url.endswith(".md"):
            url = url.rstrip("/") + "/index.md"
        return fetch_text(url)

    p = p.lstrip("/")
    if p.endswith(".md"):
        return fetch_text(f"{root}/{p}")
    p = p.rstrip("/")
    return fetch_text(f"{root}/{p}/index.md")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Fetch docs.puter.com/llms.txt")
    p_index.add_argument(
        "--json",
        action="store_true",
        help="Wrap body in a JSON object",
    )

    p_get = sub.add_parser("get", help="Fetch one docs page as Markdown")
    p_get.add_argument("path", help="e.g. AI/chat or FS/write")
    p_get.add_argument(
        "--json",
        action="store_true",
        help="Wrap body in a JSON object",
    )

    args = parser.parse_args(argv)
    try:
        if args.cmd == "index":
            body = fetch_index()
        else:
            body = fetch_page(args.path)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"network error: {exc.reason}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "bytes": len(body), "body": body}))
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
