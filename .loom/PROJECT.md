# Project Whole and Document Map

## Intended result

一个可运行的「南京旅游搭子」对话式 Agent MVP：用户问「明孝陵怎么玩？」这类单点问题，
Agent 以一个**看过小红书攻略、但自己也没去过南京**的搭子口吻，结合知识库检索到的攻略
片段给出口语化回答。背后是完整的离线管线：小红书图文抓取 → 多模态图片理解 → 结构化
攻略 chunk → 本地向量索引 → 场景化检索 → 注入 Agent prompt。

## People and operating reality

- 使用者：计划去南京旅游、喜欢小红书攻略风格信息的用户。
- 开发者：本项目独立维护，不复用 Paimon 代码库，只借鉴其 PRISMIX prompt 分层等经验。
- 运行环境：本地 Python 3.12，无外部服务依赖即可跑通 mock 管线；真实抓取/模型调用
  依赖 env 中的 API key（百炼、AI Ping）与小红书 cookies。

## Whole experience or behavior

用户输入自然语言问题 → Agent 识别场景（POI / 美食 / 避坑等）→ 检索 top-k 相关攻略
chunk → 以搭子口吻生成回答，会说「这个我也没试过，看着不错」，而不是百科全书式罗列。
知识库离线构建：抓取到的手帐风图片笔记经多模态模型理解后切成 chunk，embedding 存入
本地 JSON 索引，每日批量更新即可，不追求实时。

## Boundaries and consequential assumptions

- 独立项目：不向 Paimon 仓库写代码，不引入其包。
- MVP 只做**单点问答**，不做多日行程规划、不做实时人流/营业状态查询。
- 前端暂缓：交付物是 CLI 可调用的 Agent 管线，不是 Web UI。
- 小红书反爬是事实约束：限速 + UA 轮换 + cookies 注入是 scraper 的内建能力，但实际
  抓取稳定性依赖用户提供的有效 cookies；MVP 阶段以 mock 数据驱动。
- 知识注入必须「自然」：prompt 层明确要求 Agent 不得逐条复述攻略，只允许挑 1-2 个
  相关点揉进对话。
- 测试必须离线可跑：所有外部 API（VL / embedding / LLM / XHS）都有可注入的 mock
  实现，CI 不需要真实 key。

## Design document map

- `design/PROJECT.md` — 产品定位、人设定义、MVP 范围与差异化。
- `design/SYSTEM.md` — 端到端架构、数据流、模块间契约（JSON schema）。
- `design/SCRAPER.md` — 小红书抓取策略、反爬设计、原始数据格式。
- `design/OCR.md` — 手帐图多模态理解管线、降级链、缓存策略、chunk 产出契约。
- `design/KNOWLEDGE.md` — Chunk/索引/检索/KnowledgeGraph 数据结构与算法。
- `design/AGENT.md` — 搭子人设、PRISMIX 三层 prompt、场景检索触发规则。
- `design/task-brief-init.md` — 原始任务书（存档，不作设计依据）。

## Professional capability map

暂无独立 capability dossier。涉及的专业域（爬虫反爬、中文 OCR、RAG 检索）已在对应
design 文档内以决策形式记录；若后续某域复杂度上升再拆分为 capability。
