# 系统架构

## 全景

```
            离线知识构建管线                            在线问答
┌──────────┐   ┌──────────┐   ┌───────────┐
│ scraper  │──▶│   ocr    │──▶│ knowledge │
│ XHS 图文  │   │ VL 理解   │   │ chunk+索引 │
└──────────┘   └──────────┘   └─────┬─────┘
                                    │ retrieve(query, scene)
                              ┌─────▼─────┐   ┌──────────┐
              用户输入 ──────▶│   agent   │──▶│   LLM    │
                              │ 场景识别    │   │ qwen 系列 │
                              └───────────┘   └──────────┘
```

两条管线共享 chunk schema，通过 `data/` 下的 JSON 文件解耦 —— 离线管线可以在
没有用户的情况下跑，在线侧只需要 `data/index/` 已构建。

## 关键设计决策

### D1 统一的 OpenAI 兼容传输层
VL（豆包 2.1 via AI Ping）、LLM（qwen-turbo via 百炼）、Embedding
（qwen3.7-text-embedding-flash via 百炼）都走 `POST {base_url}/chat/completions`
或 `/embeddings`。每个模块只持有一个薄 client + 一个可注入的 provider 接口。
理由：三家用同一套鉴权/重试/错误处理；mock 时换掉 provider 即可，测试零网络。

### D2 离线优先的 provider 注入
每个外部依赖都有「真实实现 + 本地实现」：

| 依赖 | 真实 | 本地/测试 |
|------|------|-----------|
| VL 理解 | `VLClient`（AI Ping 豆包） | `MockVLUClient`（按文件名查表返回） |
| Embedding | `DashScopeEmbedding` | `HashEmbedding`（char-bigram 哈希向量） |
| LLM | `ChatClient`（百炼 qwen-turbo） | `MockLLM`（模板化搭子口吻回复） |
| XHS | `WebSource` / `MCPSource` | `FixtureSource`（读 data/mock/notes） |

`config.py` 根据 env 是否配置了 key 自动选择，也可显式注入。整条管线在无任何
API key 的机器上可跑通、可测试。

### D3 Chunk 是唯一流通货币
scraper 产 `Note`，ocr 产 `ChunkDraft`，knowledge 存 `Chunk`，agent 读
`RetrievedChunk`。字段向后兼容地增长，但 `location/type/content/tags/
structured_data/source_ref` 是契约核心（见 KNOWLEDGE.md）。

### D4 检索 = 向量召回 + 结构化约束
纯向量检索在「夫子庙美食」这种 POI×类型组合查询上噪声大。retriever 先做
POI 别名精确匹配（知识图谱提供别名表）+ 类型/tag 过滤缩圈，再在圈内做
余弦排序；无 POI 命中时退化为全库余弦 top-k。

### D5 知识注入克制原则
检索结果注入 prompt 时附带明确指令：「挑 1–2 个最相关的点用自己的话说」。
宁可少说不漏搭子人设，不允许把 chunk 列表倾倒给用户。

## 模块间契约

### Note（scraper → 文件系统）
```json
{
  "note_id": "xhs_abc123",
  "title": "南京3天2晚保姆级攻略",
  "author": "小熊软糖",
  "url": "https://www.xiaohongshu.com/explore/abc123",
  "images": ["data/raw/images/xhs_abc123_0.jpg"],
  "text": "正文文字",
  "tags": ["南京旅游", "攻略"],
  "likes": 2341,
  "created_at": "2026-08-15",
  "crawled_at": "2026-09-22T10:00:00"
}
```

### ChunkDraft（ocr → knowledge）
```json
{
  "source_note_id": "xhs_abc123",
  "source_image": "data/raw/images/xhs_abc123_0.jpg",
  "location": "明孝陵",
  "type": "POI",
  "content": "石象路秋天封神，10月中下旬银杏全黄，8点前到没人",
  "tags": ["秋天", "拍照", "清晨"],
  "structured_data": {"locations": ["明孝陵","石象路"], "activities": ["拍照"],
                      "time_hint": "10月中下旬/清晨", "food": [], "tips": ["8点前到"]},
  "confidence": 0.9
}
```

### RetrievedChunk（knowledge → agent）
```json
{"chunk_id": "ck_xhs_abc123_0", "content": "...", "location": "明孝陵",
 "type": "POI", "tags": ["..."], "score": 0.83, "source_ref": {...}}
```

## 失败与降级

- VL API 失败 → 记 warning，尝试 PaddleOCR → 仍失败则跳过该图（笔记文字仍可成 chunk）。
- Embedding API 失败 → indexer 报错退出（索引必须完整，不接受半残索引）。
- 检索结果为空 → agent 收到空知识块，prompt 指示其承认「没刷到相关攻略」。
- LLM 失败 → 抛出带上下文错误，不静默兜底。

## 目录与运行入口

结构见 `.loom/STRUCTURE.md`。运行入口：
- `scripts/seed_index.py` — 从 data/mock 或 data/processed 构建索引。
- `scripts/chat.py` — CLI 单轮/多轮问答 demo。
