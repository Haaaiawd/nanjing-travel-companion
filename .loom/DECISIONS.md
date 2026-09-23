# Decision History

Current truth belongs in PROJECT.md and linked design documents. This file preserves consequential superseding decisions.

## 2026-09-22 — 初始技术选型（基线决策）

- **统一 OpenAI 兼容传输**：VL（AI Ping 豆包 2.1 Pro/Flash）、LLM（百炼 qwen-turbo）、
  Embedding（百炼 qwen3.7-text-embedding-flash）全部走 OpenAI 兼容端点，同一套
  薄 client + provider 注入。替代旧设计中的 qwen-vl-max 专用路径 —— brief 指定
  AI Ping 豆包优先，且统一传输层让 mock/切换成本最低。
- **离线可测**：每个外部依赖都有本地 provider（HashEmbedding / MockVLClient /
  MockLLM / FixtureSource），测试零网络零 key。这是验收硬约束。
- **向量存储纯 JSON + 纯 Python 余弦**：demo 规模（数百 chunk）不引入 numpy
  或向量数据库；HashEmbedding 用 char-bigram 哈希保证测试语义可断言。
- **检索 = POI 别名缩圈 + 余弦排序 + 类型/季节硬过滤**：纯向量对
  「POI×类型」组合查询噪声大，结构化过滤先行。
- **Chunk 是唯一流通货币**：scraper→Note、ocr→ChunkDraft、knowledge→Chunk、
  agent→RetrievedChunk，模块单向依赖，经 data/ 文件解耦。
- **Keeper 跳过**：单 agent 从零构建，无前任 agent 可交接；keeper 无隔离环境
  可运行，已用 `loom keeper skip` 记录。
