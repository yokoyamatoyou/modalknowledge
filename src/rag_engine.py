"""RAG engine that answers questions using VectorStoreManager and OpenAI."""

from __future__ import annotations

from datetime import date
from typing import List, Dict

import openai

from .vector_store import VectorStoreManager


class RAGEngine:
    """Connect VectorStoreManager and LLM to generate answers."""

    def __init__(self, vector_store: VectorStoreManager, client: openai.Client) -> None:
        self.vector_store = vector_store
        self.client = client

    def _format_context(self, docs: List[Dict]) -> str:
        """Format documents as context string."""
        sections = []
        for doc in docs:
            meta = doc.get("metadata", {})
            source = meta.get("source_file", "unknown")
            page = meta.get("page", 0)
            text = doc.get("text", "")
            sections.append(f"[source: {source} page: {page}]\n{text}")
        return "\n\n".join(sections)

    def answer_question(self, question: str, filters: Dict[str, object] | None = None) -> Dict[str, object]:
        """Answer a question using current knowledge base."""
        today = date.today().strftime("%Y-%m-%d")
        search_filters = {"expiration_date_gt": today}
        if filters:
            search_filters.update(filters)
        docs = self.vector_store.search(question, filters=search_filters)
        if not docs:
            return {"answer": "ナレッジベースに情報がありません", "sources": []}

        context = self._format_context(docs)
        prompt = (
            "以下のコンテキストを参考に質問に日本語で答えてください。\n\n" + context
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt + "\n\n質問: " + question},
                ],
            )
            answer = response.choices[0].message.content.strip()
        except openai.OpenAIError:
            answer = "回答生成中にエラーが発生しました"

        sources = [doc.get("metadata", {}) for doc in docs]
        return {"answer": answer, "sources": sources}

