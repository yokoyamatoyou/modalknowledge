"""Document parser for PDF and DOCX files."""

from __future__ import annotations

import logging
from typing import List, Tuple, Dict

import fitz  # PyMuPDF
from docx import Document


logger = logging.getLogger(__name__)


def parse_document(file_path: str) -> Tuple[List[str], List[Dict]]:
    """Extract text blocks and images from a PDF or DOCX file."""

    texts: List[str] = []
    images: List[Dict] = []

    try:
        if file_path.lower().endswith(".pdf"):
            doc = fitz.open(file_path)
            for page_index in range(len(doc)):
                page = doc[page_index]
                texts.append(page.get_text())
                for img in page.get_images(full=True):
                    base = doc.extract_image(img[0])
                    images.append({"image_bytes": base["image"], "page_number": page_index + 1})
        elif file_path.lower().endswith(".docx"):
            docx = Document(file_path)
            for para in docx.paragraphs:
                if para.text:
                    texts.append(para.text)
            for rel in docx.part._rels.values():
                if "image" in rel.reltype:
                    image_bytes = rel.target_part.blob
                    images.append({"image_bytes": image_bytes, "page_number": 0})
        else:
            logger.error("Unsupported document type: %s", file_path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to parse document %s: %s", file_path, exc)
        return [], []

    return texts, images

