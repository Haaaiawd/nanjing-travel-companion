"""场景识别：把用户 query 映射到检索过滤 + 行为指令（L3 capability modules）。

识别顺序：先 POI 命中（graph 别名表），再类型关键词；POI 与类型可叠加
（「夫子庙有啥好吃的」→ poi=夫子庙 + type=美食）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..knowledge.graph import KnowledgeGraph

_SCENE_RULES: list[tuple[str, list[str], str | None, str]] = [
    # (场景名, 触发词, type_filter, 行为指令)
    ("pitfall", ["坑", "避雷", "踩雷", "别去", "劝退", "注意"],
     "避坑", "用提醒的口吻讲，像「幸好提前刷到」那种庆幸；挑最要紧的一两个坑说"),
    ("food", ["吃", "美食", "好吃", "小吃", "鸭血粉丝", "汤包", "锅贴", "餐厅"],
     "美食", "种草口吻，可以说「想跟你一起去试试」；店名只提攻略里有的"),
    ("season", ["春天", "夏天", "秋天", "冬天", "几月", "季节", "什么时候去"],
     None, "突出时间窗：攻略说什么季节/时段最好看、人流怎么避开"),
    ("route", ["怎么去", "怎么走", "交通", "地铁", "打车", "门票", "预约"],
     None, "讲到达方式和实用信息（预约/门票），只说攻略里提到的"),
    ("poi_play", ["怎么玩", "值得去", "好玩", "逛", "打卡", "拍照"],
     None, "讲玩法要点：看什么、什么时段去、怎么避开人流"),
]

GENERAL_INSTRUCTION = "没刷到相关攻略就老实说，然后邀请 ta 说说想去哪/想吃啥"


@dataclass
class Scene:
    name: str
    pois: list[str]
    type_filter: str | None = None
    season: str | None = None
    instruction: str = GENERAL_INSTRUCTION


def detect(query: str, graph: KnowledgeGraph) -> Scene:
    pois = graph.match_pois(query)

    season = None
    for w in ("春天", "夏天", "秋天", "冬天"):
        if w in query:
            season = w
            break
    if season is None and re.search(r"几月|什么时候去|最佳时间", query):
        season = ""  # 时间意图但无具体季节 → 触发 season 指令但不过滤

    name, type_filter, instruction = "general", None, GENERAL_INSTRUCTION
    for scene_name, keywords, t, instr in _SCENE_RULES:
        if any(k in query for k in keywords):
            name, type_filter, instruction = scene_name, t, instr
            break
    if season is not None and name == "general":
        name, instruction = "season", _SCENE_RULES[2][3]
    if pois and name == "general":
        name, instruction = "poi_play", _SCENE_RULES[-1][3]

    return Scene(name=name, pois=pois, type_filter=type_filter,
                 season=season or None, instruction=instruction)
