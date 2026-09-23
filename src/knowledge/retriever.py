"""场景检索：POI 别名缩圈 → 类型/季节硬过滤 → 余弦 top-k。"""
from __future__ import annotations

from .. import config
from .embeddings import EmbeddingProvider, cosine, make_default_provider
from .graph import KnowledgeGraph
from .indexer import Index
from .schema import RetrievedChunk

POI_BOOST = 1.15
SEASON_WORDS = ("春天", "夏天", "秋天", "冬天", "春", "夏", "秋", "冬")


class Retriever:
    def __init__(
        self,
        index: Index,
        graph: KnowledgeGraph | None = None,
        provider: EmbeddingProvider | None = None,
        top_k: int = config.TOP_K_RETRIEVAL,
    ) -> None:
        self.index = index
        self.graph = graph or KnowledgeGraph()
        self.provider = provider or make_default_provider()
        self.top_k = top_k

    def _season_match(self, chunk, season: str) -> bool:
        if not season:
            return True
        s = season if season.endswith("天") else season + "天"
        hay = chunk.tags + [chunk.structured_data.get("time_hint", "")]
        return any(season in str(h) or s in str(h) for h in hay)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        type_filter: str | None = None,
        season: str | None = None,
        pois: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        top_k = top_k or self.top_k
        hits = pois if pois is not None else self.graph.match_pois(query)
        primary_poi = hits[0] if hits else None

        if primary_poi:
            # POI 命中：候选 = 该 POI（含其子地点）的 chunk 集合
            cand_ids = set(self.index.candidates_for(primary_poi))
            for loc, ids in self.index.by_location.items():
                if self.graph.normalize(loc) == primary_poi:
                    cand_ids.update(ids)
            poi_scoped = [self.index.chunks[i] for i in cand_ids
                          if i in self.index.chunks]
        else:
            poi_scoped = []

        candidates = poi_scoped or list(self.index.chunks.values())
        if type_filter:
            candidates = [c for c in candidates if c.type == type_filter]
        if season:
            candidates = [c for c in candidates
                          if self._season_match(c, season)]
        if not candidates:
            # 分级降级：先丢过滤条件保留 POI 圈，再退回全库，保证有话可说
            candidates = poi_scoped or list(self.index.chunks.values())

        qvec = self.provider.embed([query])[0]
        scored = []
        for c in candidates:
            v = self.index.vectors.get(c.chunk_id)
            if v is None:
                continue
            score = cosine(qvec, v)
            if primary_poi:
                locs = {c.location,
                        *(c.structured_data.get("locations") or [])}
                if any(self.graph.normalize(l) == primary_poi for l in locs):
                    score *= POI_BOOST
            scored.append(RetrievedChunk(
                chunk=c, score=score,
                nearby=self.graph.nearby(primary_poi) if primary_poi else []))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
