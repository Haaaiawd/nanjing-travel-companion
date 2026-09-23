# OCR / 多模态理解设计

## 职责

把 `data/raw/images/` 里的手帐风图片 + 笔记正文变成 `ChunkDraft` 列表。
核心判断：**小红书的攻略信息主要在图上，不在正文里** —— 所以视觉理解是主链路，
文字 OCR 是兜底。

## 管线

```
Note
 ├─ images[] ──▶ per-image 理解（缓存命中则跳过模型调用）
 │                ├─ VLClient.understand(image) ──▶ ImageInsight
 │                └─ 失败 → PaddleOCR.extract_text() ──▶ text-only 结构化
 ├─ text ──────▶ 笔记正文 chunk（type=text，若有信息量）
 └─ merge ────▶ ChunkDraft[]（每张有效图一条 + 正文一条）
```

## VL 理解（主链路）

- **Provider**：OpenAI 兼容端点。默认 AI Ping 平台 + `doubao-2.1-pro`
  （批量处理可切 `doubao-2.1-flash` 省钱），env 可换任意兼容服务。
- **请求形态**：`chat/completions`，message content 为
  `[{type:image_url,image_url:{url:"data:image/jpeg;base64,..."}},
    {type:text,text:PROMPT}]`。
- **Prompt 要点**：明确告知这是小红书旅游攻略手帐图，要求**只输出 JSON**：
  ```json
  {"locations": [], "activities": [], "time_hint": "", "food": [],
   "tips": [], "tags": [], "scene_type": "POI|美食|路线|避坑|住宿|交通|其他",
   "summary": "一句话讲这张图在推荐什么"}
  ```
- **解析**：宽容解析 —— 先找 ```json 代码块，再退化到首尾花括号切片；
  字段缺失填默认值；解析失败返回 `confidence=0` 的草稿而不是抛错
  （坏图不该阻塞整篇笔记）。

## 缓存策略

- key = 图片内容 `sha256`（不是文件名 —— 同图跨笔记复用是常态）。
- 落盘 `data/cache/ocr/{sha256}.json`，命中直接返回 `ImageInsight`。
- 缓存命中不进模型、不计失败；`OCRCache.stats()` 供管线汇报命中率。

## PaddleOCR 降级

- `paddle_fallback.py` 用**可选导入**：`import paddleocr` 失败时
  `PaddleFallback.available == False`，管线跳过该路径。绝不因此 break 构建。
- OCR 纯文本结果交给一个简单 `structure_text()`：正则/关键词把文本切成
  locations/activities/tips 草稿（降级产物质量低于 VL，`confidence` 打 0.5）。

## ChunkDraft 产出契约

```json
{
  "source_note_id": "xhs_abc123",
  "source_image": "data/raw/images/xhs_abc123_0.jpg",
  "location": "明孝陵",                // locations[0]，多 location 时拆多 chunk
  "type": "POI",
  "content": "summary + tips 拼成的自然语言段",
  "tags": ["秋天", "拍照"],
  "structured_data": {"locations": [...], "activities": [...],
                      "time_hint": "...", "food": [...], "tips": [...]},
  "confidence": 0.9
}
```

- 一张图识别出多个 location 时**按 location 拆 chunk**（各 chunk 共享
  structured_data，location 字段不同）——检索按 location 缩圈才准。
- `content` 是给 embedding 和 LLM 看的自然语言；`structured_data` 是给
  过滤和图谱看的字段。两者都保留。
- 笔记正文独立成 chunk（`source_image=null`，`type` 从关键词推断），
  保证纯文字笔记也能进库。

## 边界

- 不做图片质量过滤（模糊图 VL 自己会给出低 confidence）。
- 不做跨笔记内容去重（相似攻略是有效信号，检索层 top-k 自然消化）。
- 不写 knowledge 索引 —— 产出止步于 `data/processed/chunks.json`。
