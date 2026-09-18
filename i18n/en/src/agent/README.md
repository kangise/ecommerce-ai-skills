# Agent Integration

`dist/` is this repository's agent package: 9 skills, a domain ontology, the prompt library and an MCP server, built from the same source as the chapters on this site and held to the same CI gates. Pick one of three ways to connect it.

## Claude Code

Two commands install the 9 skills; no Python environment needed:

```
/plugin marketplace add kangise/ecommerce-ai-skills
/plugin install ecommerce-ai-skills@ecommerce-ai-skills
```

Only each skill's name and description stay in context; the body, platform constraints and prompt sets load when a skill is used.

## Claude Desktop / Cursor (MCP)

```bash
pip install "ecommerce-ai-skills[mcp] @ git+https://github.com/kangise/ecommerce-ai-skills"
```

```json
{
  "mcpServers": {
    "opc-ecommerce": {
      "command": "opc-ecommerce",
      "args": ["mcp"]
    }
  }
}
```

The MCP server provides 8 resources and 5 tools; pointed at a running Commerce Agent OS, it adds 4 read-only operations tools. See the [MCP guide](https://github.com/kangise/ecommerce-ai-skills/blob/main/integration/mcp.md).

## Load the files directly

Agents that use neither Claude Code nor MCP can read [`dist/SKILL.md`](https://github.com/kangise/ecommerce-ai-skills/blob/main/dist/SKILL.md): it is the entry point and carries the rules for routing a request to the right skill. The full package is in [`dist/`](https://github.com/kangise/ecommerce-ai-skills/tree/main/dist).

## What's inside

| Layer | Content | For |
|---|---|---|
| Knowledge base | 69 chapters in Chinese, English and Japanese | People reading · agent retrieval |
| Ontology | 100 entities · 322 constraints | A shared contract between agents |
| Skills | 9 installable skills · 878 prompts | Agents calling them directly |

## Verify

From the repository root:

```bash
python3 scripts/verify_all.py   # all gates
python3 scripts/build_dist.py   # build dist/
```
