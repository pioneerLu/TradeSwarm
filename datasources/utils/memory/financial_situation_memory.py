import chromadb
from chromadb.config import Settings
from openai import OpenAI

from tradingagents.llm_env_compat import env_silicon_key_and_base


class FinancialSituationMemory:
    def __init__(self, name="test", config=None):
        if config is None:
            config = {}
            
        # 默认使用 text-embedding-v4
        self.embedding = "text-embedding-v4"
        
        api_key = config.get("api_key")
        base_url = config.get("backend_url")
        if not api_key or not base_url:
            sk = env_silicon_key_and_base()
            if sk:
                api_key = api_key or sk[0]
                base_url = base_url or sk[1]
        if not api_key or not base_url:
            raise ValueError(
                "FinancialSituationMemory 需要 Silicon：请配置 Silicon_API_KEY（及 base_url_silicon），"
                "或传入 config 含 api_key/backend_url"
            )
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.chroma_client = chromadb.Client(Settings(allow_reset=True))
        self.situation_collection = self.chroma_client.get_or_create_collection(name=name)

    def get_embedding(self, text):
        """Get OpenAI embedding for a text"""
        response = self.client.embeddings.create(
            model=self.embedding, 
            input=text
        )
        return response.data[0].embedding

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""
        situations = []
        advice = []
        ids = []
        embeddings = []

        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        self.situation_collection.add(
            documents=situations,
            metadatas=[{"recommendation": rec} for rec in advice],
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using OpenAI embeddings"""
        query_embedding = self.get_embedding(current_situation)

        results = self.situation_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_matches,
            include=["metadatas", "documents", "distances"],
        )

        matched_results = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                matched_results.append(
                    {
                        "matched_situation": results["documents"][0][i],
                        "recommendation": results["metadatas"][0][i]["recommendation"],
                        "similarity_score": 1 - results["distances"][0][i],
                    }
                )

        return matched_results

