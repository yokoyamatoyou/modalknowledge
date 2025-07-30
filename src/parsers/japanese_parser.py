"""Advanced Japanese text parser using SudachiPy."""

from typing import List
from sudachipy import tokenizer, dictionary

class JapaneseSentenceSplitter:
    """Splits Japanese text into sentences using SudachiPy."""

    def __init__(self):
        self.tokenizer = dictionary.Dictionary().create()
        self.mode = tokenizer.Tokenizer.SplitMode.C

    def split(self, text: str) -> List[str]:
        """Split text into a list of sentences."""
        if not text:
            return []
        # Sudachi normalizes text internally (e.g., full-width to half-width numbers)
        return [s.surface for s in self.tokenizer.tokenize(text, self.mode)]

def create_chunks(sentences: List[str], chunk_size: int = 512, overlap: int = 50) -> List[str]:
    """Create overlapping chunks from a list of sentences."""
    if not sentences:
        return []

    chunks = []
    current_chunk = ""
    for sentence in sentences:
        # If adding the new sentence exceeds chunk_size, finalize the current chunk
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            # Start new chunk with overlap from the previous one
            overlap_text = current_chunk[-overlap:]
            current_chunk = overlap_text + sentence
        else:
            current_chunk += sentence

    # Add the last remaining chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

class JapaneseTextParser:
    """A text parser optimized for Japanese documents."""

    def __init__(self):
        self.splitter = JapaneseSentenceSplitter()

    def parse(self, text: str) -> List[str]:
        """Parse text by splitting into sentences and creating overlapping chunks."""
        sentences = self.splitter.split(text)
        chunks = create_chunks(sentences)
        return chunks
