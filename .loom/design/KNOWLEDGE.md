# Knowledge 设计 — chunk 库、索引与场景检索

## 职责

知识库是 chunk 的「主人」：定义 schema、构建/加载向量索引、回答
「和这个问题最相关的攻略片段是什么」、维护 POI 关系图。

## Chunk schema（契约核心）

```json
{
  "chunk_id": "ck_xhs_abc123_0",
  "source_note_id": "xhs_abc123",
  "location": "明孝陵",
  "type": "POI",
  "content": "石象路秋天封神，10月中下旬银杏全黄，建议8点前到避开人流",
  "tags": ["秋天", "拍照", "清晨"],
  "structured_data": {
    "locations": ["明孝陵", "石象路"],
    "activities": ["拍照", "散步"],
    "time_hint": "10月中下旬/清晨",
    "food": [],
    "tips": ["8点前到避开人流"]
  },
  "source_ref": {"note_title": "南京3天2晚保姆级攻略", "note_url": "...",
                 "image": "data/raw/images/xhs_abc123_0.jpg"},
  "confidence": 0.9,
  "created_at": "2026-09-22"
}
```

- `type` 枚举：`POI | 美食 | 路线 | 避坑 | 住宿 | 交通 | 其他`。
- `chunk_id` 由 pipeline 确定性生成（`ck_{note_id}_{img_idx}` / 正文用 `_text`），
  重复构建索引时 id 稳定，方便幂等更新。
- embedding 文本 = `location + " " + type + " " + " ".join(tags) + " " + content`
  —— 结构化字段先拍平进文本，向量模型才能感知 POI 名。

## Embedding：`EmbeddingProvider` 协议

```python
class EmbeddingProvider(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

| 实现 | 场景 |
|------|------|
| `DashScopeEmbedding` | 真实：`{DASHSCOPE_BASE_URL}/embeddings`，model=`qwen3.7-text-embedding-flash` |
| `HashEmbedding` | 离线/测试：char unigram+bigram → `sha256(token) % dim` 桶计数 → L2 归一 |

`HashEmbedding` 对中文足够「有区分度」——共享子串（「明孝陵」）天然产生高余弦，
测试断言排序时有真实语义而非随机。`config.make_embedding_provider()` 按有无
`DASHSCOPE_API_KEY` 自动选。

## 索引与存储

```
data/processed/chunks.json        # Chunk[] 全量
data/index/embeddings.json        # {chunk_id: [float...]}
data/index/search_index.json      # {"by_location": {loc: [ids]}, "by_type": {...}, "by_tag": {...}}
```

- `indexer.build(chunks)` 一次成型：embedding 批量请求 → 写三个文件。
- `indexer.load()` 返回 `Index(chunks, vectors, inverted)` 纯内存结构；
  数百 chunk 暴力扫描是毫秒级，不引入任何向量库依赖。
- 更新策略：整库重建（demo 规模下增量索引不值得复杂度）。

## 场景检索：`retriever.retrieve`

```python
def retrieve(query: str, *, top_k=5, type=None, season=None) -> list[RetrievedChunk]
```

三步：

1. **POI 命中**：用 KnowledgeGraph 的别名表（「明孝陵」「石象路」「梅花山」→ 明孝陵）
   扫描 query；命中 → 候选 = `by_location[poi]`，且该 POI 命中的 chunk 分数 ×1.15 加权。
2. **过滤**：`type`（美食/避坑…）、`season`（匹配 tags 或 time_hint 中的季节词）
   在候选集上做硬过滤；无 POI 命中时候选 = 全库。
3. **排序**：query embedding 对候选做余弦 top-k，返回 `RetrievedChunk(score)`。

知识图扩展：检索结果可附带 `nearby` POI（如查明孝陵带回「中山陵也在旁边」），
由 agent 决定是否提一嘴 —— 知识层只供料，不替 agent 说话。

## KnowledgeGraph（轻量）

```json
{
  "locations": {
    "明孝陵": {"aliases": ["石象路", "梅花山"], "nearby": ["中山陵", "美龄宫"],
               "tags": ["秋天", "历史"], "chunk_ids": ["ck_..."]}
  }
}
```

- `nearby` 来源：(a) 人工种子表（mock 阶段主力）+ (b) 同笔记 co-occurrence 统计。
- `graph.py` 从 chunks + 种子 `POI_SEED` 构建；别名表同时服务检索归一化
  （query 里的「石象路」应命中明孝陵 chunk）。

## 边界

- 不持久化对话历史、不做用户画像 —— agent 的事。
- 不做实时更新接口；索引是构建产物，改数据就重建。
- 检索质量验收只看 mock 数据集上的排序正确性，不承诺真实语料效果。
