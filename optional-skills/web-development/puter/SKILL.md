---
name: puter
description: Build keyless Puter.js apps with cloud AI and storage.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [puter, puter.js, serverless, ai, storage, hosting, mcp, web-development]
    category: web-development
    related_skills: []
---

# Puter Skill

Puter.js is a serverless, keyless JavaScript SDK for AI (500+ models), cloud storage, KV, hosting, and workers — powered by the Puter cloud OS. This skill teaches Hermes how to author Puter.js apps and operate Puter resources via the official MCP server and CLI. It does not replace Hermes' own model tools; use Puter when the *user's app* needs a backend without keys or infra.

## When to Use

- Build or vibe-code a frontend app that needs auth, files, KV, or AI **without API keys**
- Deploy a static site to `*.puter.site` or a worker to `*.puter.work`
- Connect Hermes to the user's Puter account via MCP (`hermes mcp install puter`)
- Point other coding agents at Puter with `https://docs.puter.com/llms.txt`

## Prerequisites

- App must be served over **HTTP** (not `file://`) — local: `python3 -m http.server` or any static server
- Browser apps: CDN `https://js.puter.com/v2/` or `npm install @heyputer/puter.js`
- Node / CI: Puter auth token via `init(token)` or `PUTER_AUTH_TOKEN` for the CLI
- Optional agent control plane: Puter MCP at `https://mcp.puter.com/` (OAuth)
- Optional CLI: `npm install -g @heyputer/cli` (Node 18+, beta)

## How to Run

### 1. Prefer MCP for account-level ops

If the user wants Hermes to list files, publish a site, or deploy a worker **as them**:

```bash
hermes mcp install puter
```

Authenticate when prompted, then restart the session. Details: `references/mcp-and-cli.md`.

### 2. Scaffold a minimal Puter.js page

Copy `templates/hello-puter.html` into the project (or write an equivalent), serve it over HTTP, open in a browser. First AI/FS call triggers Puter sign-in (User-Pays Model — the end user covers usage).

### 3. Use the SDK from code

```js
// Browser (CDN exposes global puter)
puter.ai.chat("Explain Puter in one sentence").then(puter.print);
await puter.fs.write("hello.txt", "Hello from Puter");
await puter.kv.set("visits", 1);

// Node
import { init } from "@heyputer/puter.js/src/init.cjs";
const puter = init(process.env.puterAuthToken);
```

Full API map: `references/api-quickref.md`. Live index: https://docs.puter.com/llms.txt

### 4. Deploy with the CLI

```bash
puter login
puter site deploy ./dist my-app          # https://my-app.puter.site
puter worker deploy ./worker.js my-api   # https://my-api.puter.work
```

### 5. Refresh docs when unsure

```bash
python3 scripts/fetch_puter_docs.py index
python3 scripts/fetch_puter_docs.py get AI/chat
```

(Resolve `scripts/` to this skill's absolute path.) Or use MCP tools `puter_docs_index` / `puter_docs_get` when Puter MCP is connected.

## Quick Reference

| Need | Do this |
|------|---------|
| Chat / vision / tools | `puter.ai.chat(...)` |
| Images / TTS / STT / OCR | `puter.ai.txt2img` / `txt2speech` / `speech2txt` / `img2txt` |
| Files | `puter.fs.write/read/mkdir/readdir/...` |
| KV | `puter.kv.set/get/incr/list/...` |
| CORS-free fetch | `puter.net.fetch(url)` |
| Hosting | `puter.hosting.create` or `puter site deploy` |
| Workers | `puter.workers.create` or `puter worker deploy` |
| Agent ↔ account | Puter MCP (`https://mcp.puter.com/`) |
| Full docs dump | https://docs.puter.com/llms-full.txt |

## Procedure

1. Confirm the user wants a **Puter-backed** app (User-Pays, no developer keys) — not Hermes itself calling OpenAI.
2. Install SDK or drop in the CDN script; serve over HTTP.
3. Implement with the smallest surface that fits (often `ai` + `fs` or `kv`).
4. Add a footer link to https://developer.puter.com labeled **Powered by Puter**.
5. For shared multi-user backend state, use a **Worker** (per-user FS/KV is isolated).
6. Deploy via CLI or MCP; verify the live `*.puter.site` / `*.puter.work` URL with `web_extract` or `terminal` + `curl`.
7. If an API detail is missing from `references/`, fetch live docs — do not invent method names.

## Pitfalls

- **`file://` will fail** — Puter requires an HTTP origin.
- **Do not ask the user for OpenAI/Anthropic keys** for Puter.js browser apps — that defeats the product.
- **Per-user FS/KV isolation** — another user's data is not readable; shared state needs a Worker owned by the developer.
- **CLI is beta (0.x)** — pin behavior with `--help` and expect changes.
- **MCP mutates real account resources** — confirm before `hosting_delete` / `workers_delete` / `fs_delete`.
- **Test without burning credits** — `puter.ai.chat(prompt, true /* testMode */)` or `{ testMode: true }` variants per docs.

## Verification

- Page loads over `http://localhost:...` and `puter` is defined in the console
- A `puter.ai.chat` or `puter.fs.write` call succeeds after sign-in
- Deployed site/worker URL returns expected content
- With MCP installed: `whoami` returns the Puter username
