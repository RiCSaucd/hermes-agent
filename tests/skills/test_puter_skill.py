"""Tests for optional-skills/web-development/puter."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

SKILL_DIR = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "web-development"
    / "puter"
)
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPT = SKILL_DIR / "scripts" / "fetch_puter_docs.py"
MANIFEST = (
    Path(__file__).resolve().parents[2] / "optional-mcps" / "puter" / "manifest.yaml"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("fetch_puter_docs", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestSkillFrontmatter:
    def test_skill_md_exists(self):
        assert SKILL_MD.is_file()

    def test_description_contract(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        assert m, "missing description frontmatter"
        desc = m.group(1).strip()
        assert len(desc) <= 60, len(desc)
        assert desc.endswith(".")
        assert "puter" in desc.lower()

    def test_required_sections(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        for heading in (
            "## When to Use",
            "## Prerequisites",
            "## How to Run",
            "## Quick Reference",
            "## Procedure",
            "## Pitfalls",
            "## Verification",
        ):
            assert heading in text, f"missing {heading}"

    def test_references_shipped(self):
        for name in ("api-quickref.md", "mcp-and-cli.md", "docs-index.md"):
            path = SKILL_DIR / "references" / name
            assert path.is_file(), name
            assert path.stat().st_size > 100

    def test_template_has_powered_by_footer(self):
        html = (SKILL_DIR / "templates" / "hello-puter.html").read_text(
            encoding="utf-8"
        )
        assert "js.puter.com/v2" in html
        assert "developer.puter.com" in html
        assert "Powered by Puter" in html


class TestFetchPuterDocs:
    def test_fetch_index_uses_llms_txt(self):
        mod = _load_script()
        with patch.object(mod, "fetch_text", return_value="# Puter.js\n") as ft:
            body = mod.fetch_index("https://docs.puter.com")
        assert body.startswith("# Puter.js")
        ft.assert_called_once_with("https://docs.puter.com/llms.txt")

    def test_fetch_page_appends_index_md(self):
        mod = _load_script()
        with patch.object(mod, "fetch_text", return_value="chat docs") as ft:
            assert mod.fetch_page("AI/chat") == "chat docs"
        ft.assert_called_once_with("https://docs.puter.com/AI/chat/index.md")

    def test_fetch_page_accepts_full_url(self):
        mod = _load_script()
        with patch.object(mod, "fetch_text", return_value="ok") as ft:
            mod.fetch_page("https://docs.puter.com/FS/write/")
        ft.assert_called_once_with("https://docs.puter.com/FS/write/index.md")

    def test_cli_index_json(self, capsys):
        mod = _load_script()
        with patch.object(mod, "fetch_index", return_value="INDEX"):
            rc = mod.main(["index", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"ok": true' in out
        assert "INDEX" in out

    def test_cli_get_prints_body(self, capsys):
        mod = _load_script()
        with patch.object(mod, "fetch_page", return_value="PAGE"):
            rc = mod.main(["get", "KV/set"])
        assert rc == 0
        assert capsys.readouterr().out == "PAGE\n"


class TestPuterMcpCatalog:
    def test_manifest_parses(self):
        raw = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        assert raw["manifest_version"] == 1
        assert raw["name"] == "puter"
        assert raw["transport"]["type"] == "http"
        assert raw["transport"]["url"].startswith("https://mcp.puter.com")
        assert raw["auth"]["type"] == "oauth"

    def test_catalog_loads_puter_entry(self, monkeypatch):
        # Use the real repo optional-mcps/ (no HERMES_OPTIONAL_MCPS override).
        monkeypatch.delenv("HERMES_OPTIONAL_MCPS", raising=False)
        from hermes_cli.mcp_catalog import get_entry

        entry = get_entry("puter")
        assert entry is not None
        assert entry.transport.url == "https://mcp.puter.com/"
        assert entry.auth.type == "oauth"
