"""Vector store manager with per-document storage for easy deletion."""

from __future__ import annotations
import json
import pickle
import shutil
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import logging

logging.basicConfig(level=logging.INFO)

import faiss
import numpy as np
import openai

from .utils import log_operation

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """Manages a vector store where each document has its own directory."""

    def __init__(self, client: openai.Client, kb_path: str = "data/unified_kb"):
        self.client = client
        self.kb_path = Path(kb_path)
        self.docs_path = self.kb_path / "documents"
        self.faiss_path = self.kb_path / "faiss_index"

        self.docs_path.mkdir(parents=True, exist_ok=True)
        self.faiss_path.mkdir(parents=True, exist_ok=True)

        self.index_file = self.faiss_path / "kb.faiss"
        self.id_map_file = self.faiss_path / "id_map.pkl"

        self.index: Optional[faiss.IndexIDMap] = None
        self.id_map: Dict[int, str] = {}
        self.documents: Dict[str, List[Dict]] = {}

        self._load()

    def _load(self) -> None:
        """Load the FAISS index, ID map, and all document chunks."""
        if self.index_file.exists() and self.id_map_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                with open(self.id_map_file, "rb") as f:
                    self.id_map = pickle.load(f)
            except EOFError:
                # If files are empty or corrupted, start fresh
                self.index = None
                self.id_map = {}
                # Optionally, you could also delete the corrupted files here
                self.index_file.unlink(missing_ok=True)
                self.id_map_file.unlink(missing_ok=True)

        for doc_dir in self.docs_path.iterdir():
            if doc_dir.is_dir():
                doc_id = doc_dir.name
                chunks_file = doc_dir / "chunks.jsonl"
                if chunks_file.exists():
                    with open(chunks_file, "r", encoding="utf-8") as f:
                        self.documents[doc_id] = [json.loads(line) for line in f]

    def _save_index(self) -> None:
        """Save the FAISS index and the ID-to-document mapping."""
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_file))
            with open(self.id_map_file, "wb") as f:
                pickle.dump(self.id_map, f)

    def _embed(self, text: str) -> np.ndarray:
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small", input=text
            )
            return np.array(response.data[0].embedding, dtype="float32")
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Embedding failed: %s", exc)
            # Fallback: deterministic pseudo-random vector from text hash
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
            return rng.random(1536, dtype="float32")

    def _match_filters(self, chunk: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        """Return True if the chunk satisfies the filter conditions."""
        if not filters:
            return True

        meta = chunk.get("metadata", {})
        text = chunk.get("text", "")

        # **デバッグログを追加**
        logger.debug("チャンクのメタデータ: %s", meta)
        logger.debug("適用中のフィルタ: %s", filters)

        for key, value in filters.items():
            if key == "expiration_date_gt":
                exp = meta.get("expiration_date")
                logger.debug("有効期限チェック: %s > %s", exp, value)
                if not exp:
                    # 有効期限が設定されていない場合は除外
                    logger.debug("有効期限未設定のため除外")
                    return False
                # 文字列での日付比較（YYYY-MM-DD形式を前提）
                if exp <= value:
                    logger.debug("期限切れのため除外: %s <= %s", exp, value)
                    return False
            elif key == "expiration_date_start":
                exp = meta.get("expiration_date")
                logger.debug("開始日チェック: %s >= %s", exp, value)
                if exp and exp < value:
                    return False
            elif key == "expiration_date_end":
                exp = meta.get("expiration_date")
                logger.debug("終了日チェック: %s <= %s", exp, value)
                if exp and exp > value:
                    return False
            elif key == "author":
                if meta.get("author") != value:
                    logger.debug("作成者不一致: %s != %s", meta.get('author'), value)
                    return False
            elif key == "tag":
                tags = meta.get("ai_tags", [])
                if isinstance(value, str):
                    if value not in tags:
                        logger.debug("タグ不一致: %s not in %s", value, tags)
                        return False
                else:
                    if not any(v in tags for v in value):
                        logger.debug("タグ不一致: %s not in %s", value, tags)
                        return False
            elif key == "keyword":
                if value.lower() not in text.lower():
                    logger.debug("キーワード不一致: %s not in text", value)
                    return False
            else:
                if meta.get(key) != value:
                    logger.debug("メタデータ不一致: %s != %s", meta.get(key), value)
                    return False

        logger.debug("フィルタ条件をすべて満たしています")
        return True

    def add_document(self, original_path: Path, chunks: List[Dict], thumbnail_path: Optional[Path]) -> None:
        """Add a new document and its chunks to the knowledge base."""
        doc_id = str(uuid.uuid4())
        doc_dir = self.docs_path / doc_id
        doc_dir.mkdir()

        # Store original file and thumbnail
        shutil.copy(original_path, doc_dir / original_path.name)
        if thumbnail_path:
            shutil.copy(thumbnail_path, doc_dir / thumbnail_path.name)

        # Store chunks in a human-readable JSONL file
        with open(doc_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        # Add vectors to FAISS index
        vectors = [self._embed(chunk['text']) for chunk in chunks]
        if not vectors:
            return

        vector_dim = vectors[0].shape[0]
        if self.index is None:
            index = faiss.IndexFlatL2(vector_dim)
            self.index = faiss.IndexIDMap(index)

        # Generate unique, sequential IDs for FAISS
        start_id = max(self.id_map.keys()) + 1 if self.id_map else 0
        ids = np.arange(start_id, start_id + len(vectors))

        self.index.add_with_ids(np.array(vectors), ids)
        for i, faiss_id in enumerate(ids):
            self.id_map[int(faiss_id)] = f"{doc_id}/{i}"  # Map FAISS ID to doc_id and chunk_index

        self._save_index()
        self.documents[doc_id] = chunks
        log_operation("add_document", {"doc_id": doc_id, "file": str(original_path)})

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its associated data."""
        doc_dir = self.docs_path / doc_id
        if not doc_dir.exists():
            return False

        # Find FAISS IDs to remove
        ids_to_remove = [faiss_id for faiss_id, mapping in self.id_map.items() if mapping.startswith(doc_id)]
        if ids_to_remove and self.index is not None:
            self.index.remove_ids(np.array(ids_to_remove))
            for faiss_id in ids_to_remove:
                del self.id_map[faiss_id]
            self._save_index()

        # Delete document directory
        shutil.rmtree(doc_dir)
        if doc_id in self.documents:
            del self.documents[doc_id]

        log_operation("delete_document", {"doc_id": doc_id})

        return True

    def search(self, query: str, k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.index is None or not self.documents:
            return []

        query_vector = self._embed(query)
        distances, ids = self.index.search(np.expand_dims(query_vector, axis=0), k * 5) # Search more to filter

        results = []
        seen_mappings = set()
        for dist, faiss_id in zip(distances[0], ids[0]):
            if faiss_id == -1 or len(results) >= k:
                continue

            mapping = self.id_map.get(int(faiss_id))
            if not mapping or mapping in seen_mappings:
                continue

            doc_id, chunk_index_str = mapping.split("/")
            chunk_index = int(chunk_index_str)

            doc_chunks = self.documents.get(doc_id)
            if not doc_chunks or chunk_index >= len(doc_chunks):
                continue

            chunk = doc_chunks[chunk_index]
            if not self._match_filters(chunk, filters):
                continue

            chunk_with_score = chunk.copy()
            chunk_with_score["score"] = float(dist)
            chunk_with_score["doc_id"] = doc_id # Add doc_id for deletion UI
            results.append(chunk_with_score)
            seen_mappings.add(mapping)

        return results

    def export_all(self, export_path: str) -> None:
        """Export the entire knowledge base to a JSON Lines file."""
        export_file = Path(export_path)
        export_file.parent.mkdir(parents=True, exist_ok=True)
        with open(export_file, "w", encoding="utf-8") as f:
            for doc_id, chunks in self.documents.items():
                for chunk in chunks:
                    record = {
                        "doc_id": doc_id,
                        "text": chunk.get("text", ""),
                        "metadata": chunk.get("metadata", {}),
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
