"""
Text Chunking - Split documents into smaller pieces for embedding.

WHY CHUNKING?
=============
Embedding models have limitations:
1. MAX INPUT LENGTH: Most models cap at 512 tokens (~2000 chars)
2. SEMANTIC DILUTION: Long texts have "averaged" embeddings that lose specificity
3. RETRIEVAL PRECISION: Smaller chunks = more precise search results

Example of semantic dilution:
- Document about "Python programming" and "cooking recipes"
- Full-doc embedding: somewhere between programming and cooking (useless!)
- Chunked: separate embeddings for each topic (finds the right one)

CHUNKING STRATEGIES COMPARED:
=============================

1. FIXED-SIZE (Naive)
   ───────────────────
   Split every N characters, regardless of content.
   
   Pros: Simple, predictable chunk sizes
   Cons: Cuts mid-sentence, loses context
   
   Example: "The quick brown fox" with size=10
   → ["The quick ", "brown fox"]  # "brown" separated from context

2. SENTENCE-BASED
   ────────────────
   Split on sentence boundaries.
   
   Pros: Preserves sentence integrity
   Cons: Variable sizes, some sentences are very long
   
   Example: Split on ". ", "!", "?"

3. PARAGRAPH-BASED
   ─────────────────
   Split on double newlines.
   
   Pros: Preserves topic coherence
   Cons: Paragraphs vary wildly in size

4. RECURSIVE (LangChain-style)
   ────────────────────────────
   Try paragraph → sentence → word → character splits.
   
   Pros: Best of all worlds
   Cons: Complex, slower

5. OVERLAPPING WINDOWS (What we use)
   ──────────────────────────────────
   Fixed size with overlap between chunks.
   
   Pros: 
   - Predictable sizes
   - Context preserved at boundaries
   - Simple and effective
   
   Cons:
   - Some redundancy in storage
   - May cut mid-sentence (but overlap helps)

   Example: size=100, overlap=20
   
   Text: [===========================================]
   Chunk 1: [==========]
   Chunk 2:        [==========]    ← overlaps by 20 chars
   Chunk 3:               [==========]
   
   If a search query matches the boundary area, BOTH chunks are retrieved,
   providing full context.

WHY WE CHOSE OVERLAPPING WINDOWS:
=================================
1. Industry standard for RAG systems
2. Simple to implement and tune
3. Works well with all document types
4. Overlap mitigates boundary issues
5. Consistent chunk sizes = consistent embedding quality
"""

import logging
import re
from typing import List, Optional
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """
    Represents a single chunk of text.
    
    WHY A DATACLASS?
    ================
    @dataclass automatically generates:
    - __init__() with all fields as parameters
    - __repr__() for debugging
    - __eq__() for comparison
    
    This is cleaner than a regular class or dict:
    
    # Without dataclass:
    chunk = {"content": "...", "index": 0, "start": 0, "end": 100}
    print(chunk["content"])  # Error-prone string keys
    
    # With dataclass:
    chunk = Chunk(content="...", index=0, start_char=0, end_char=100)
    print(chunk.content)  # IDE autocomplete, type checking
    """
    content: str           # The chunk text
    index: int            # Position in document (0, 1, 2, ...)
    start_char: int       # Start character position in original
    end_char: int         # End character position in original
    token_count: int      # Approximate token count


