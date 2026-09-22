# Nanjing Travel Companion — System Design

## 架构概览

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  小红书 Scraper │────▶│  OCR/理解   │────▶│ 知识结构化   │
│  (图文笔记)     │     │ (文字+图片)  │     │ (chunks)     │
└─────────────┘     └─────────────┘     └──────┬───────┘
                                                  │
                                                  ▼
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  用户输入     │────▶│ 场景检索     │────▶│ Agent 生成   │
│ (语音/文字)  │     │ (向量 top-k) │     │ (对话式输出)  │
└─────────────┘     └─────────────┘     └──────────────┘
```

## 数据流

1. **采集**：Scraper 抓取小红书南京攻略笔记（图文）
2. **解析**：OCR 提取图片文字 + 视觉理解提取结构化信息
3. **索引**：生成 Chunk，Embedding，存入向量索引
4. **检索**：用户输入 → 场景检索 → top-k 相关攻略
5. **生成**：Agent 基于检索结果 + 人设，生成对话式回答

## 关键设计决策

### 1. 图文混合处理
- 小红书笔记 = 封面图 + 手帐排版图 + 文字描述
- **不依赖纯文字**：OCR 是必须的
- 图片理解优先级：通义千问 VL > PaddleOCR（手帐风需要视觉理解）

### 2. 场景化检索
- 不是全文搜索，而是「用户要去 X → 检索 X 相关攻略」
- 索引维度：POI + 场景类型 + 时间 + 标签
- 检索策略：余弦 top-k + 规则过滤（如「秋天」相关）

### 3. Agent 人设
- **看过攻略，但没去过南京** 的搭子
- 语气：热情、会种草、偶尔犹豫「这个我也没试过」
- 不是「旅游专家」，是「一起做攻略的伙伴」

### 4. MVP 边界
- 不做多轮规划（「帮我规划 3 天行程」）
- 只做单点问答（「明孝陵怎么玩？」）
- 不做实时信息（「今天明孝陵人多吗？」）

## 模块接口

### Scraper → OCR
```json
{
  "note_id": "xxx",
  "title": "南京7天6晚",
  "images": ["url1", "url2", ...],
  "text": "正文文字（如有）",
  "author": "xxx",
  "likes": 1234
}
```

### OCR → Knowledge
```json
{
  "chunk_id": "chunk_001",
  "source_note_id": "xxx",
  "location": "明孝陵",
  "type": "POI|美食|住宿|交通|避坑",
  "content": "结构化攻略文字",
  "media_refs": ["image_001.jpg"],
  "tags": ["秋天", "拍照"],
  "confidence": 0.9
}
```

### Knowledge → Agent
```json
{
  "query": "明孝陵怎么玩",
  "relevant_chunks": [
    {
      "content": "明孝陵石象路秋天超美...",
      "source": "小红书笔记 xxx",
      "relevance": 0.92
    }
  ],
  "context": "用户正在计划南京旅游..."
}
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Scraper | xiaohongshu-mcp / Playwright |
| OCR | 通义千问 VL + PaddleOCR |
| Embedding | 百炼 qwen3.7-text-embedding-flash |
| 向量库 | 本地 JSON + 余弦 top-k |
| Agent | Python + 百炼 LLM |
| 前端 | 暂缓，先做知识库 + Agent |

## 目录结构

```
nanjing-travel-companion/
├── .loom/
│   ├── PROJECT.md
│   ├── SYSTEM.md
│   ├── SCRAPER.md
│   ├── OCR.md
│   ├── KNOWLEDGE.md
│   ├── AGENT.md
│   └── tasks.json
├── data/
│   ├── raw/                    # 原始抓取数据
│   │   ├── notes/              # 笔记 JSON
│   │   └── images/             # 图片缓存
│   ├── processed/              # OCR 后结构化数据
│   │   ├── chunks.json
│   │   └── knowledge_graph.json
│   └── index/                  # 向量索引
│       ├── embeddings.json
│       └── search_index.json
├── src/
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── xhs_client.py       # 小红书 API/页面抓取
│   │   └── downloader.py       # 图片下载
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── vl_client.py        # 通义千问 VL
│   │   ├── paddle_ocr.py       # PaddleOCR 备用
│   │   └── chunker.py          # OCR 结果分块
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── schema.py           # Chunk / KnowledgeGraph 数据模型
│   │   ├── extractor.py        # 从 OCR 结果提取结构化信息
│   │   ├── indexer.py          # Embedding + 索引
│   │   └── retriever.py        # 场景检索
│   └── agent/
│       ├── __init__.py
│       ├── persona.py          # 搭子人设
│       ├── prompt.py           # Prompt 模板
│       └── companion.py        # Agent 核心逻辑
├── tests/
│   ├── test_scraper.py
│   ├── test_ocr.py
│   ├── test_knowledge.py
│   └── test_agent.py
├── .env.example
├── requirements.txt
└── README.md
```
