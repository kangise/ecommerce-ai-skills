# Privacy

This project does not operate a service. Nothing in this repository sends data
to its maintainers, and no component contains telemetry, analytics, crash
reporting or an update check. The sections below describe, component by
component, what is stored and which network connections are made. Each
statement is taken from the code in this repository; the file paths are given
so it can be checked.

## Claude Code plugin (the 9 skills)

The plugin (`dist/`, installed with `/plugin install
ecommerce-ai-skills@ecommerce-ai-skills`) consists of Markdown and YAML files:
skill instructions, platform constraints and prompt templates. It contains no
executable code, stores nothing and makes no network connections.

When Claude Code uses a skill, it reads these files into the conversation. What
Claude Code sends to Anthropic is governed by your agreement with Anthropic, not
by this project.

## MCP server

`opc-ecommerce mcp` (or `integration/mcp-server.py`) reads the knowledge package
from local disk. It makes one kind of network request, and only when both
`OPC_RUNTIME_URL` and `OPC_RUNTIME_API_KEY` are set: read-only requests to that
URL, which is a Commerce Agent OS instance you run yourself. The server does not
expose any tool that approves or executes an action.

## Commerce Agent OS (optional runtime)

The runtime runs on your own machine or server. There is no hosted version.

### What it stores

All runtime data is kept in one SQLite file, at the path you pass with `--db`
(`ecommerce_ai_skills/runtime/storage.py`):

- tenants, and users with their name and email address
- API keys, as salted hashes only; a key is shown once, when it is issued
- connector configuration: account identifiers and the *names* of the
  environment variables that hold credentials. A configuration containing a
  secret value is rejected (`ecommerce_ai_skills/runtime/accounts.py`)
- imported report files: the rows as imported, with the file name and a SHA-256
  checksum
- metric observations derived from those reports
- agent runs, their outputs, proposals, approvals and executions
- an audit log. Database triggers reject updates to audit entries

### How long it is kept

The live event stream shown in the interface keeps the latest 1,000 events per
tenant; older events are removed automatically. Everything else stays in the
database file until you delete it. Deleting the file removes all runtime data.

### Outbound connections

The runtime connects to other services only when you configure them:

| Destination | When | What is sent |
|---|---|---|
| Amazon Selling Partner API (`sellingpartnerapi-na/-eu/-fe.amazon.com`), Amazon Ads API (`advertising-api.amazon.com`, `-eu`, `-fe`), Login with Amazon (`api.amazon.com`) | A connector is configured and a report sync, health check or approved action runs | Requests for your own account's reports; an approved change |
| Your Shopify store (`<shop>.myshopify.com`) | Same as above | Same as above |
| OpenAI (`api.openai.com/v1/responses`, the default) or Anthropic (`api.anthropic.com/v1/messages`, with `EAI_AGENT_PROVIDER=anthropic`) | A Weekly Ops or Daily Ops review runs | The workflow, its objective, the skill instructions, and the imported report rows for the platform under review |

For the model providers (`ecommerce_ai_skills/runtime/agents.py`):

- OpenAI requests set `store: false`.
- Each request carries a pseudonymous identifier: `eai_` followed by the first
  32 hexadecimal characters of the SHA-256 of the tenant ID and user ID. Names
  and email addresses are not sent.
- An operator-triggered provider check sends the fixed message `Reply OK.` and
  no tenant data.
- What a provider does with a request is governed by your agreement with that
  provider.

In demo mode (`opc-ecommerce demo`), agent reviews run on a built-in
deterministic provider (`ecommerce_ai_skills/demo_seed.py`), so they send
nothing to OpenAI or Anthropic.

### Browser interface

The interface at `/app` loads no resources from other sites; its fonts, scripts
and icons are served by the runtime itself. Browser storage holds only the
theme and language preferences. The API key is kept in page memory and is not
written to browser storage or to the runtime database.

## Documentation site

The site at https://kangise.github.io/ecommerce-ai-skills/ is a set of static
pages hosted on GitHub Pages. It includes no analytics or tracking scripts. The
site's scripts store your theme and sidebar preferences in browser storage.
GitHub, as the host, receives the usual request data for any web page; see
[GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Maintainer scripts

The scripts under `scripts/` are not included in the Python package. When run,
two of them make network requests: `verify_content.py --probe-links` requests
each source URL cited in the chapters, and `watch_sources.py` queries the GitHub
API for the upstream repositories listed in `maintenance/source-watch.yaml`.

## Questions

Open an issue at https://github.com/kangise/ecommerce-ai-skills/issues. To
report a security problem, follow [SECURITY.md](SECURITY.md) instead.

Changes to this document are recorded in the repository's git history.
