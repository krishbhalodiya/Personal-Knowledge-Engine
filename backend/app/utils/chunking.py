import logging
import re
from typing import List, Optional
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a single chunk of text."""
    content: str
    index: int            # Position in document (0, 1, 2, ...)
    start_char: int       # Start character position in original
    end_char: int         # End character position in original
    token_count: int      # Approximate token count


class TextChunker:
    """Text chunker using overlapping windows strategy."""
    
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.chars_per_token = 4
        
        self.chunk_size_chars = self.chunk_size * self.chars_per_token
        self.overlap_chars = self.chunk_overlap * self.chars_per_token
        
        logger.info(
            f"TextChunker initialized: {self.chunk_size} tokens "
            f"(~{self.chunk_size_chars} chars), {self.chunk_overlap} overlap"
        )
    
    def chunk(self, text: str) -> List[Chunk]:
        """Split text into overlapping chunks."""
        text = self._clean_text(text)
        
        if not text:
            logger.warning("Empty text provided for chunking")
            return []
        
        if len(text) <= self.chunk_size_chars:
            return [Chunk(
                content=text,
                index=0,
                start_char=0,
                end_char=len(text),
                token_count=self._estimate_tokens(text),
            )]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size_chars
            
            if end >= len(text):
                end = len(text)
            else:
                end = self._find_break_point(text, start, end)
            
            chunk_content = text[start:end].strip()
            
            if chunk_content:
                chunks.append(Chunk(
                    content=chunk_content,
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    token_count=self._estimate_tokens(chunk_content),
                ))
                chunk_index += 1
            
            step = self.chunk_size_chars - self.overlap_chars
            start = start + step
            
            if start <= chunks[-1].start_char if chunks else 0:
                start = end
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text before chunking."""
        if not text:
            return ""
        
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.replace('\t', ' ')
        text = text.strip()
        
        return text
    
    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find a good break point near the target end position."""
        search_start = max(start, end - int(self.chunk_size_chars * 0.2))
        search_text = text[search_start:end]
        
        break_patterns = [
            r'\n\n',
            r'[.!?]\s+',
            r'[,;:]\s+',
            r'\s+',
        ]
        
        for pattern in break_patterns:
            matches = list(re.finditer(pattern, search_text))
            if matches:
                last_match = matches[-1]
                return search_start + last_match.end()
        
        return end
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.chars_per_token


_chunker: Optional[TextChunker] = None


def get_chunker() -> TextChunker:
    global _chunker
    if _chunker is None:
        _chunker = TextChunker()
    return _chunker


def chunk_text(text: str) -> List[Chunk]:
    return get_chunker().chunk(text)


def chunk_text_with_settings(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Chunk]:
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk(text)

