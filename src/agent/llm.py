"""LLM client：OpenAI 兼容 chat（百炼 qwen-turbo）+ 离线 MockLLM。"""
from __future__ import annotations

import re

import requests

from .. import config


class ChatClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or config.DASHSCOPE_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.DASHSCOPE_API_KEY
        self.model = model or config.COMPANION_MODEL
        self.temperature = (temperature if temperature is not None
                            else config.COMPANION_TEMPERATURE)
        self.session = session or requests.Session()
        self.timeout = timeout

    def chat(self, messages: list[dict]) -> str:
        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages,
                  "temperature": self.temperature},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class MockLLM:
    """离线 LLM：把注入的 top-1 chunk 包进搭子模板，断言端到端可验证。

    recorded 保存每次收到的 messages，测试可直接检查 prompt 组装。
    """

    def __init__(self) -> None:
        self.recorded: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> str:
        self.recorded.append(messages)
        system = messages[0]["content"]
        user = messages[-1]["content"]
        m = re.search(r"- \[(.+?)\] (.+?)（来源：(.+?)）", system)
        if not m:
            return ("这个我还没刷到诶，攻略里没看到相关的。你想去南京哪儿？"
                    "说说看我去翻翻笔记。")
        label, content, src = m.groups()
        poi = label.split("·")[0]
        first_point = content.split("。贴士：")[0].rstrip("。")
        return (f"哎{user.rstrip('？?')}是吧，我刷到《{src}》里说{first_point}。"
                f"{poi}我自己也没去过，不过看攻略感觉挺值得的，要不要安排上？")
