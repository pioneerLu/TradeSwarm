import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from tradingagents.llm_env_compat import env_silicon_key_and_base

SituationItem = Union[
    Tuple[str, str],
    Tuple[str, str, Dict[str, Any]],
]


class FinancialSituationMemory:
    """
    情境向量库：Embedding + Chroma（可选持久化目录）。

    支持两种 embedding backend：
    - silicon（默认）：使用 Silicon 的 OpenAI-compatible embeddings API
    - bge_local：使用本地 BGE（SentenceTransformer）生成 embedding（适合离线/可控缓存）

    写入时可为每条记录附带 metadata（如 symbol），查询时可按 symbol 过滤。
    """

    def __init__(self, name: str = "test", config: Optional[Dict[str, Any]] = None) -> None:
        if config is None:
            config = {}

        self.embedding_backend = str(config.get("embedding_backend", "silicon")).strip().lower()
        self.embedding = config.get("embedding_model", "text-embedding-v4")
        self._bge_model = None
        self.bge_model_name_or_path: Optional[str] = None

        if self.embedding_backend not in ("silicon", "bge_local"):
            raise ValueError(f"未知 embedding_backend={self.embedding_backend}（仅支持 silicon / bge_local）")

        if self.embedding_backend == "silicon":
            api_key = config.get("api_key")
            base_url = config.get("backend_url")
            if not api_key or not base_url:
                sk = env_silicon_key_and_base()
                if sk:
                    api_key = api_key or sk[0]
                    base_url = base_url or sk[1]
            if not api_key or not base_url:
                raise ValueError(
                    "FinancialSituationMemory.embedding_backend=silicon 需要 Silicon："
                    "请配置 Silicon_API_KEY（及 base_url_silicon），或传入 config 含 api_key/backend_url"
                )

            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            # bge_local
            bge_path = config.get("bge_model_path") or config.get("embedding_model_path")
            bge_name = config.get("bge_model_name") or config.get("embedding_model_name")
            self.bge_model_name_or_path = str(bge_path or bge_name or "").strip() or None
            if not self.bge_model_name_or_path:
                raise ValueError("embedding_backend=bge_local 需要提供 bge_model_path（推荐本地目录）或 bge_model_name（HF repo id）")

        persist_dir = config.get("persist_directory") or config.get("chroma_persist_directory")
        if persist_dir:
            os.makedirs(persist_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.chroma_client = chromadb.Client(Settings(allow_reset=True))

        self.situation_collection = self.chroma_client.get_or_create_collection(name=name)

    def get_embedding(self, text: str) -> List[float]:
        if self.embedding_backend == "silicon":
            response = self.client.embeddings.create(model=self.embedding, input=text)
            return response.data[0].embedding

        # bge_local
        if self._bge_model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
            except Exception as e:
                raise RuntimeError(
                    "未安装本地 embedding 依赖。请执行：pip install -U \".[embeddings]\""
                ) from e

            model_path = self.bge_model_name_or_path
            self._bge_model = SentenceTransformer(
                str(model_path),
                device=str(os.getenv("BGE_DEVICE") or "cpu"),
            )

        vec = self._bge_model.encode([text], normalize_embeddings=True)
        return [float(x) for x in vec[0].tolist()]

    def add_situations(self, situations_and_advice: List[SituationItem]) -> None:
        """
        批量写入。每项为 (situation, recommendation) 或 (situation, recommendation, extra_metadata)。

        extra_metadata 可含: symbol, cycle_start_date, cycle_end_date, id（稳定 id 便于 upsert）。
        recommendation 同时存入 metadata 供 query 返回。
        """
        situations: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        embeddings: List[List[float]] = []

        for item in situations_and_advice:
            if len(item) == 2:
                situation, recommendation = item[0], item[1]
                extra: Dict[str, Any] = {}
            else:
                situation, recommendation, extra = item[0], item[1], dict(item[2])

            rec_str = recommendation if isinstance(recommendation, str) else str(recommendation)
            meta: Dict[str, Any] = {}
            for k, v in extra.items():
                if k == "id" or v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)

            sid = extra.get("id")
            if not sid:
                h = hashlib.sha256(f"{situation}|{rec_str}|{sorted(meta.items())}".encode()).hexdigest()[:16]
                sid = f"auto_{h}"
            meta["recommendation"] = rec_str

            situations.append(situation)
            metadatas.append(meta)
            ids.append(str(sid))
            embeddings.append(self.get_embedding(situation))

        if not situations:
            return

        self.situation_collection.upsert(
            documents=situations,
            metadatas=metadatas,
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(
        self,
        current_situation: str,
        n_matches: int = 1,
        *,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索；若提供 symbol，仅返回该标的的文档。"""
        query_embedding = self.get_embedding(current_situation)

        q_kw: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_matches,
            "include": ["metadatas", "documents", "distances"],
        }
        if symbol:
            q_kw["where"] = {"symbol": symbol}

        results = self.situation_collection.query(**q_kw)

        matched_results: List[Dict[str, Any]] = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                md = results["metadatas"][0][i] or {}
                rec = md.get("recommendation", "")
                dist = results["distances"][0][i] if results.get("distances") else 0.0
                matched_results.append(
                    {
                        "matched_situation": results["documents"][0][i],
                        "recommendation": rec,
                        "similarity_score": float(1.0 - dist) if dist is not None else 0.0,
                        "source": "chroma",
                    }
                )

        return matched_results
