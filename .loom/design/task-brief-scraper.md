# Devin Brief: 小红书真搜索 + 开源方案接入

## 项目
Nanjing Travel Companion (`/home/haa/sites/nanjing-travel-companion`)

## 背景
当前 `src/scraper/xhs_client.py` 只有本地 keyword→note_id 种子文件，没有真搜索。我们需要从真实小红书数据中抓取南京旅游攻略，给知识库提供素材。

## 你的任务

### 1. 调研开源小红书爬虫/搜索方案
- 搜索 GitHub 上近期可用的开源项目（如小红书 API 逆向、Playwright 方案、MCP server 等）
- 评估：是否需要 cookies、JS 签名难度、图片下载能力、稳定性
- 把调研结论写入 `.loom/design/SCRAPER.md`

### 2. 改造 `src/scraper/xhs_client.py`
- 目标：实现**真实搜索**，能按关键词搜索小红书南京旅游笔记
- 优先使用调研中**最可行**的开源方案
- 如果纯 HTTP 不可行，切换到 Playwright + 用户提供的 cookies
- 保持现有数据模型（`Note` / `ImageRef`）不变
- 添加 rate limiting（2 秒/请求）

### 3. 图片下载
- 实现 `src/scraper/downloader.py`：批量下载笔记图片到 `data/raw/images/`
- 缓存策略：已下载的图片不重复下载
- 错误处理：404/超时/重试

### 4. 真实数据抓取
- 用 3–5 个关键词搜索南京旅游（如「南京旅游攻略」「明孝陵」「夫子庙美食」等）
- 每个关键词抓取前 10–20 篇
- 保存到 `data/raw/notes/` 和 `data/raw/images/`
- **不要抓取太多**，先验证流程可行

### 5. 更新 Mock 数据
- 基于抓取到的真实笔记，更新 `data/mock/notes/` 中的 mock 数据
- 至少保证 5 篇有真实参考的 mock 笔记

### 6. 测试
- 更新 `tests/test_scraper.py`：加入真实搜索测试（如果环境允许）
- 保持现有测试通过

## 约束
- **不要动** `src/ocr/` `src/knowledge/` `src/agent/`
- 只改 `src/scraper/` 和 `data/raw/`
- 保持现有 `Note` / `ImageRef` 数据模型
- 如果调研发现没有稳定方案，报告结论，不要硬写一个脆弱的 scraper

## 完成后
执行 COMPLETION_NOTIFY。

---
## COMPLETION_NOTIFY
source: assistant
task: scraper-real-search
deliverables:
- .loom/design/SCRAPER.md updated with research findings
- src/scraper/xhs_client.py with real search
- src/scraper/downloader.py implemented
- data/raw/ populated with real notes/images
- tests updated
status: success
errors: none
---
