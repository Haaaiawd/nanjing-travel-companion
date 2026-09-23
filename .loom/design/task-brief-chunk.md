# Devin Brief: 栖霞笔记 → Chunk 知识库 + 索引 + 上云

## 项目
Nanjing Travel Companion (`/home/haa/sites/nanjing-travel-companion`)

## 背景
`data/raw/notes/` 已有 15 条栖霞区真实笔记（b460_*），覆盖千佛岩/舍利塔/达摩古洞。
现在需要按 KNOWLEDGE.md 的 schema 转成 Chunk，构建索引，然后 commit + push。

## Chunk schema（严格遵守）
```json
{
  "chunk_id": "ck_{note_id}_{idx}",
  "source_note_id": "b460_xxx",
  "location": "栖霞山/千佛岩/舍利塔/达摩古洞（归一化）",
  "type": "POI|美食|路线|避坑|住宿|交通|其他",
  "content": "攻略片段，≤200字",
  "tags": ["秋天", "拍照", "交通"],
  "structured_data": {
    "locations": ["栖霞山"],
    "activities": ["徒步", "拍照"],
    "time_hint": "11月中旬-12月上旬",
    "food": ["梅花糕", "糖炒栗子"],
    "tips": ["早7点前入园免费"]
  },
  "source_ref": {
    "note_title": "原标题",
    "note_url": "https://b.460.net.cn/a/xxx.html",
    "image": "data/raw/images/xxx.jpg"
  },
  "confidence": 0.9,
  "created_at": "2026-09-23"
}
```

## 要求
1. 读取 `data/raw/notes/b460_*.json`，逐条提取攻略片段
2. 按 `type` 分类：POI/路线/交通/避坑/美食
3. `location` 归一化：栖霞山/千佛岩/舍利塔/达摩古洞
4. 生成 `data/processed/chunks.json`
5. 调用 `config.make_embedding_provider()` 生成 embedding
6. 构建 `data/index/embeddings.json` + `data/index/search_index.json`
7. 更新 `data/raw/HARVEST.md` 记录本次 chunk 化过程
8. 运行 `pytest` 确保测试通过
9. **必须 commit + push 到 origin master**

## 交付
- `data/processed/chunks.json`
- `data/index/embeddings.json`
- `data/index/search_index.json`
- `data/raw/HARVEST.md` updated
- git commit + push

```json
COMPLETION_NOTIFY
source: assistant
task: qixia-chunk-index
deliverables:
- data/processed/chunks.json
- data/index/embeddings.json
- data/index/search_index.json
- HARVEST.md updated
- tests passing
- committed and pushed
status: success
errors: none
```
