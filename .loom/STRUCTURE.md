# Project structure

## Source code

`src/` 是按管线阶段划分的 Python 包（以 `src.<module>` 形式导入）：

- `src/config.py` — 环境变量集中读取（API key、模型名、路径常量），所有模块共用。
- `src/scraper/` — 小红书抓取：`xhs_client.py`（搜索/详情，限速+UA 轮换+cookies）、
  `downloader.py`（图片落盘）、`models.py`（Note 数据模型）。
- `src/ocr/` — 图片理解：`vl_client.py`（OpenAI 兼容视觉模型，默认走 AI Ping 的
  豆包 2.1 Pro/Flash）、`paddle_fallback.py`（本地 PaddleOCR 备用）、
  `pipeline.py`（笔记 → chunks 的编排）、`cache.py`（按图片内容 hash 缓存结果）。
- `src/knowledge/` — 知识库：`schema.py`（Chunk/KnowledgeGraph）、
  `embeddings.py`（百炼 embedding provider + 离线 hash 实现）、`indexer.py`
  （构建/读写本地 JSON 索引）、`retriever.py`（场景检索）、`graph.py`（POI 关系图）。
- `src/agent/` — 对话：`persona.py`（搭子人设 stable core）、`prompt.py`（PRISMIX
  三层组装）、`scenes.py`（场景识别与检索触发）、`llm.py`（OpenAI 兼容 chat client
  + mock）、`companion.py`（主流程编排）。

## Tests

`tests/` 平铺测试文件（`test_scraper.py` 等），不镜像 src 层级。全部测试离线运行，
外部服务用注入的 mock provider 替代。`tests/conftest.py` 负责把仓库根目录加入
sys.path 并提供共享 fixtures。

## Documents

`.loom/` 为 LOOM 状态与设计文档（`PROJECT.md` 是入口，`.loom/design/` 下是各模块
设计）。根目录 `README.md` 是给人看的快速上手文档。

## Configuration and build

- `requirements.txt` — 运行依赖（仅 requests；pytest 在 requirements-dev.txt）。
- `.env.example` — 所有外部服务配置项的模板。
- `pyproject.toml` — 只放 pytest 配置与项目元信息，不作打包用途。

## Assets and fixtures

`data/` 是全部数据资产：

- `data/raw/notes/` — scraper 产出的笔记 JSON（每篇一个文件）。
- `data/raw/images/` — 笔记图片，文件名 `{note_id}_{idx}.jpg`。
- `data/processed/` — `chunks.json`（OCR/理解产物）、`knowledge_graph.json`。
- `data/index/` — `embeddings.json`、`search_index.json`（倒排索引）。
- `data/mock/` — 手工编写的 mock 笔记与预生成 chunks，供离线开发与测试。
- `data/cache/ocr/` — 图片理解结果缓存（key = 图片内容 sha256）。
