# Devin Brief: 补充栖霞区景点素材

## 项目
Nanjing Travel Companion (`/home/haa/sites/nanjing-travel-companion`)

## 背景
现有 `data/raw/notes/` 有 20 条真实笔记，但缺少栖霞区素材。
上一阶段已验证：游客频道/镜像提取能拿到真实笔记和图片，无需登录。

## 目标
围绕以下关键词补充攻略素材：
- 栖霞山
- 千佛岩
- 舍利塔
- 达摩古洞

## 要求
1. 复用已验证可用的抓取路径：MCP 游客频道 + 镜像页提取
2. 新增笔记落盘到 `data/raw/notes/`，图片到 `data/raw/images/`
3. 每条记录保留原始 note_id、来源 URL、抓取时间
4. 最终输出可被 `knowledge/` 模块直接导入的结构化内容
5. 保持与现有 `Note` 模型字段兼容，不改动模型定义

## 交付
- 新增 8~15 条栖霞相关真实笔记
- 对应图片下载完成
- 更新 `HARVEST.md` 记录 provenance

```json
COMPLETION_NOTIFY
source: assistant
task: qixia-harvest
deliverables:
- data/raw/notes/*.json 新增栖霞区素材
- data/raw/images/* 对应图片
- HARVEST.md updated
status: success
errors: none
```
