# Devin Brief: 南京旅游搭子知识库项目 — 从零构建

## 项目
Nanjing Travel Companion (`/home/haa/sites/nanjing-travel-companion`)

## 背景
我们要做一个基于小红书攻略知识库的对话式旅游伴侣 Agent。Agent 人设是：**看过攻略，但和用户一样没去过南京**的搭子。数据源主要是小红书南京攻略，特点是**图片为主、手帐风排版**，需要 OCR + 多模态理解提取结构化信息。

## 你的任务

### 1. 初始化 Loom 项目结构
- 运行 `loom init` 或按项目规范创建 `.loom/` 目录
- 创建 `tasks.json`，列出所有任务（至少包括 scraper、OCR、knowledge、agent 四大模块）
- 创建 `STRUCTURE.md`，定义代码目录结构
- 创建 `design/` 下的设计文档（你重新写，不要用现有的，按你理解重新设计）

### 2. 设计并实现 Scraper 模块
- 抓取小红书南京旅游攻略笔记（图文混合）
- **关键**：小红书反爬强，需要限速、随机 UA、cookies 策略
- 图片下载到 `data/raw/images/`
- 笔记元数据保存到 `data/raw/notes/`
- **输出格式**：JSON，包含 note_id、title、images、text、tags、likes、created_at

### 3. 设计并实现 OCR/多模态理解模块
- **重要**：小红书笔记主要是**手帐风图片**，不是纯文字
- OCR 流程：
  1. 图片 → 多模态模型识别（优先用 AI Ping 平台的豆包 2.1 Pro/Flash，或其他你推荐的视觉模型）
  2. 提取结构化信息：POI、活动、时间、美食、贴士、标签
  3. 输出结构化 JSON（chunk 格式）
- 备用 OCR：PaddleOCR（本地，中文手写体）
- 图片缓存策略：避免重复处理

### 4. 设计并实现 Knowledge 模块
- Chunk 数据结构：location、type、content、tags、structured_data、source_ref
- Embedding：百炼 qwen3.7-text-embedding-flash
- 向量索引：本地 JSON + 余弦 top-k
- 场景检索：支持 POI 查询、场景类型过滤、时间维度
- 轻量 KnowledgeGraph：POI 关系（nearby、tags 关联）

### 5. 设计并实现 Agent 模块
- **人设**：看过攻略、但和用户一样没去过南京的搭子
  - 语气：热情、会种草、会说「这个我也没试过，看着不错」
  - 不是旅游专家，是「一起做攻略的伙伴」
- Prompt 设计：PRISMIX 三层结构
  - stable core：搭子人设
  - environment adaptation：知识库检索注入
  - capability modules：场景化检索触发
- 对话流程：用户输入 → 场景检索 → 注入知识 → 生成回答

### 6. 创建 Mock 数据
- 先不用真实抓取，创建 5–10 条 mock 攻略数据
- 覆盖主要 POI：明孝陵、夫子庙、老门东、玄武湖、总统府
- 每条包含：location、type、content、tags、structured_data

### 7. 测试
- scraper：mock 抓取测试
- ocr：mock 图片理解测试
- knowledge：chunk 创建、embedding、检索测试
- agent：人设测试、知识注入测试

## 技术选型参考
- **AI Ping 平台**：豆包 2.1 Pro / 豆包 2.1 Flash（多模态，图片→文字/结构化）
- **Embedding**：百炼 qwen3.7-text-embedding-flash
- **LLM**：百炼 qwen-turbo / qwen-flash
- **向量库**：本地 JSON + 余弦 top-k（Demo 阶段）
- **语言**：Python

## 关键约束
- **独立项目**，不要和 Paimon 混代码
- 先做知识库 + Agent，前端暂缓
- MVP 只做单点问答（「明孝陵怎么玩？」），不做多日行程规划
- 知识注入要自然，不要让 Agent 变成「百科全书式回答」

## 完成后
执行 COMPLETION_NOTIFY。

---
## COMPLETION_NOTIFY
source: assistant
task: nanjing-companion-init
deliverables:
- Loom project structure
- scraper/ocr/knowledge/agent modules
- mock data
- tests passing
status: success
errors: none
---
