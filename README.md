# 南京旅游搭子 Nanjing Travel Companion

基于小红书攻略知识库的对话式旅游伴侣。人设：**看过一堆攻略、但和你一样没去过南京**的搭子 —— 会种草、会犹豫、绝不装导游。

```
小红书图文 → scraper → 多模态理解(豆包VL/PaddleOCR) → chunk 知识库
                                                        ↓
你的问题 → 场景识别 → 向量+结构化检索 → PRISMIX 三层 prompt → 搭子回答
```

## 快速开始（离线可跑）

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/seed_index.py     # 用 mock chunks 构建索引
.venv/bin/python scripts/chat.py           # CLI 对话（无 key 时用 MockLLM）
.venv/bin/python -m pytest                 # 29 个测试，全离线
```

## 接入真实服务

复制 `.env.example` 为 `.env`：

| 变量 | 用途 |
|------|------|
| `DASHSCOPE_API_KEY` | 百炼：LLM(qwen-turbo) + embedding(qwen3.7-text-embedding-flash) |
| `VL_API_KEY` / `VL_BASE_URL` / `VL_MODEL` | 视觉理解，默认 AI Ping + doubao-2.1-pro |
| `XHS_COOKIES` | 小红书登录态（真实抓取用） |

不配 key 时整条管线自动切本地 provider（HashEmbedding / MockLLM / FixtureSource），
行为确定、可测试。

## 目录

- `src/scraper` — 小红书抓取（限速/UA轮换/cookies，数据源可插拔）
- `src/ocr` — 手帐图理解（VL 主链路 + PaddleOCR 降级 + sha256 缓存）
- `src/knowledge` — chunk schema、embedding、JSON 向量索引、POI 图谱、场景检索
- `src/agent` — 搭子人设、PRISMIX 三层 prompt、对话编排
- `data/` — raw 素材 / processed chunks / index / mock 数据 / OCR 缓存
- `.loom/` — LOOM 项目状态与设计文档（`.loom/design/`）

设计细节见 `.loom/design/`（SYSTEM 是架构总览）。
