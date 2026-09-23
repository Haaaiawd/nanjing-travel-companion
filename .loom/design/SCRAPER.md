# Scraper 设计 — 小红书攻略抓取

## 职责

把小红书南京攻略笔记变成干净的本地素材：笔记 JSON 落 `data/raw/notes/`，
图片落 `data/raw/images/`。**只搬运，不理解** —— 内容语义是 ocr 模块的事。

## 数据源抽象：`NoteSource`

抓取渠道易变（反爬升级、账号封禁、工具换代），所以抓取入口定义为协议：

```python
class NoteSource(Protocol):
    def search(self, keyword: str, limit: int) -> list[str]: ...   # → note_ids
    def fetch_note(self, note_id: str) -> RawNote: ...             # → 原始 dict
```

三个实现：

| 实现 | 用途 | 说明 |
|------|------|------|
| `FixtureSource` | 测试/离线开发 | 从 `data/mock/notes/*.json` 读，支持关键词过滤 |
| `WebSource` | 真实抓取 | requests + cookies 打 web 端接口，内建反爬策略 |
| `MCPSource` | 备选 | 本地 xiaohongshu-mcp 服务（localhost:18060）若可用 |

`XhsScraper` 编排任意 source：`scrape(keywords) → Note → save_note() +
download_images()`。切换渠道不改编排代码。

## 反爬设计（WebSource 内建）

小红书风控维度：请求频率、UA 指纹、登录态、签名。对应策略：

1. **限速**：`RateLimiter(min_interval=2.0, jitter=1.5)` —— 每次请求前 sleep
   到 `min_interval + uniform(0, jitter)`，令牌消耗串行化。图片下载单独一个
   更宽松的 limiter。
2. **UA 轮换**：`UA_POOL` 内置若干真实桌面 Chrome/Safari UA，每请求随机取，
   同时附带匹配的 `Accept`/`Accept-Language`/`Referer` 头。
3. **Cookies**：从 env `XHS_COOKIES` 注入（用户手动从浏览器导出）。
   无 cookies 时 WebSource 仍可构造，但调用方应预期 403/登录墙。
4. **重试**：429/5xx → 指数退避（2s/4s/8s，最多 3 次）；明确 401/403 →
   抛 `AuthError` 提示换 cookies，不重试。
5. **幂等**：`note_id` 已存在于 `data/raw/notes/` 则跳过抓取；图片按
   `{note_id}_{idx}.jpg` 命名，已存在则跳过下载。

## 数据格式

### 落盘 Note（data/raw/notes/{note_id}.json）
```json
{
  "note_id": "xhs_abc123",
  "title": "南京3天2晚保姆级攻略",
  "author": "小熊软糖",
  "url": "https://www.xiaohongshu.com/explore/abc123",
  "images": ["data/raw/images/xhs_abc123_0.jpg", "..."],
  "text": "正文文字（可能很短）",
  "tags": ["南京旅游", "攻略", "明孝陵"],
  "likes": 2341,
  "created_at": "2026-08-15",
  "crawled_at": "2026-09-22T10:00:00"
}
```

`images` 存的是**本地相对路径**（下载完成后），不是原始 URL —— 下游 ocr 直接读盘。
原始 CDN URL 保留在 `image_urls` 字段备查。

### 关键词集（默认搜索计划）
`南京旅游攻略` `南京美食` `南京拍照` `明孝陵` `中山陵` `夫子庙` `老门东`
`玄武湖` `总统府` `南京秋天` —— 覆盖主要 POI + 场景词。

## 边界

- 不解析图片内容、不做 dedup 内容判断（同图不同笔记是合法重复，ocr 缓存处理）。
- 真实抓取不做验收；验收的是限速器行为、Note 序列化格式、下载器幂等、
  FixtureSource 驱动全流程。