class TextChunker:
    """
    Text chunker using overlapping windows strategy.
    
    HOW IT WORKS:
    =============
    1. Clean the text (normalize whitespace)
    2. Slide a window across the text
    3. Try to break at sentence boundaries when possible
    4. Create chunks with specified overlap
    
    PARAMETERS:
    ===========
    - chunk_size: Target size in tokens (~4 chars per token)
    - chunk_overlap: Number of tokens to overlap
    
    Default 512/50 means:
    - Each chunk is ~2048 characters
    - Chunks share ~200 characters at boundaries
    """
    
    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target chunk size in tokens (default from settings)
            chunk_overlap: Overlap between chunks in tokens (default from settings)
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        
        # Approximate chars per token (varies by language/content)
        # English averages ~4 chars per token
        # This is a heuristic; exact tokenization depends on the model
        self.chars_per_token = 4
        
        self.chunk_size_chars = self.chunk_size * self.chars_per_token
        self.overlap_chars = self.chunk_overlap * self.chars_per_token
        
        logger.info(
            f"TextChunker initialized: {self.chunk_size} tokens "
            f"(~{self.chunk_size_chars} chars), {self.chunk_overlap} overlap"
        )
    
    def chunk(self, text: str) -> List[Chunk]:
        """
        Split text into overlapping chunks.
        
        ALGORITHM:
        ==========
        1. Clean and normalize the text
        2. If text fits in one chunk, return single chunk
        3. Otherwise, use sliding window:
           a. Start at position 0
           b. Find end position (start + chunk_size)
           c. Adjust end to nearest sentence boundary
           d. Create chunk
           e. Move start forward (accounting for overlap)
           f. Repeat until end of text
        
        Args:
            text: The text to chunk
            
        Returns:
            List of Chunk objects
        """
        # Step 1: Clean the text
        text = self._clean_text(text)
        
        if not text:
            logger.warning("Empty text provided for chunking")
            return []
        
        # Step 2: Check if text fits in single chunk
        if len(text) <= self.chunk_size_chars:
            return [Chunk(
                content=text,
                index=0,
                start_char=0,
                end_char=len(text),
                token_count=self._estimate_tokens(text),
            )]
        
        # Step 3: Sliding window chunking
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size_chars
            
            # Don't exceed text length
            if end >= len(text):
                end = len(text)
            else:
                # Try to find a good break point (sentence boundary)
                end = self._find_break_point(text, start, end)
            
            # Extract chunk content
            chunk_content = text[start:end].strip()
            
            if chunk_content:  # Only add non-empty chunks
                chunks.append(Chunk(
                    content=chunk_content,
                    index=chunk_index,
                    start_char=start,
                    end_char=end,
                    token_count=self._estimate_tokens(chunk_content),
                ))
                chunk_index += 1
            
            # Move start forward (minus overlap)
            # This creates the overlapping effect
            step = self.chunk_size_chars - self.overlap_chars
            start = start + step
            
            # Safety: ensure we make progress
            if start <= chunks[-1].start_char if chunks else 0:
                start = end
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text before chunking.
        
        CLEANING STEPS:
        ===============
        1. Strip leading/trailing whitespace
        2. Normalize multiple newlines (max 2)
        3. Normalize multiple spaces (max 1)
        4. Remove null bytes and other control characters
        
        WHY CLEAN?
        ==========
        - Reduces noise in embeddings
        - Consistent chunk sizes
        - Better search relevance
        """
        if not text:
            return ""
        
        # Remove null bytes and control characters (except newline, tab)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Normalize multiple newlines to max 2 (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Normalize multiple spaces to single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Normalize tabs to spaces
        text = text.replace('\t', ' ')
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a good break point near the target end position.
        
        STRATEGY:
        =========
        Look for break points in order of preference:
        1. Paragraph break (double newline) - best for topic coherence
        2. Sentence end (. ! ?) - good for semantic completeness  
        3. Clause break (, ; :) - acceptable
        4. Word boundary (space) - minimum acceptable
        5. Original end position - last resort
        
        We search BACKWARDS from the target end, within a window.
        This ensures chunks don't exceed the target size.
        
        SEARCH WINDOW:
        ==============
        Look back up to 20% of chunk size for a good break point.
        If nothing found, use the original end position.
        """
        # Define search window (look back up to 20% of chunk size)
        search_start = max(start, end - int(self.chunk_size_chars * 0.2))
        search_text = text[search_start:end]
        
        # Try to find break points (in order of preference)
        break_patterns = [
            r'\n\n',           # Paragraph break (best)
            r'[.!?]\s+',       # Sentence end
            r'[,;:]\s+',       # Clause break
            r'\s+',            # Word boundary (last resort)
        ]
        
        for pattern in break_patterns:
            matches = list(re.finditer(pattern, search_text))
            if matches:
                # Use the last match (closest to target end)
                last_match = matches[-1]
                # Return position after the break character
                return search_start + last_match.end()
        
        # No good break point found, use original end
        return end
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        WHY ESTIMATE?
        =============
        Exact tokenization requires the actual tokenizer (model-specific).
        For chunking, an estimate is sufficient:
        - We use character-based chunking anyway
        - Token count is for informational purposes
        - 4 chars/token is a reasonable average for English
        
        More accurate options (if needed):
        - tiktoken library (OpenAI tokenizer)
        - transformers.AutoTokenizer (HuggingFace)
        """
        return len(text) // self.chars_per_token


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Singleton instance
_chunker: Optional[TextChunker] = None


def get_chunker() -> TextChunker:
    """Get or create the default chunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = TextChunker()
    return _chunker


def chunk_text(text: str) -> List[Chunk]:
    """
    Convenience function to chunk text using default settings.
    
    Usage:
        from app.utils.chunking import chunk_text
        
        chunks = chunk_text(document_content)
        for chunk in chunks:
            print(f"Chunk {chunk.index}: {chunk.token_count} tokens")
    """
    return get_chunker().chunk(text)


def chunk_text_with_settings(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Chunk]:
    """
    Chunk text with custom settings.
    
    Use this when you need different chunking parameters
    (e.g., smaller chunks for precise retrieval).
    """
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk(text)

