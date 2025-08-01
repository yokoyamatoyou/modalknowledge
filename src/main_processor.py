"""Main processor to route files to appropriate parsers and create thumbnails."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

import openai
from PIL import Image

from .parsers import text_parser, image_parser, doc_parser

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (128, 128)

def generate_ai_metadata(content: str, client: openai.Client) -> dict:
    """Generate metadata using OpenAI API."""
    prompt = f"""あなたは、企業のナレッジマネジメントを支援するAIアシスタントです。
以下のテキスト（または画像の内容説明）を分析し、検索精度を最大化するためのメタデータを生成してください。

このメタデータは、社内の様々な部署の従業員が、多様なキーワードで情報を探すために利用されます。
専門用語だけでなく、日常的な言葉や、関連する可能性のある言葉も幅広く含めてください。

# 指示:
1.  **要約 (summary):** テキスト全体の内容を、100文字程度で簡潔に要約してください。
2.  **検索タグ (tags):** この内容を検索する際に使われそうなキーワードやフレーズを、JSONのリスト形式で、少なくとも10個以上、できるだけ多く挙げてください。以下の視点を必ず含めてください。
    *   中心となるトピックや概念
    *   関連する製品名、サービス名、プロジェクト名
    *   登場する人物名、部署名
    *   類義語や言い換え（例：会議、ミーティング、打ち合わせ）
    *   より広い概念（例：「RAG」に対して「AI」「自然言語処理」）
    *   具体的なアクションや目的（例：「手順書」「トラブルシューティング」「企画書」）

# 出力形式:
必ず以下のJSON形式で出力してください。
{{
  "summary": "（ここに要約を記述）",
  "tags": ["（ここにタグ1を記述）", "（ここにタグ2を記述）", ...]
}}

# 分析対象のテキスト/内容:
{content}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        if response.choices:
            ai_meta = json.loads(response.choices[0].message.content)
            return {
                "ai_summary": ai_meta.get("summary", ""),
                "ai_tags": ai_meta.get("tags", [])
            }
        else:
            logger.warning("AI metadata generation returned no choices.")
            return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from AI response: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to generate AI metadata: {e}", exc_info=True)
        return {}

def create_thumbnail(image_path: Path, temp_dir: Path) -> Optional[Path]:
    """Create a thumbnail for an image file."""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            thumbnail_path = temp_dir / f"thumbnail_{image_path.stem}.png"
            img.save(thumbnail_path, "PNG")
            return thumbnail_path
    except Exception as e:
        logger.error(f"Failed to create thumbnail for {image_path}: {e}")
        return None

def process_file(
    file_path: str,
    metadata: dict,
    client: openai.Client,
    temp_dir: Path
) -> Tuple[List[Dict], Optional[Path]]:
    """Process a file, return chunks and an optional thumbnail path."""
    path = Path(file_path)
    ext = path.suffix.lower()
    base_meta = metadata.copy()
    base_meta["source_file"] = path.name

    results: List[Dict] = []
    thumbnail_path: Optional[Path] = None

    try:
        # --- AI Metadata Generation ---
        full_text_for_ai = ""
        ai_meta = {}

        if ext in (".txt", ".md"):
            full_text_for_ai = path.read_text(encoding="utf-8")
        elif ext in (".pdf", ".docx"):
            texts, _ = doc_parser.parse_document(file_path)
            full_text_for_ai = "\n".join(texts)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            with open(path, "rb") as f:
                image_bytes = f.read()
            full_text_for_ai = image_parser.parse_image(image_bytes, client)

        if full_text_for_ai:
            ai_meta = generate_ai_metadata(full_text_for_ai, client)

        # --- Chunking and Processing ---
        if ext in (".txt", ".md"):
            texts = text_parser.parse_text(file_path)
            for i, chunk_text in enumerate(texts):
                meta = base_meta.copy()
                meta.update({"page": i + 1, "type": "text"})
                meta.update(ai_meta)  # Add AI metadata
                results.append({"text": chunk_text, "metadata": meta})

        elif ext in (".pdf", ".docx"):
            texts, images = doc_parser.parse_document(file_path)
            for i, chunk_text in enumerate(texts):
                meta = base_meta.copy()
                meta.update({"page": i + 1, "type": "text"})
                meta.update(ai_meta)  # Add AI metadata
                results.append({"text": chunk_text, "metadata": meta})

            for img_data in images:
                img_bytes = img_data.get("image_bytes", b"")
                if img_bytes:
                    desc = image_parser.parse_image(img_bytes, client)
                    img_ai_meta = generate_ai_metadata(desc, client)
                    meta = base_meta.copy()
                    meta.update({"page": img_data.get("page_number", 0), "type": "document_image"})
                    meta.update(img_ai_meta)
                    results.append({"text": desc, "metadata": meta})

        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            thumbnail_path = create_thumbnail(path, temp_dir)
            desc = full_text_for_ai 
            meta = base_meta.copy()
            meta.update({"page": 1, "type": "image"})
            meta.update(ai_meta)
            if thumbnail_path:
                meta['thumbnail_path'] = str(thumbnail_path.relative_to(temp_dir.parent))
            meta['original_path'] = str(path.relative_to(temp_dir.parent))
            results.append({"text": desc, "metadata": meta})

        else:
            logger.warning(f"Unsupported file type: {ext}")

    except Exception as e:
        logger.error(f"Failed to process {path}: {e}", exc_info=True)

    return results, thumbnail_path
