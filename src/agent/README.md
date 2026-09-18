# Agent 接入

`dist/` 是这个仓库的 agent 能力包：9 个 skill、领域 ontology、Prompt 库和 MCP Server，与站点上的章节出自同一份源，经过同一套 CI 门禁。下面三种接入方式任选其一。

## Claude Code

两条命令安装 9 个 skill，不需要 Python 环境：

```
/plugin marketplace add kangise/ecommerce-ai-skills
/plugin install ecommerce-ai-skills@ecommerce-ai-skills
```

常驻上下文的只有各 skill 的名称和描述，正文、平台约束和 Prompt 集在用到时才加载。

## Claude Desktop / Cursor（MCP）

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

MCP Server 提供 8 个 resource 和 5 个工具；连接到运行中的 Commerce Agent OS 后，另有 4 个只读运营工具。详见 [MCP 接入说明](https://github.com/kangise/ecommerce-ai-skills/blob/main/integration/mcp.md)。

## 直接加载文件

不使用 Claude Code 或 MCP 的 agent，可以直接读取 [`dist/SKILL.md`](https://github.com/kangise/ecommerce-ai-skills/blob/main/dist/SKILL.md)：它是 agent 的入口，包含把请求路由到各 skill 的规则。完整目录见 [`dist/`](https://github.com/kangise/ecommerce-ai-skills/tree/main/dist)。

## 包里有什么

| 层 | 内容 | 给谁 |
|---|---|---|
| 知识库 | 69 章，中英日三语 | 人读 · agent 检索 |
| Ontology | 100 实体 · 322 约束 | agent 之间的共享契约 |
| Skills | 9 个可安装 skill · 878 条 Prompt | agent 直接调用 |

## 验证

在仓库根目录运行：

```bash
python3 scripts/verify_all.py   # 所有门禁
python3 scripts/build_dist.py   # 构建 dist/
```
