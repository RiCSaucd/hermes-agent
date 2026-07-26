# Puter MCP Server and CLI

Scraped from https://docs.puter.com/mcp/ and https://docs.puter.com/cli/ (2026-07-26).

## MCP server (agent integration)

- **Endpoint:** `https://mcp.puter.com/` (HTTP / Streamable HTTP, OAuth required)
- **OAuth resource metadata:** `https://mcp.puter.com/.well-known/oauth-protected-resource`
- Nothing to host locally — point Hermes (or Cursor / Claude Code / Codex / OpenCode) at the URL and sign in.

### Hermes

```bash
hermes mcp install puter
# or: hermes mcp catalog  → install puter
```

Catalog manifest: `optional-mcps/puter/manifest.yaml`.

### Cursor

```json
{
  "mcpServers": {
    "puter": {
      "url": "https://mcp.puter.com/"
    }
  }
}
```

Then Cursor Settings → MCP → login next to `puter`.

### Claude Code

```bash
claude mcp add --transport http --scope user puter https://mcp.puter.com/
```

Then `/mcp` inside Claude Code to authenticate.

### Tools exposed

| Group | Tools |
|-------|-------|
| Filesystem | `fs_write_file`, `fs_read_file`, `fs_readdir`, `fs_mkdir`, `fs_stat`, `fs_delete` |
| Hosting | `hosting_create`, `hosting_list`, `hosting_get`, `hosting_update`, `hosting_delete` |
| Workers | `workers_create`, `workers_exec`, `workers_list`, `workers_get`, `workers_delete` |
| Apps | `apps_create`, `apps_check_name`, `apps_list`, `apps_get`, `apps_update`, `apps_delete` |
| Docs | `puter_docs_index`, `puter_docs_get` |
| Account | `whoami` |

Each tool mirrors the equivalent Puter.js SDK call. Prefer `puter_docs_get` when you need a specific API page beyond this skill's references.

## CLI (`@heyputer/cli`)

Beta (0.x). Scraped npm latest: `0.1.2`. Requires Node 18+.

```bash
npm install -g @heyputer/cli
puter login                 # browser OAuth; stores token
# headless / CI:
echo "$TOKEN" | puter login --with-token
export PUTER_AUTH_TOKEN=... # skips login; preferred for automation
puter whoami
```

### Sites

```bash
puter site deploy ./dist my-app   # → https://my-app.puter.site
puter site list
puter site get <subdomain>
puter site delete <subdomain> -y
```

Deploys are versioned (each upload lands in its own folder).

### Workers

```bash
puter worker deploy ./api.js my-api   # → https://my-api.puter.work
puter worker list
puter worker get <name>
puter worker delete <name> -y
```

Redeploying the same name replaces the worker in place.

### Apps (read-only)

```bash
puter app list
puter app get <name>
```

### Env

| Variable | Meaning |
|----------|---------|
| `PUTER_AUTH_TOKEN` | Auth token; wins over stored login |
| `CI` | Forces non-interactive mode (no prompts) |
