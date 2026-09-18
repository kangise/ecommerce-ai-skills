# Agent 統合

`dist/` はこのリポジトリの agent 向けパッケージです。9 個の skill、ドメイン ontology、プロンプト集、MCP Server を含み、このサイトの各章と同じソースから生成され、同じ CI ゲートを通っています。接続方法は次の 3 つから選べます。

## Claude Code

2 つのコマンドで 9 個の skill をインストールできます。Python 環境は不要です。

```
/plugin marketplace add kangise/ecommerce-ai-skills
/plugin install ecommerce-ai-skills@ecommerce-ai-skills
```

常駐するのは各 skill の名前と説明だけで、本文・プラットフォーム制約・プロンプト集は使うときに読み込まれます。

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

MCP Server は 8 個の resource と 5 個のツールを提供し、稼働中の Commerce Agent OS に接続すると読み取り専用の運用ツールが 4 個追加されます。詳しくは [MCP 連携ガイド](https://github.com/kangise/ecommerce-ai-skills/blob/main/integration/mcp.md) を参照してください。

## ファイルを直接読み込む

Claude Code も MCP も使わない agent は、[`dist/SKILL.md`](https://github.com/kangise/ecommerce-ai-skills/blob/main/dist/SKILL.md) を読み込んでください。agent の入口で、リクエストを各 skill に振り分けるルールを含みます。パッケージ全体は [`dist/`](https://github.com/kangise/ecommerce-ai-skills/tree/main/dist) にあります。

## 中身

| 層 | 内容 | 対象 |
|---|---|---|
| ナレッジベース | 69 章、中・英・日の 3 言語 | 人が読む · agent が検索 |
| Ontology | 100 エンティティ · 322 制約 | agent 間で共有する契約 |
| Skills | インストール可能な 9 個の skill · 878 プロンプト | agent が直接呼び出す |

## 検証

リポジトリのルートで実行します。

```bash
python3 scripts/verify_all.py   # すべてのゲート
python3 scripts/build_dist.py   # dist/ をビルド
```
