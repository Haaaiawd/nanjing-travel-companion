# 知识库设计

## 目标
将抓取+OCR 后的攻略片段，构造成可检索的知识库，支持场景化查询。

## 核心数据结构

### Chunk（攻略片段）
最小知识单元，对应一篇笔记中的一个信息点。

```json
{
  "chunk_id": "chunk_001",
  "source_note_id": "note_abc123",
  "location": "明孝陵",
  "type": "POI|美食|住宿|交通|避坑|路线|贴士",
  "content": "明孝陵石象路秋天超美，10月中下旬最佳...",
  "tags": ["秋天", "拍照", "石象路", "清晨"],
  "structured_data": {
    "locations": ["明孝陵", "石象路"],
    "activities": ["拍照"],
    "time": "10月中下旬",
    "tips": ["早上8点前到避开人流"]
  },
  "source_ref": {
    "note_title": "南京7天6晚超详细攻略",
    "note_url": "https://...",
    "image_refs": ["note_001_img_003.jpg"]
  },
  "confidence": 0.9,
  "created_at": "2026-09-22"
}
```

### KnowledgeGraph（轻量）
不需要完整知识图谱，只需要 POI 之间的关系索引。

```json
{
  "locations": {
    "明孝陵": {
      "nearby": ["中山陵", "音乐台"],
      "type": "POI",
      "tags": ["秋天", "拍照", "历史"],
      "chunk_ids": ["chunk_001", "chunk_005"]
    },
    "夫子庙": {
      "nearby": ["老门东", "秦淮河"],
      "type": "POI",
      "tags": ["夜景", "美食", "商业化"],
      "chunk_ids": ["chunk_002", "chunk_007"]
    }
  }
}
```

## 索引策略

### 向量索引
- Embedding 模型：百炼 qwen3.7-text-embedding-flash
- 索引维度：chunk.content + chunk.tags + chunk.location
- 检索方式：余弦相似度 top-k
- 本地存储：JSON 文件（Demo 阶段）

### 场景检索
```python
def retrieve(query: str, top_k: int = 5) -> List[Chunk]:
    """
    场景化检索：
    1. 提取 query 中的 POI / 场景关键词
    2. 向量检索 top-k 相关 chunks
    3. 规则过滤（如时间、场景类型）
    4. 返回相关度排序的结果
    """
```

### 检索场景示例
- 用户问「明孝陵怎么玩」→ 检索明孝陵相关 POI chunks
- 用户问「南京秋天去哪」→ 检索 tags 含「秋天」的 chunks
- 用户问「南京美食」→ 检索 type=美食 的 chunks

## 存储格式

### 本地存储（Demo）
```
data/
├── processed/
│   ├── chunks.json          # 所有 chunks
│   └── knowledge_graph.json # POI 关系图
└── index/
    ├── embeddings.json      # chunk_id -> vector
    └── search_index.json    # 倒排索引（location -> chunk_ids）
```

### 写入流程
```
OCR 结果 → extractor → Chunk → indexer → embeddings.json + search_index.json
```

## 更新策略
- 初始：批量导入（50–100 篇笔记）
- 增量：新抓取的笔记 → OCR → 追加到 chunks.json → 更新索引
- 不需要实时更新，每日批量即可
