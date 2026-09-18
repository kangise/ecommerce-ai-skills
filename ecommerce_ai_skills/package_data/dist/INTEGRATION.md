# Integration Guides

This package is framework-agnostic. Choose your integration path:

| Framework | Guide | Why |
|-----------|-------|-----|
| Claude Code plugin | `/plugin marketplace add kangise/ecommerce-ai-skills` then `/plugin install ecommerce-ai-skills@ecommerce-ai-skills` | This directory is the plugin (`.claude-plugin/plugin.json`); the 9 skills load on demand, no server |
| MCP (Model Context Protocol) | [integration/mcp.md](integration/mcp.md) | Natural fit: resources + prompts + tools |
| Runtime API | [integration/runtime-api.md](integration/runtime-api.md) | Authenticated persistence, Weekly Ops agents, approvals, and actions |
| Direct file loading | [integration/mcp-system-prompt.md](integration/mcp-system-prompt.md) | No server needed — load files directly |

## Which Framework?

- **Claude Code plugin** — Best for Claude Code: skills only, nothing to run
- **MCP** — Best for Claude Desktop, Cursor, and any MCP-compatible client
- **Direct loading** — Works with any agent that can read files and follow instructions

## Adding a New Framework

1. Create `integration/<framework>.md` with setup instructions
2. Add a system-prompt file with the adapted system prompt
3. Document any framework-specific routing or tool call format differences
