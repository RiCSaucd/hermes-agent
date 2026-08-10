"""Tests for Firecrawl Interact (scrape → act → stop) integration.

Covers the HTTP path with mocked ``requests`` — no live Firecrawl calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")
    monkeypatch.delenv("FIRECRAWL_API_URL", raising=False)
    yield hermes_home


@pytest.fixture(autouse=True)
def _reset_firecrawl_client():
    from plugins.web.firecrawl.provider import _reset_client_for_tests

    _reset_client_for_tests()
    yield
    _reset_client_for_tests()


def test_check_interact_available_respects_api_key(monkeypatch):
    from plugins.web.firecrawl import interact as fc

    assert fc.check_interact_available() is True
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    # Also clear any gateway path
    with patch(
        "plugins.web.firecrawl.provider._is_tool_gateway_ready",
        return_value=False,
    ):
        assert fc.check_interact_available() is False


def test_start_session_http_extracts_scrape_id(monkeypatch):
    from plugins.web.firecrawl import interact as fc

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "success": True,
        "data": {
            "markdown": "# Hi",
            "metadata": {"title": "Example", "scrapeId": "job-abc"},
        },
    }

    # Force SDK path to miss scrape_id so HTTP path runs
    fake_client = MagicMock()
    fake_client.scrape.side_effect = RuntimeError("sdk down")
    fake_client.interact = None

    with patch.object(fc, "_get_firecrawl_client", return_value=fake_client), patch(
        "plugins.web.firecrawl.interact.requests.post", return_value=mock_resp
    ) as post, patch(
        "plugins.web.firecrawl.interact.is_safe_url", return_value=True
    ), patch(
        "plugins.web.firecrawl.interact.check_website_access", return_value=None
    ):
        result = fc.start_session(
            "https://example.com",
            profile_name="my-profile",
            profile_save_changes=True,
        )

    assert result["success"] is True
    assert result["scrape_id"] == "job-abc"
    assert result["title"] == "Example"
    body = post.call_args.kwargs["json"]
    assert body["url"] == "https://example.com"
    assert body["profile"] == {"name": "my-profile", "saveChanges": True}


def test_start_session_blocks_unsafe_url():
    from plugins.web.firecrawl import interact as fc

    with patch(
        "plugins.web.firecrawl.interact.is_safe_url", return_value=False
    ):
        result = fc.start_session("http://127.0.0.1/")
    assert result["success"] is False
    assert "SSRF" in result["error"]


def test_act_http_normalizes_live_view_url():
    from plugins.web.firecrawl import interact as fc

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "success": True,
        "output": "clicked login",
        "liveViewUrl": "https://live.example/view",
    }

    fake_client = MagicMock(spec=[])  # no interact methods

    with patch.object(fc, "_get_firecrawl_client", return_value=fake_client), patch(
        "plugins.web.firecrawl.interact.requests.post", return_value=mock_resp
    ) as post:
        result = fc.act("job-abc", prompt="Click the login button")

    assert result["success"] is True
    assert result["output"] == "clicked login"
    assert result["live_view_url"] == "https://live.example/view"
    assert post.call_args.args[0].endswith("/v2/scrape/job-abc/interact")
    assert post.call_args.kwargs["json"]["prompt"] == "Click the login button"


def test_act_requires_prompt_or_code():
    from plugins.web.firecrawl import interact as fc

    result = fc.act("job-abc")
    assert result["success"] is False
    assert "prompt" in result["error"]


def test_stop_session_http_delete():
    from plugins.web.firecrawl import interact as fc

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.content = b'{"success":true,"creditsBilled":3}'
    mock_resp.json.return_value = {"success": True, "creditsBilled": 3}

    fake_client = MagicMock(spec=[])

    with patch.object(fc, "_get_firecrawl_client", return_value=fake_client), patch(
        "plugins.web.firecrawl.interact.requests.delete", return_value=mock_resp
    ) as delete:
        result = fc.stop_session("job-abc")

    assert result["success"] is True
    assert result["credits_billed"] == 3
    assert delete.call_args.args[0].endswith("/v2/scrape/job-abc/interact")


def test_run_flow_chains_start_act_stop():
    from plugins.web.firecrawl import interact as fc

    with patch.object(
        fc,
        "start_session",
        return_value={"success": True, "scrape_id": "job-1", "url": "https://example.com"},
    ), patch.object(
        fc,
        "act",
        return_value={"success": True, "output": "done", "live_view_url": "https://lv"},
    ) as act, patch.object(
        fc,
        "stop_session",
        return_value={"success": True, "scrape_id": "job-1"},
    ) as stop:
        result = fc.run_flow(
            "https://example.com",
            prompt="Fill the form",
            profile_name="p1",
        )

    assert result["success"] is True
    assert result["output"] == "done"
    assert result["scrape_id"] == "job-1"
    act.assert_called_once()
    stop.assert_called_once_with("job-1")


def test_tool_handler_dispatches_actions():
    from plugins.web.firecrawl.tools import handle_firecrawl_interact

    with patch(
        "plugins.web.firecrawl.tools.fc_interact.start_session",
        return_value={"success": True, "scrape_id": "x"},
    ):
        raw = handle_firecrawl_interact(
            {"action": "start", "url": "https://example.com"}
        )
    data = json.loads(raw)
    assert data["scrape_id"] == "x"

    raw = handle_firecrawl_interact({"action": "nope"})
    assert json.loads(raw)["success"] is False


def test_cli_run_requires_prompt_or_code(capsys):
    from argparse import Namespace

    from plugins.web.firecrawl.cli import firecrawl_command

    with patch(
        "plugins.web.firecrawl.cli.fc_interact.check_interact_available",
        return_value=True,
    ):
        code = firecrawl_command(
            Namespace(
                firecrawl_command="run",
                url="https://example.com",
                prompt=None,
                code=None,
                code_file=None,
                language="node",
                profile_name=None,
                profile_save_changes=None,
                timeout=None,
                keep_open=False,
                json=False,
            )
        )
    assert code == 2
    err = capsys.readouterr().err
    assert "--prompt" in err


def test_plugin_registers_tool_and_cli():
    from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from plugins.web.firecrawl import register
    from tools.registry import registry

    manager = get_plugin_manager()
    manifest = PluginManifest(name="web-firecrawl", version="1.1.0", source="test")
    ctx = PluginContext(manifest, manager)

    with patch.object(ctx, "register_web_search_provider"), patch.object(
        ctx, "register_skill"
    ):
        register(ctx)

    entry = registry.get_entry("firecrawl_interact")
    assert entry is not None
    assert entry.toolset == "firecrawl_interact"
    assert "firecrawl" in manager._cli_commands


def test_firecrawl_interact_default_off():
    from hermes_cli.tools_config import _DEFAULT_OFF_TOOLSETS

    assert "firecrawl_interact" in _DEFAULT_OFF_TOOLSETS