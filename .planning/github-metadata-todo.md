# GitHub 元数据与发布清单

**agent 改不了，需要仓库主人在 GitHub 设置里或用自己的账号操作。**

最后核对：2026-09-18（数字由 `scripts/verify_all.py --d2` 的口径实测得出）

## About 描述 —— 待改

当前线上描述里的数字是旧的：

| | 描述现写 | 实际 |
|---|---|---|
| entities | 94 | **100** |
| constraints | 318 | **322** |

其余（69 chapters / 878 prompts / 9 skills）正确。README 里的同样数字有 `D2` 门禁盯着，仓库描述在 GitHub 设置里，门禁够不着；每次 ontology 增删后都要手动核一遍。

建议改成：

```
Cross-border e-commerce AI knowledge base, read by people and installed by agents: 69 trilingual guides, 878 prompts, a 100-entity / 322-constraint ontology, and 9 skills as a Claude Code plugin or over MCP. Factual claims are dated and CI-verified. CC0.
```

## Social Preview —— 文件已备好，待上传

`assets/social-preview.png`（1280×640，英文，数字与 D2 口径一致，2026-09-17 重绘）。
Settings → General → Social preview → Upload an image。
旧图写的是 56 篇、旧仓库名和 ACOS 35%→18% 一类仓库已不背书的数字，凡是贴出仓库链接的地方显示的都是它。

## 私密漏洞报告 —— 待启用

`SECURITY.md` 让报告人走 Security → Report a vulnerability。这个入口要在
Settings → Code security and analysis → Private vulnerability reporting 里打开，否则读者点进去看不到表单。

## Topics —— 已配置 19 个，建议调整

`.planning/launch/registries/github-topics.md` 按 GitHub 上各 topic 的仓库数给出了 20 个的建议集：
去掉 `amazon-seller-assistant`，加 `claude-code` 和 `model-context-protocol`（上限 20 个）。

## 主页 —— 已完成

已指向 https://kangise.github.io/ecommerce-ai-skills/

## README 排布 —— 已完成（2026-09-17）

`README.md` 现在是英文版（GitHub 默认渲染），中文在 `README_ZH.md`，日文在 `README_JA.md`。
首屏有 CI 徽章、真实截图（`assets/screenshots/`）和三行可直接跑的快速开始。

## 发布 —— 待办

远端只有 `v1.0.0`、`v1.1.0` 两个 tag，且 **Releases 页面是空的**。`pyproject.toml` 已到 `1.3.0`，
v1.2.0 与 v1.3.0 从未打过 tag。后果：`release.yml` 里的 PyPI 发布 job 绑在 `push: tags: ["v*"]`，从未被触发过；
包不在 PyPI 上，所有安装命令只能写 `git+https`，官方 MCP registry 的 `server.json` 也因此无法通过校验。

打 tag 之前要先做的一次性配置：

1. PyPI 上为本仓库注册 trusted publisher（workflow = `release.yml`，environment = `pypi`）
2. GitHub 的 `pypi` environment 里加必需审阅人 —— PyPI 上传不可撤销，一个版本号用掉就没了

两步做完再打 `v1.3.0`，整条发布链路才走得通。发完 PyPI 之后：README 里的安装命令可以缩成
`pip install "ecommerce-ai-skills[mcp]"`，`.planning/launch/registries/server.json` 可以直接用 `mcp-publisher` 发。

## 发布物料 —— 全部是草稿，一个都没发出去

`.planning/launch/` 下的内容由 agent 起草，**没有在任何地方发布、提交或开 PR**。每份文件末尾有发帖前检查项；
所有第一人称句子（"I built"、"我做了"）都要你自己确认属实再用。

| 文件 | 去处 | 你要做的 |
|---|---|---|
| `show-hn.md` | Hacker News | 自己发 Show HN，先搜一遍有没有人发过 |
| `reddit.md` | r/ecommerce · r/ClaudeAI · r/LocalLLaMA | 发前看各版当日的自荐规则 |
| `x-thread.md` | X | 8 条，字数已核 |
| `devto-article.md` | Dev.to | 1300 词，讲 CI 门禁抓到的 10 倍错误 |
| `zhihu.md` · `juejin.md` · `v2ex.md` | 知乎 · 掘金 · V2EX | 中文社区 |
| `zenn.md` · `qiita.md` | Zenn · Qiita | 日文社区 |
| `registries/awesome-mcp-servers.md` | punkpeye/awesome-mcp-servers | 用你的账号开 PR，条目文本已写好 |
| `registries/awesome-claude-code.md` | hesreallyhim/awesome-claude-code | 该仓库只收 issue 表单，字段值已填好 |
| `registries/mcp-registry.md` + `server.json` | 官方 MCP registry | 依赖 PyPI 发布 |
| `registries/glama-smithery-pulsemcp.md` | Glama / Smithery / PulseMCP | 三家都抓官方 registry；PulseMCP 目前暂停收录 |
| `good-first-issues.md` | 本仓库 Issues | 用 GitHub 建 issue 并打 `good first issue` 标签 |
