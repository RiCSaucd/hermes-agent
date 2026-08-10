"""Firecrawl Interact — scrape-bound browser sessions.

Wraps Firecrawl's scrape → interact → stop flow:

  POST   /v2/scrape
  POST   /v2/scrape/{scrapeId}/interact   (prompt and/or Playwright code)
  DELETE /v2/scrape/{scrapeId}/interact

Uses raw HTTP so Interact works even when the pinned ``firecrawl-py``
SDK predates these methods. When the SDK *does* expose ``interact`` /
``stop_interaction``, we prefer that path so gateway auth stays consistent
with search/extract.

Primary use cases: login flows, form fills, multi-step navigation, and
persisting cookies via named profiles.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import requests

from hermes_constants import display_hermes_home
from plugins.web.firecrawl.provider import (
    _get_direct_firecrawl_config,
    _get_firecrawl_client,
    check_firecrawl_api_key,
)
from tools.url_safety import is_safe_url
from tools.website_policy import check_website_access

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api.firecrawl.dev"
_REQUEST_TIMEOUT = 120


def check_interact_available() -> bool:
    """Runtime gate for interact tools/CLI — same credentials as web Firecrawl."""
    return check_firecrawl_api_key()


def _plain(value: Any) -> Any:
    """Best-effort conversion of SDK / pydantic objects to plain data."""
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "__dict__"):
        try:
            return {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        except Exception:  # noqa: BLE001
            pass
    return value


def _resolve_http_auth() -> Tuple[str, Dict[str, str]]:
    """Return ``(base_url, headers)`` for direct or managed-gateway auth.

    Mirrors :func:`_get_firecrawl_client` preference order so Interact hits
    the same backend the user configured for search/extract.
    """
    import tools.web_tools as _wt

    direct = _get_direct_firecrawl_config()
    if direct is not None and not _wt.prefers_gateway("web"):
        kwargs, _ = direct
        api_key = (kwargs.get("api_key") or "").strip()
        api_url = (kwargs.get("api_url") or _DEFAULT_API_URL).rstrip("/")
        if not api_key and not kwargs.get("api_url"):
            raise ValueError(
                "Firecrawl is not configured. Set FIRECRAWL_API_KEY in "
                f"{display_hermes_home()}/.env or run `hermes tools` to select "
                "a web provider."
            )
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return api_url, headers

    managed = _wt.resolve_managed_tool_gateway(
        "firecrawl", token_reader=_wt._read_nous_access_token
    )
    if managed is None:
        # Fall back to direct if gateway preferred but unavailable and direct exists
        if direct is not None:
            kwargs, _ = direct
            api_key = (kwargs.get("api_key") or "").strip()
            api_url = (kwargs.get("api_url") or _DEFAULT_API_URL).rstrip("/")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            return api_url, headers
        raise ValueError(
            "Firecrawl is not configured. Set FIRECRAWL_API_KEY or enable "
            "Nous Subscription for managed Firecrawl via `hermes tools`."
        )

    return managed.gateway_origin.rstrip("/"), {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {managed.nous_user_token}",
    }


def _sdk_supports_interact(client: Any) -> bool:
    return callable(getattr(client, "interact", None)) and callable(
        getattr(client, "stop_interaction", None)
    )


def _extract_scrape_id(document: Any) -> Optional[str]:
    """Pull scrapeId / scrape_id out of an SDK Document or plain dict."""
    plain = _plain(document)
    if not isinstance(plain, dict):
        return None

    data = plain.get("data") if isinstance(plain.get("data"), dict) else plain
    metadata = data.get("metadata") if isinstance(data, dict) else None
    metadata = _plain(metadata) if metadata is not None else {}
    if not isinstance(metadata, dict):
        metadata = {}

    for key in ("scrape_id", "scrapeId"):
        value = metadata.get(key) or (data.get(key) if isinstance(data, dict) else None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def start_session(
    url: str,
    *,
    profile_name: Optional[str] = None,
    profile_save_changes: Optional[bool] = None,
    timeout_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Scrape ``url`` and return ``{success, scrape_id, ...}`` for Interact.

    Optional ``profile_name`` persists browser state (cookies, localStorage)
    across sessions — use ``profile_save_changes=True`` after a login so the
    next scrape with the same profile reuses the session.
    """
    url = (url or "").strip()
    if not url:
        return {"success": False, "error": "url is required"}

    if not is_safe_url(url):
        return {
            "success": False,
            "error": "URL blocked by SSRF safety checks (private/local targets are not allowed).",
        }

    blocked = check_website_access(url)
    if blocked:
        return {
            "success": False,
            "error": blocked.get("message") or "URL blocked by website policy",
            "blocked_by_policy": {
                "host": blocked.get("host"),
                "rule": blocked.get("rule"),
                "source": blocked.get("source"),
            },
        }

    profile: Optional[Dict[str, Any]] = None
    if profile_name:
        profile = {
            "name": profile_name.strip(),
            "saveChanges": (
                True if profile_save_changes is None else bool(profile_save_changes)
            ),
        }

    # Prefer SDK scrape when available (handles gateway quirks + normalization)
    try:
        client = _get_firecrawl_client()
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    scrape_kwargs: Dict[str, Any] = {}
    if profile is not None:
        scrape_kwargs["profile"] = profile
    if timeout_ms is not None:
        scrape_kwargs["timeout"] = int(timeout_ms)

    try:
        if hasattr(client, "scrape"):
            document = client.scrape(url, **scrape_kwargs)
            scrape_id = _extract_scrape_id(document)
            payload = _plain(document)
            if scrape_id:
                meta = {}
                if isinstance(payload, dict):
                    raw_meta = payload.get("metadata") or {}
                    meta = _plain(raw_meta) if raw_meta else {}
                return {
                    "success": True,
                    "scrape_id": scrape_id,
                    "url": url,
                    "title": (meta or {}).get("title") if isinstance(meta, dict) else None,
                    "profile": profile,
                    "message": (
                        "Scrape session ready. Call firecrawl_interact with "
                        "action='act' using this scrape_id, then action='stop' when done."
                    ),
                }
        # Fall through to HTTP if scrape_id missing from SDK response
    except Exception as exc:  # noqa: BLE001
        logger.info("SDK scrape for interact failed (%s); trying HTTP", exc)

    try:
        base_url, headers = _resolve_http_auth()
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    body: Dict[str, Any] = {"url": url}
    if profile is not None:
        body["profile"] = profile
    if timeout_ms is not None:
        body["timeout"] = int(timeout_ms)

    try:
        response = requests.post(
            f"{base_url}/v2/scrape",
            headers=headers,
            json=body,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        return {"success": False, "error": f"Firecrawl scrape request failed: {exc}"}

    if not response.ok:
        return {
            "success": False,
            "error": f"Firecrawl scrape failed: HTTP {response.status_code} {response.text[:500]}",
        }

    try:
        payload = response.json()
    except ValueError:
        return {"success": False, "error": "Firecrawl scrape returned non-JSON response"}

    if not payload.get("success", True) and payload.get("error"):
        return {"success": False, "error": payload.get("error")}

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    scrape_id = _extract_scrape_id({"data": data} if data is not payload else payload)
    if not scrape_id:
        return {
            "success": False,
            "error": (
                "Scrape succeeded but no scrapeId was returned — Interact requires "
                "a scrape-bound session. Ensure your Firecrawl plan/API supports Interact."
            ),
        }

    metadata = data.get("metadata") if isinstance(data, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "success": True,
        "scrape_id": scrape_id,
        "url": url,
        "title": metadata.get("title"),
        "profile": profile,
        "message": (
            "Scrape session ready. Call firecrawl_interact with action='act' "
            "using this scrape_id, then action='stop' when done."
        ),
    }


def act(
    scrape_id: str,
    *,
    prompt: Optional[str] = None,
    code: Optional[str] = None,
    language: str = "node",
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Run a natural-language prompt and/or Playwright code on a scrape session."""
    scrape_id = (scrape_id or "").strip()
    if not scrape_id:
        return {"success": False, "error": "scrape_id is required"}

    prompt_text = (prompt or "").strip() or None
    code_text = (code or "").strip() or None
    if not prompt_text and not code_text:
        return {
            "success": False,
            "error": "Provide prompt (natural language) and/or code (Playwright)",
        }

    language = (language or "node").strip().lower()
    if language not in {"python", "node", "bash"}:
        return {
            "success": False,
            "error": "language must be one of: python, node, bash",
        }

    # Prefer SDK when Interact methods exist
    try:
        client = _get_firecrawl_client()
        if _sdk_supports_interact(client):
            result = client.interact(
                scrape_id,
                code_text,
                prompt=prompt_text,
                language=language,
                timeout=timeout,
            )
            plain = _plain(result)
            if not isinstance(plain, dict):
                plain = {"result": plain}
            plain.setdefault("success", True)
            plain["scrape_id"] = scrape_id
            return plain
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.info("SDK interact failed (%s); trying HTTP", exc)

    try:
        base_url, headers = _resolve_http_auth()
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    body: Dict[str, Any] = {"language": language}
    if prompt_text:
        body["prompt"] = prompt_text
    if code_text:
        body["code"] = code_text
    if timeout is not None:
        body["timeout"] = int(timeout)

    try:
        response = requests.post(
            f"{base_url}/v2/scrape/{scrape_id}/interact",
            headers=headers,
            json=body,
            timeout=max(_REQUEST_TIMEOUT, int(timeout or 0) + 30),
        )
    except requests.RequestException as exc:
        return {"success": False, "error": f"Firecrawl interact request failed: {exc}"}

    if not response.ok:
        return {
            "success": False,
            "error": (
                f"Firecrawl interact failed: HTTP {response.status_code} "
                f"{response.text[:500]}"
            ),
            "scrape_id": scrape_id,
        }

    try:
        payload = response.json()
    except ValueError:
        return {"success": False, "error": "Firecrawl interact returned non-JSON response"}

    # Normalize camelCase fields from the API
    out = dict(payload) if isinstance(payload, dict) else {"result": payload}
    for camel, snake in (
        ("liveViewUrl", "live_view_url"),
        ("interactiveLiveViewUrl", "interactive_live_view_url"),
        ("cdpUrl", "cdp_url"),
        ("exitCode", "exit_code"),
    ):
        if camel in out and snake not in out:
            out[snake] = out[camel]
    out["scrape_id"] = scrape_id
    if "success" not in out:
        out["success"] = not bool(out.get("error"))
    return out


def stop_session(scrape_id: str) -> Dict[str, Any]:
    """Stop the Interact session for ``scrape_id`` (ends billing for the browser)."""
    scrape_id = (scrape_id or "").strip()
    if not scrape_id:
        return {"success": False, "error": "scrape_id is required"}

    try:
        client = _get_firecrawl_client()
        if _sdk_supports_interact(client):
            result = client.stop_interaction(scrape_id)
            plain = _plain(result)
            if not isinstance(plain, dict):
                plain = {"result": plain}
            plain.setdefault("success", True)
            plain["scrape_id"] = scrape_id
            return plain
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.info("SDK stop_interaction failed (%s); trying HTTP", exc)

    try:
        base_url, headers = _resolve_http_auth()
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    try:
        response = requests.delete(
            f"{base_url}/v2/scrape/{scrape_id}/interact",
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as exc:
        return {"success": False, "error": f"Firecrawl stop request failed: {exc}"}

    if not response.ok:
        return {
            "success": False,
            "error": (
                f"Firecrawl stop failed: HTTP {response.status_code} "
                f"{response.text[:500]}"
            ),
            "scrape_id": scrape_id,
        }

    try:
        payload = response.json() if response.content else {"success": True}
    except ValueError:
        payload = {"success": True}

    out = dict(payload) if isinstance(payload, dict) else {"success": True}
    for camel, snake in (
        ("sessionDurationMs", "session_duration_ms"),
        ("creditsBilled", "credits_billed"),
    ):
        if camel in out and snake not in out:
            out[snake] = out[camel]
    out.setdefault("success", True)
    out["scrape_id"] = scrape_id
    return out


def run_flow(
    url: str,
    *,
    prompt: Optional[str] = None,
    code: Optional[str] = None,
    language: str = "node",
    profile_name: Optional[str] = None,
    profile_save_changes: Optional[bool] = None,
    timeout: Optional[int] = None,
    stop: bool = True,
) -> Dict[str, Any]:
    """One-shot scrape → interact → optional stop (login/form convenience path)."""
    started = start_session(
        url,
        profile_name=profile_name,
        profile_save_changes=profile_save_changes,
    )
    if not started.get("success"):
        return started

    scrape_id = started["scrape_id"]
    interacted = act(
        scrape_id,
        prompt=prompt,
        code=code,
        language=language,
        timeout=timeout,
    )

    stopped: Optional[Dict[str, Any]] = None
    if stop:
        stopped = stop_session(scrape_id)

    return {
        "success": bool(interacted.get("success")),
        "scrape_id": scrape_id,
        "url": url,
        "start": started,
        "interact": interacted,
        "stop": stopped,
        "output": interacted.get("output"),
        "result": interacted.get("result"),
        "live_view_url": interacted.get("live_view_url") or interacted.get("liveViewUrl"),
        "error": interacted.get("error"),
    }
