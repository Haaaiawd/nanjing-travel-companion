"""Embedding providers：百炼 DashScope（真实）+ HashEmbedding（离线确定性）。

HashEmbedding：char unigram+bigram → sha256 桶计数 → L2 归一。对中文有真实
区分度（共享「明孝陵」的文本天然高相似），测试断言排序时不是随机结果。
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

import requests

from .. import config


class EmbeddingProvider(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


def _tokens(text: str) -> list[str]:
    """中文按字 unigram+bigram；ascii 词整词。够用于关键词语义近似。"""
    chars = [c for c in text if not c.isspace()]
    toks = [c for c in chars]
    toks += [a + b for a, b in zip(chars, chars[1:])]
    return toks


class HashEmbedding:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _tokens(text):
                h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            out.append(_l2(vec))
        return out


class DashScopeEmbedding:
    """百炼 OpenAI 兼容 /embeddings 端点。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.DASHSCOPE_API_KEY
        self.base_url = (base_url or config.DASHSCOPE_BASE_URL).rstrip("/")
        self.model = model or config.EMBEDDING_MODEL
        self.session = session or requests.Session()
        self.timeout = timeout
        self.dim = 0  # 首次调用后由响应确定

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self.session.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        vectors = [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
        if vectors and not self.dim:
            self.dim = len(vectors[0])
        return vectors


def make_default_provider() -> EmbeddingProvider:
    """有 key 用百炼，否则离线 hash。显式注入优先于自动选择。"""
    if config.DASHSCOPE_API_KEY:
        return DashScopeEmbedding()
    return HashEmbedding()
