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
| `MCPSource` | **真实抓取主路径** | 本机已部署的 xiaohongshu-mcp（:18060）HTTP API；登录后真搜索 |
| `WebSource` | 窄路径 | requests + cookies 抓详情页（无真搜索），保留 |

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
  "images": ["/abs/path/data/raw/images/xhs_abc123_0.jpg", "..."],
  "text": "正文文字（可能很短）",
  "tags": ["南京旅游", "攻略", "明孝陵"],
  "likes": 2341,
  "created_at": "2026-08-15",
  "crawled_at": "2026-09-22T10:00:00"
}
```

`images` 存的是**本地绝对路径**（下载完成后），不是原始 URL —— 下游 ocr 直接读盘，
绝对路径不受调用方 cwd 影响。原始 CDN URL 保留在 `image_urls` 字段备查。

### 关键词集（默认搜索计划）
`南京旅游攻略` `南京美食` `南京拍照` `明孝陵` `中山陵` `夫子庙` `老门东`
`玄武湖` `总统府` `南京秋天` —— 覆盖主要 POI + 场景词。

## 边界

- 不解析图片内容、不做 dedup 内容判断（同图不同笔记是合法重复，ocr 缓存处理）。
- 真实抓取不做验收；验收的是限速器行为、Note 序列化格式、下载器幂等、
  FixtureSource 驱动全流程。

## 开源方案调研（2026-09，全部实测验证）

候选方案评估：

| 方案 | 原理 | cookies | 签名难度 | 结论 |
|------|------|---------|----------|------|
| **xpzouying/xiaohongshu-mcp** | go-rod 驱动真实 Chrome，XHS 自己的 JS 完成签名 | 扫码一次，服务端持久化 | 不需要管 | ✅ **已部署**（:18060, v2.5.0, docker 3 周），首选 |
| 纯 requests + cookies | 直打 web 端点 | 需要 | X-S/X-T/X-S-common 由混淆 JS 生成 | ❌ 数据中心 IP 只拿到 stub/登录墙，实测 |
| Playwright 自研 | 同 MCP 思路 | 需要 | 不需要管 | 可行但重复造轮子，MCP 已覆盖 |
| MediaCrawler | playwright + 签名注入 | 需要 | 内置 | 可行，体量远大于需求 |
| 搜索引擎 → note_id → 详情 | bing/baidu 索引 note URL | — | — | ❌ 实测 bing 无索引；且 detail 需要 xsec_token，搜索引擎拿不到 |
| 第三方解析站（6li6 等） | 镜像他人抓取结果 | — | — | ❌ 抓「抓的抓」，脆弱且灰色 |

### 实测结果（本机，数据中心 IP，未登录）

| 通道 | 结果 |
|------|------|
| `GET www.xiaohongshu.com/explore`（匿名） | 302 → 登录页，无 `__INITIAL_STATE__` 数据 |
| `GET /search_result?keyword=`（匿名） | 200 但 `search.feeds=[]`、`user.loggedIn=false` |
| `GET /explore/{note_id}`（匿名） | 200 但 `noteDetailMap={}` |
| MCP `GET /api/v1/feeds/list` | ✅ **免登录**，~27 条首页推荐（泛内容，带 xsecToken） |
| MCP `POST /api/v1/feeds/detail` | ✅ **免登录**（需 feed 的 xsecToken），完整 title/desc/imageList/互动数 |
| MCP `GET /api/v1/feeds/search` | ❌ 未登录返回空 feeds |
| 页内签名 `_webmsxyw` + `edith …/search/notes` | ❌ 签名被接受但 `-104 无权限`（搜索对游客关闭） |
| 页内签名 `…/homefeed` 手搓调用 | ❌ 461（需要完整 x-s-common 会话态，不值得复刻） |
| MCP `POST /api/v1/user/profile` | ❌ 需用户主页级 xsec_token，拿不到 |
| CDP 劫持 MCP 的浏览器换频道页 | 可行但浏览器按调用生灭，竞态不可用 |

### 结论与选型

**关键词真搜索 = 必须登录**。小红书对游客关闭搜索 API，任何不登录的
「真搜索」都是幻觉。选定路径：

1. **主路径 `MCPSource`**：对接本机已部署的 xiaohongshu-mcp HTTP API
   （`GET /api/v1/feeds/search`、`POST /api/v1/feeds/detail`、
   `GET /api/v1/feeds/list`、`GET /api/v1/login/status`）。
   用户扫码一次（`GET /api/v1/login/qrcode` 返回 4 分钟有效 PNG）后
   cookies 持久化在容器卷 `/home/haa/xiaohongshu-mcp/data/cookies.json`。
2. **游客降级**：未登录时 `feeds/list` + `feeds/detail` 仍可用——
   首页推荐流真实笔记可抓，用于验证管线；拿不到定向关键词结果。
3. `WebSource` 保留为「有 cookies 时抓详情页」的窄路径；搜索仍需签名，不实装。

### MCP API 关键形态（v2.5.0）

- `GET /api/v1/feeds/search?keyword=X` → `{success, data:{feeds:[{id, xsecToken, noteCard:{displayTitle,user,interactInfo,cover}}], count}}`
- `POST /api/v1/feeds/detail` `{feed_id, xsec_token, load_all_comments:false}` →
  `{data:{data:{note:{noteId,title,desc,time(ms),user,interactInfo,imageList[{urlDefault,urlPre}]}, comments}}}`
- `xsecToken` 按笔记发放、detail 必带；search/list 结果是唯一可靠来源。
- `imageList[].urlDefault` 是 `sns-webpic-qc.xhscdn.com` CDN 地址，带时效参数，
  需尽快下载；实测 CDN 无鉴权，纯 GET 可拉。

### 追加实测（2026-09-23，栖霞区定向采集）

| 通道 | 结果 |
|------|------|
| `POST /api/v1/user/profile` `{user_id, xsec_token}` | ✅ **游客态可用**——token 是用户级（XHS 笔记内 @提及锚点上带的 token 即用户 token）。返回 userBasicInfo + feeds[noteCard]，但 **note id 被置空**（游客响应剥离 id/modelType，只剩封面/标题/互动数） |
| `feeds/detail` 用他笔记/用户 token | ❌ 500——xsec_token 严格按资源绑定 |
| 6li6 `/q?w=` 站内搜 | ❌ 只索引 bilibili 分区，xiaohongshu 分区无搜索 |
| 6li6 list/archive 全量扫描（~7600 页） | ❌ 栖霞相关内容近零；该站 XHS 笔记为「用户解析驱动」，无主题覆盖保证 |
| **b.460.net.cn**（江苏便民信息网） | ✅ **XHS 笔记整段转载农场**：正文保留 `data-v-*` Vue 标记、hashtag 尾块、`data-user-id`/`data-xsec-token` @提及锚点，可判定真实笔记；`/a/{seq}.html` 顺序号可扫，Google `site:` 有索引。⚠️ 不保留上游 note_id；图片走 `img.bim99.cn` 已全站 404；同站混有微信公众号转载（"点赞/在看/内容来源" UI），需按 XHS 特征过滤 |
| 搜索引擎（Google/Bing/so/sm/百度）找 note URL | ❌ 目标关键词均无 `xiaohongshu.com/explore/{id}` 索引命中 |

**结论**：游客态拿不到「定向关键词 + note_id + 原图」三者齐全的笔记。
b.460 镜像可补真实正文/tags（note_id 为镜像号），图片缺口只能等登录后
`feeds/search` 按标题重搜回填。采集脚本：`scripts/mirror_460_harvest.py`。
