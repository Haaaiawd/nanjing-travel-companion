"""轻量 KnowledgeGraph：POI 别名归一 + nearby 关系。

nearby 来源：人工种子表 POI_SEED + 同笔记 location co-occurrence。
别名表同时服务检索的 query 归一化（「石象路」→「明孝陵」）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Chunk

# 南京主要 POI 种子表：别名 + 地理/游览邻近关系
POI_SEED: dict[str, dict] = {
    "明孝陵": {"aliases": ["石象路", "梅花山", "紫金山"],
               "nearby": ["中山陵", "美龄宫", "灵谷寺"]},
    "中山陵": {"aliases": ["中山陵风景区"], "nearby": ["明孝陵", "音乐台", "美龄宫"]},
    "夫子庙": {"aliases": ["南京夫子庙", "文庙", "秦淮河"],
               "nearby": ["老门东", "秦淮河画舫", "瞻园"]},
    "老门东": {"aliases": ["老门东历史街区"], "nearby": ["夫子庙", "中华门", "大报恩寺"]},
    "玄武湖": {"aliases": ["玄武湖公园"], "nearby": ["鸡鸣寺", "南京站", "台城"]},
    "总统府": {"aliases": ["南京总统府", "大行宫"],
               "nearby": ["六朝博物馆", "江宁织造博物馆", "新街口"]},
    "鸡鸣寺": {"aliases": ["古鸡鸣寺"], "nearby": ["玄武湖", "台城", "东南大学"]},
    "南京博物院": {"aliases": ["南博"], "nearby": ["明故宫", "中山门"]},
    "牛首山": {"aliases": ["牛首山文化旅游区"], "nearby": ["金陵小镇"]},
    "颐和路": {"aliases": ["颐和路民国公馆区"], "nearby": ["南京大学", "先锋书店"]},
    "栖霞山": {"aliases": ["栖霞山风景区", "栖霞寺", "栖霞古寺", "栖霞古镇",
                           "红叶谷", "霜红苑", "明镜湖", "桃花湖", "枫林湖",
                           "太虚亭", "始皇临江处", "桃花坞", "红枫林",
                           "桃花扇亭", "虎山", "天街"],
               "nearby": ["千佛岩", "舍利塔", "达摩古洞"]},
    "千佛岩": {"aliases": ["千佛窟"], "nearby": ["栖霞山", "舍利塔"]},
    "舍利塔": {"aliases": ["栖霞寺舍利塔"], "nearby": ["栖霞山", "千佛岩"]},
    "达摩古洞": {"aliases": ["达摩洞", "幕燕滨江", "幕府山", "夹骡峰",
                             "燕子矶", "燕子矶公园", "五马渡", "长江观音景区",
                             "一苇渡光影馆"],
                 "nearby": ["八卦洲", "长江大桥", "栖霞山"]},
}


class KnowledgeGraph:
    def __init__(self, locations: dict[str, dict] | None = None) -> None:
        self.locations: dict[str, dict] = locations or {}
        self._alias: dict[str, str] = {}
        for name, info in self.locations.items():
            self._alias[name] = name
            for a in info.get("aliases", []):
                self._alias[a] = name

    # --- 查询 ---
    def normalize(self, name: str) -> str:
        return self._alias.get(name, name)

    def match_pois(self, text: str) -> list[str]:
        """在 query 里找命中的 canonical POI（含别名匹配），按名字长度降序去重。

        「南京」这类城市级名字不算 POI 命中 —— 否则所有含南京的 query
        都会被错误地缩圈到城市粒度。"""
        hits = []
        for name in sorted(self._alias, key=len, reverse=True):
            if name in text:
                canon = self._alias[name]
                if canon not in hits and canon != "南京":
                    hits.append(canon)
        return hits

    def nearby(self, poi: str, limit: int = 3) -> list[str]:
        info = self.locations.get(self.normalize(poi), {})
        return list(info.get("nearby", []))[:limit]

    def chunk_ids(self, poi: str) -> list[str]:
        info = self.locations.get(self.normalize(poi), {})
        return list(info.get("chunk_ids", []))

    # --- 构建与持久化 ---
    @classmethod
    def build(cls, chunks: list[Chunk],
              seed: dict[str, dict] | None = None) -> "KnowledgeGraph":
        seed = seed if seed is not None else POI_SEED
        locations: dict[str, dict] = {
            name: {"aliases": list(info.get("aliases", [])),
                   "nearby": list(info.get("nearby", [])),
                   "tags": set(), "chunk_ids": []}
            for name, info in seed.items()
        }
        alias = {a: n for n, info in seed.items() for a in [n, *info.get("aliases", [])]}

        def canon(loc: str) -> str:
            return alias.get(loc, loc)

        note_locs: dict[str, set[str]] = {}
        for c in chunks:
            locs = {canon(l) for l in
                    (c.structured_data.get("locations") or [c.location])}
            locs.add(canon(c.location))
            note_locs.setdefault(c.source_note_id, set()).update(locs)
            for loc in locs:
                node = locations.setdefault(
                    loc, {"aliases": [], "nearby": [], "tags": set(), "chunk_ids": []})
                node["tags"].update(c.tags)
                if c.chunk_id not in node["chunk_ids"]:
                    node["chunk_ids"].append(c.chunk_id)

        # co-occurrence：同一笔记里出现的不同 POI 互认 nearby
        for locs in note_locs.values():
            for a in locs:
                for b in locs:
                    if a != b and b not in locations[a]["nearby"]:
                        locations[a]["nearby"].append(b)

        for info in locations.values():
            info["tags"] = sorted(info["tags"])
        return cls(locations)

    def to_dict(self) -> dict:
        return {"locations": self.locations}

    def save(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "KnowledgeGraph":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["locations"])
