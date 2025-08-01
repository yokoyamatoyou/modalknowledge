"""RAG engine that answers questions using VectorStoreManager and OpenAI."""

from __future__ import annotations

from typing import List, Dict

import openai
import logging

from .vector_store import VectorStoreManager

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


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
        search_filters = filters or {}

        # 日付フィルタが指定されていない場合は、全てのナレッジを対象に検索する
        if not any(key.startswith("expiration_date") for key in search_filters):
            logger.debug("日付フィルタ未指定のため、全期間から検索します")

        docs = self.vector_store.search(question, filters=search_filters)

        # **デバッグログを追加**
        logger.debug("検索クエリ: %s", question)
        logger.debug("適用フィルタ: %s", search_filters)
        logger.debug("検索結果数: %s", len(docs))

        if not docs:
            return {"answer": "ナレッジベースに情報がありません。登録済みナレッジの有効期限を確認してください。", "sources": []}

        context = self._format_context(docs)
        prompt = (
            "以下のコンテキストを参考に質問に日本語で答えてください。\n\n" + context
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt + "\n\n質問: " + question},
                ],
            )
            answer = response.choices[0].message.content.strip()
        except openai.OpenAIError as e:
            logger.error("OpenAI API エラー: %s", e)
            answer = "回答生成中にエラーが発生しました"

        # return both metadata and document id for referencing in the UI
        sources = [
            {"metadata": doc.get("metadata", {}), "doc_id": doc.get("doc_id")}
            for doc in docs
        ]
        return {"answer": answer, "sources": sources}

