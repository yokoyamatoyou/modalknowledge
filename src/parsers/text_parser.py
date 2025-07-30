"""Text file parser that delegates to a Japanese-specific parser if needed."""

from __future__ import annotations
import logging
from pathlib import Path
import re

from langchain.text_splitter import RecursiveCharacterTextSplitter
from .japanese_parser import JapaneseTextParser

logger = logging.getLogger(__name__)

# Regular expression to detect a significant number of Japanese characters
# (Hiragana, Katakana, or common Kanji)
JAPANESE_REGEX = re.compile(r"[\u3040-\u30ff\u4e00-\u9faf]{50,}")

def is_japanese(text: str) -> bool:
    """Check if the text contains a significant amount of Japanese."""
    return JAPANESE_REGEX.search(text) is not None

def parse_text(file_path: str) -> list[str]:
    """Parse a text file, using a specialized parser for Japanese."""
    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("Text file not found: %s", file_path)
        return []

    if is_japanese(text):
        logger.info("Japanese text detected, using JapaneseTextParser.")
        parser = JapaneseTextParser()
        return parser.parse(text)
    else:
        logger.info("Using default RecursiveCharacterTextSplitter.")
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        return splitter.split_text(text)

