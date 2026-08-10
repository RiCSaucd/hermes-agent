---
name: firecrawl-interact
description: Drive scrape sessions for logins and form fills.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [firecrawl, browser, login, forms, interact]
    category: web
---

# Firecrawl Interact Skill

Use Firecrawl Interact to open a page, drive it with a natural-language
prompt or Playwright code, optionally persist login state in a profile,
and always stop the session when finished.

This skill covers the Hermes-integrated path (agent tool + CLI). It does
not replace the built-in `browser_*` tools for general browsing — prefer
Interact for Firecrawl-hosted scrape sessions, logins, and form flows.

## When to Use

- Log in to a site and reuse cookies later (profiles)
- Fill and submit forms with a prompt or Playwright selectors
- Chain multiple steps on the same page session
- One-shot scrape → act → stop from the CLI

## Prerequisites

- `FIRECRAWL_API_KEY` in `~/.hermes/.env`, or Nous managed Firecrawl via
  `hermes tools`
- Firecrawl plan/API that supports Interact (`/v2/scrape/{id}/interact`)

## How to Run

**Agent tool** (preferred in-session):

```text
firecrawl_interact action=start url="https://example.com" profile_name="my-profile" profile_save_changes=true
firecrawl_interact action=act scrape_id="<id>" prompt="Log in with test@example.com / password123"
firecrawl_interact action=stop scrape_id="<id>"
```

One-shot:

```text
firecrawl_interact action=run url="https://example.com" prompt="Submit the contact form with …"
```

**CLI** (from `terminal` or a shell):

```bash
hermes firecrawl scrape "https://example.com" --profile my-profile --save-changes
hermes firecrawl interact <scrape_id> --prompt "Click login and fill the email field"
hermes firecrawl stop <scrape_id>

# One-shot login / form flow
hermes firecrawl run "https://example.com" \
  --prompt "Log in with test@example.com / password123" \
  --profile my-profile --save-changes
```

Playwright code path:

```bash
hermes firecrawl interact <scrape_id> --language node --code '
  await page.click("#login-button");
  await page.fill("#email", "test@example.com");
  return await page.title();
'
```

## Quick Reference

| Action | Needs | Notes |
|--------|-------|-------|
| `start` | `url` | Returns `scrape_id` |
| `act` | `scrape_id` + `prompt` and/or `code` | Session state persists |
| `stop` | `scrape_id` | Always stop to avoid billing |
| `run` | `url` + `prompt`/`code` | start→act→stop |

## Procedure

1. Start (or `run`) with the target URL.
2. Prefer `prompt` for open-ended UI; use `code` when selectors are known.
3. Chain more `act` calls on the same `scrape_id` as needed.
4. For login reuse: start with `profile_name` + `profile_save_changes=true`,
   then later start with the same profile and `profile_save_changes=false`.
5. Call `stop` when done (unless `run` already stopped).

## Pitfalls

- Leaving sessions open bills for idle browser time — always `stop`.
- `scrape_id` comes from Interact-capable scrapes; missing id usually means
  the API/plan does not expose Interact.
- Do not put secrets in skill files; pass credentials only in the live
  prompt/code for that run.
- SSRF/policy gates block private/local URLs.

## Verification

```bash
hermes firecrawl scrape "https://example.com" --json
# expect success=true and a scrape_id, then:
hermes firecrawl stop <scrape_id>
```
