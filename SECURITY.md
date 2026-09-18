# Security Policy

## Scope

Security reports are for the code that runs: the operations runtime
(`ecommerce_ai_skills/runtime/` — API authentication, tenant isolation, the
proposal → approval → execute control plane, and the Amazon SP-API / Amazon Ads /
Shopify connectors that hold credentials), the MCP server
(`integration/mcp-server.py`), the CLI (`opc-ecommerce`), and the build and
verification scripts under `scripts/`.

A wrong number or a bad recommendation in the knowledge base is a content
defect, not a vulnerability. Open a regular issue for those.

## Supported versions

| Version | Supported |
|---|---|
| `main` | yes |
| 1.3.x | yes |
| earlier | no — upgrade |

## Reporting

Use GitHub's private vulnerability reporting on this repository:
**Security → Report a vulnerability**. Do not open a public issue for anything
that could be exploited before it is fixed.

Include what you did, what happened, and what you expected; a minimal
reproduction is more useful than a long description.

You will get an acknowledgement within 7 days. Fixes for confirmed issues in
the runtime or connectors are released on `main` first; the changelog names the
fix without reproduction details until the release has been out for two weeks.

## What the runtime does with credentials

- Runtime API keys are issued once by `opc-ecommerce init` and are not
  recoverable afterwards; rotate by issuing a new one.
- The runtime database never holds connector secrets. A connector config
  stores the *names* of environment variables (`LWA_CLIENT_SECRET`-style
  references); a config that contains an actual secret value is rejected at
  write time. Secrets live in the environment of the process that runs the
  connector and nowhere else — not in the knowledge package, the MCP server's
  responses, or the audit log.
- Every write toward a platform goes through a proposal that a person approves
  in the UI or the API; the MCP server exposes read-only tools only and cannot
  approve or execute anything.
- The `demo` command runs an isolated database on loopback with clearly marked
  sample data; do not point it at production credentials.
