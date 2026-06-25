"""
rag/rag_engine.py
-----------------
RAG layer using ChromaDB + sentence-transformers (all-MiniLM-L6-v2).

Purpose:
  Given detected entity types, retrieve the most relevant
  compliance rules from the local ChromaDB vector store.
  This grounds the reasoning layer in actual regulatory definitions
  rather than relying on the LLM's parametric knowledge.

No API calls. No internet at runtime.
Embeddings run locally via sentence-transformers.
ChromaDB runs fully in-process (no server needed).
"""

import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

RULES_PATH = Path(__file__).parent / "rules.json"
CHROMA_PATH = Path(__file__).parent / "chroma_store"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "compliance_rules"


class RAGEngine:
    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collection = None
        self._embedder: Optional[SentenceTransformer] = None
        self._loaded = False

    def load(self):
        """Load ChromaDB and embedding model. Call once at startup."""
        if self._loaded:
            return

        print("Loading embedding model (all-MiniLM-L6-v2)...")
        self._embedder = SentenceTransformer(EMBEDDING_MODEL)

        print("Initialising ChromaDB...")
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Populate if empty
        if self._collection.count() == 0:
            print("Populating ChromaDB with compliance rules...")
            self._ingest_rules()

        self._loaded = True
        print(f"RAG engine ready. {self._collection.count()} rules indexed.")

    def _ingest_rules(self):
        """Read rules.json, embed each rule, and store in ChromaDB."""
        with open(RULES_PATH, "r") as f:
            rules = json.load(f)

        documents = []
        metadatas = []
        ids = []

        for rule in rules:
            # Build a rich text representation for embedding
            doc_text = (
                f"Framework: {rule['framework']}. "
                f"Rule: {rule['rule']}. "
                f"Description: {rule['description']}. "
                f"Entity types: {', '.join(rule['entity_types'])}."
            )
            documents.append(doc_text)
            metadatas.append({
                "framework":    rule["framework"],
                "rule":         rule["rule"],
                "entity_types": ",".join(rule["entity_types"]),
                "risk":         rule["risk"],
                "description":  rule["description"],
            })
            ids.append(rule["id"])

        # Embed all at once (batch is faster)
        embeddings = self._embedder.encode(documents, show_progress_bar=False).tolist()

        self._collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def query(self, entity_types: list[str], top_k: int = 5) -> list[dict]:
        """
        Given a list of detected entity types, find the most relevant
        compliance rules via semantic similarity.

        Returns a list of rule dicts with keys:
          framework, rule, description, entity_types, risk, relevance_score
        """
        if not self._loaded:
            self.load()

        if not entity_types:
            return []

        # Build a query string from detected entity types
        query_text = f"Sensitive data found: {', '.join(entity_types)}"
        query_embedding = self._embedder.encode([query_text], show_progress_bar=False).tolist()

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        rules = []
        for i, meta in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            relevance = round(1 - distance, 3)  # cosine distance → similarity
            rules.append({
                "framework":    meta["framework"],
                "rule":         meta["rule"],
                "description":  meta["description"],
                "entity_types": meta["entity_types"].split(","),
                "risk":         meta["risk"],
                "relevance":    relevance,
            })

        return rules

    def get_compliance_exposure(self, entity_types: list[str]) -> dict[str, float]:
        """
        Return a per-framework exposure score (0–100) based on
        how many relevant rules are triggered by the detected entity types.
        Used for the compliance dashboard.
        """
        if not entity_types:
            return {}

        all_rules = self.query(entity_types, top_k=20)
        frameworks = {}

        for rule in all_rules:
            fw = rule["framework"]
            # Weight by relevance and risk
            risk_weight = {"High": 1.0, "Medium": 0.6, "Low": 0.3}.get(rule["risk"], 0.5)
            score = rule["relevance"] * risk_weight * 100

            if fw not in frameworks:
                frameworks[fw] = []
            frameworks[fw].append(score)

        # Aggregate: take max score per framework (worst-case exposure)
        return {
            fw: round(min(max(scores), 100), 1)
            for fw, scores in frameworks.items()
        }
