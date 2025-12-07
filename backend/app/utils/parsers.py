"""
Document Parsers - Extract text from various file formats.

WHY PARSERS?
============
Different file formats store text differently:
- PDF: Binary format with fonts, layouts, images. Text is embedded in content streams.
- DOCX: Actually a ZIP file containing XML files with text in <w:t> tags.
- Markdown: Plain text with formatting syntax (# headers, **bold**, etc.)
- TXT: Plain text, no parsing needed.

Each parser extracts the raw text content so we can:
1. Chunk it into smaller pieces
2. Generate embeddings for semantic search
3. Store in the vector database

LIBRARIES USED:
==============
- PyMuPDF (fitz): Fast PDF parsing, handles most PDFs well
- python-docx: Microsoft's recommended library for DOCX
- markdown + BeautifulSoup: Convert MD to HTML, then strip tags
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO

import fitz  # PyMuPDF
from docx import Document as DocxDocument
import markdown
from bs4 import BeautifulSoup

from ..models.documents import DocumentType

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    Abstract base class for document parsers.
    
    WHY ABSTRACT BASE CLASS?
    ========================
    Using ABC (Abstract Base Class) enforces a contract:
    - All parsers MUST implement `parse()` and `parse_bytes()`
    - This allows us to swap parsers without changing calling code
    - Enables polymorphism: treat all parsers the same way
    
    Example:
        parser = get_parser(DocumentType.PDF)
        text = parser.parse(file_path)  # Works for any parser type!
    """
    
    @abstractmethod
    def parse(self, file_path: Path) -> str:
        """
        Parse a document from a file path.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted plain text content
        """
        pass
    
    @abstractmethod
    def parse_bytes(self, content: bytes, filename: str) -> str:
        """
        Parse a document from bytes (for uploaded files).
        
        WHY BYTES?
        ==========
        When users upload files via API, we receive raw bytes, not file paths.
        This method handles that case without writing to disk first.
        
        Args:
            content: Raw file bytes
            filename: Original filename (for logging/debugging)
            
        Returns:
            Extracted plain text content
        """
        pass
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from document (optional override).
        
        Default implementation returns basic file info.
        Subclasses can override to extract format-specific metadata
        (e.g., PDF author, creation date, page count).
        """
        return {
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        }


class PDFParser(BaseParser):
    """
    PDF Parser using PyMuPDF (fitz).
    
    WHY PyMuPDF?
    ============
    Compared to alternatives:
    
    | Library      | Speed  | Quality | Memory | Install |
    |--------------|--------|---------|--------|---------|
    | PyMuPDF      | Fast   | Good    | Low    | Easy    |
    | pdfplumber   | Slow   | Best    | High   | Easy    |
    | PyPDF2       | Medium | Poor    | Low    | Easy    |
    | pdfminer     | Slow   | Good    | High   | Complex |
    
    PyMuPDF is the best balance of speed and quality for most PDFs.
    
    HOW PDF TEXT EXTRACTION WORKS:
    ==============================
    1. Open the PDF file (loads into memory)
    2. Iterate through each page
    3. Call get_text() which reads the content stream
    4. Content stream contains text positioning commands
    5. PyMuPDF reconstructs reading order from positions
    6. Returns plain text with newlines between blocks
    """
    
    def parse(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        logger.info(f"Parsing PDF: {file_path}")
        
        try:
            # Open the PDF document
            # fitz.open() returns a Document object with page access
            doc = fitz.open(file_path)
            
            text_parts = []
            for page_num, page in enumerate(doc):
                # get_text() extracts text in reading order
                # "text" mode gives plain text (vs "html", "dict", etc.)
                page_text = page.get_text("text")
                
                if page_text.strip():
                    text_parts.append(page_text)
                    
            doc.close()
            
            # Join pages with double newlines for clear separation
            full_text = "\n\n".join(text_parts)
            
            logger.info(f"Extracted {len(full_text)} characters from {len(text_parts)} pages")
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise ValueError(f"Failed to parse PDF: {e}")
    
    def parse_bytes(self, content: bytes, filename: str) -> str:
        """Extract text from PDF bytes."""
        logger.info(f"Parsing PDF from bytes: {filename}")
        
        try:
            # fitz can open from bytes using stream parameter
            # filetype="pdf" tells it not to guess from extension
            doc = fitz.open(stream=content, filetype="pdf")
            
            text_parts = []
            for page in doc:
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(page_text)
                    
            doc.close()
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to parse PDF bytes {filename}: {e}")
            raise ValueError(f"Failed to parse PDF: {e}")
    
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract PDF-specific metadata."""
        base_meta = super().extract_metadata(file_path)
        
        try:
            doc = fitz.open(file_path)
            
            # PDF metadata is stored in the document catalog
            meta = doc.metadata
            base_meta.update({
                "page_count": doc.page_count,
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "subject": meta.get("subject", ""),
                "creator": meta.get("creator", ""),
                "creation_date": meta.get("creationDate", ""),
            })
            
            doc.close()
            
        except Exception as e:
            logger.warning(f"Could not extract PDF metadata: {e}")
            
        return base_meta


class DOCXParser(BaseParser):
    """
    DOCX Parser using python-docx.
    
    WHY python-docx?
    ================
    - Official Microsoft-recommended library
    - Handles complex DOCX features (tables, headers, etc.)
    - Well-maintained and documented
    
    HOW DOCX FILES WORK:
    ====================
    A .docx file is actually a ZIP archive containing:
    
    my_document.docx/
    ├── [Content_Types].xml    # MIME types for parts
    ├── _rels/                 # Relationships between parts
    ├── docProps/              # Document properties (author, etc.)
    └── word/
        ├── document.xml       # Main document content <-- TEXT IS HERE
        ├── styles.xml         # Style definitions
        ├── fontTable.xml      # Font information
        └── media/             # Embedded images
    
    Text is in document.xml as:
    <w:p>                      # Paragraph
      <w:r>                    # Run (text with same formatting)
        <w:t>Hello World</w:t> # Actual text
      </w:r>
    </w:p>
    
    python-docx parses this XML structure and gives us Paragraph objects.
    """
    
    def parse(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        logger.info(f"Parsing DOCX: {file_path}")
        
        try:
            # Document() opens and parses the DOCX ZIP structure
            doc = DocxDocument(file_path)
            
            # Extract text from all paragraphs
            # doc.paragraphs is a list of Paragraph objects
            paragraphs = []
            for para in doc.paragraphs:
                # para.text joins all runs in the paragraph
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            # Also extract text from tables (often missed!)
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        paragraphs.append(" | ".join(row_text))
            
            full_text = "\n\n".join(paragraphs)
            
            logger.info(f"Extracted {len(full_text)} characters from DOCX")
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to parse DOCX {file_path}: {e}")
            raise ValueError(f"Failed to parse DOCX: {e}")
    
    def parse_bytes(self, content: bytes, filename: str) -> str:
        """Extract text from DOCX bytes."""
        logger.info(f"Parsing DOCX from bytes: {filename}")
        
        try:
            # python-docx can open from file-like objects
            # BytesIO wraps bytes to behave like a file
            doc = DocxDocument(BytesIO(content))
            
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        paragraphs.append(" | ".join(row_text))
            
            return "\n\n".join(paragraphs)
            
        except Exception as e:
            logger.error(f"Failed to parse DOCX bytes {filename}: {e}")
            raise ValueError(f"Failed to parse DOCX: {e}")


class MarkdownParser(BaseParser):
    """
    Markdown Parser - converts MD to plain text.
    
    WHY TWO-STEP PROCESS (MD → HTML → TEXT)?
    ========================================
    Markdown has many edge cases:
    - # Headers
    - **bold**, *italic*, ~~strikethrough~~
    - [links](url), ![images](url)
    - ```code blocks```
    - > blockquotes
    - Lists, tables, footnotes...
    
    Instead of handling all these with regex (error-prone), we:
    1. Convert MD to HTML (markdown library handles all syntax)
    2. Strip HTML tags (BeautifulSoup handles all tag variants)
    
    This is more robust than direct MD→text conversion.
    
    EXAMPLE:
    ========
    Input:  "# Hello **World**"
    Step 1: "<h1>Hello <strong>World</strong></h1>"
    Step 2: "Hello World"
    """
    
    def __init__(self):
        """Initialize markdown converter with extensions."""
        # Extensions add support for extra MD features
        # 'tables': GitHub-style tables
        # 'fenced_code': ```code blocks```
        # 'nl2br': Convert newlines to <br> (preserves line breaks)
        self.md = markdown.Markdown(
            extensions=['tables', 'fenced_code', 'nl2br']
        )
    
    def parse(self, file_path: Path) -> str:
        """Extract text from Markdown file."""
        logger.info(f"Parsing Markdown: {file_path}")
        
        try:
            # Read the raw markdown text
            content = file_path.read_text(encoding='utf-8')
            return self._convert_to_text(content)
            
        except Exception as e:
            logger.error(f"Failed to parse Markdown {file_path}: {e}")
            raise ValueError(f"Failed to parse Markdown: {e}")
    
    def parse_bytes(self, content: bytes, filename: str) -> str:
        """Extract text from Markdown bytes."""
        logger.info(f"Parsing Markdown from bytes: {filename}")
        
        try:
            # Decode bytes to string (assume UTF-8)
            text = content.decode('utf-8')
            return self._convert_to_text(text)
            
        except Exception as e:
            logger.error(f"Failed to parse Markdown bytes {filename}: {e}")
            raise ValueError(f"Failed to parse Markdown: {e}")
    
    def _convert_to_text(self, md_content: str) -> str:
        """
        Convert markdown to plain text.
        
        Process:
        1. Reset the markdown converter (clears state from previous conversions)
        2. Convert markdown → HTML
        3. Parse HTML with BeautifulSoup
        4. Extract text (get_text() strips all tags)
        5. Clean up whitespace
        """
        # Reset is important! MD converter is stateful (footnotes, etc.)
        self.md.reset()
        
        # Convert to HTML
        html = self.md.convert(md_content)
        
        # Parse HTML and extract text
        # 'html.parser' is Python's built-in parser (no extra deps)
        soup = BeautifulSoup(html, 'html.parser')
        
        # get_text() extracts all text, separator adds space between elements
        text = soup.get_text(separator='\n')
        
        # Clean up excessive whitespace while preserving paragraph breaks
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        logger.info(f"Converted {len(md_content)} chars MD to {len(text)} chars text")
        return text


class TextParser(BaseParser):
    """
    Plain text parser - simplest case.
    
    WHY HAVE A PARSER FOR TEXT?
    ===========================
    Even plain text needs handling:
    1. Character encoding detection/conversion (UTF-8, Latin-1, etc.)
    2. Line ending normalization (Windows \r\n vs Unix \n)
    3. BOM (Byte Order Mark) removal
    4. Consistent interface with other parsers
    
    Having a TextParser means our code can treat all file types the same:
        parser = get_parser(doc_type)
        text = parser.parse(file)  # Works for any type!
    """
    
    def parse(self, file_path: Path) -> str:
        """Read text from plain text file."""
        logger.info(f"Parsing text file: {file_path}")
        
        try:
            # Try UTF-8 first (most common)
            try:
                content = file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Fall back to Latin-1 (handles any byte sequence)
                content = file_path.read_text(encoding='latin-1')
            
            # Normalize line endings to Unix style
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]
            
            logger.info(f"Read {len(content)} characters from text file")
            return content
            
        except Exception as e:
            logger.error(f"Failed to parse text file {file_path}: {e}")
            raise ValueError(f"Failed to parse text file: {e}")
    
    def parse_bytes(self, content: bytes, filename: str) -> str:
        """Convert bytes to text."""
        logger.info(f"Parsing text from bytes: {filename}")
        
        try:
            # Try UTF-8 first
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                text = content.decode('latin-1')
            
            # Normalize line endings
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            
            # Remove BOM
            if text.startswith('\ufeff'):
                text = text[1:]
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to parse text bytes {filename}: {e}")
            raise ValueError(f"Failed to parse text: {e}")


# =============================================================================
# PARSER FACTORY
# =============================================================================

# Registry mapping document types to parser classes
# Using a dict instead of if/elif makes it easy to add new parsers
PARSER_REGISTRY: Dict[DocumentType, type] = {
    DocumentType.PDF: PDFParser,
    DocumentType.DOCX: DOCXParser,
    DocumentType.MARKDOWN: MarkdownParser,
    DocumentType.TXT: TextParser,
}

# Singleton instances (parsers are stateless, reuse them)
_parser_instances: Dict[DocumentType, BaseParser] = {}


def get_parser(doc_type: DocumentType) -> BaseParser:
    """
    Factory function to get a parser for a document type.
    
    WHY FACTORY PATTERN?
    ====================
    1. Encapsulation: Calling code doesn't need to know parser class names
    2. Singleton: Reuses parser instances (they're stateless)
    3. Extensibility: Add new parsers by updating PARSER_REGISTRY
    4. Type safety: Returns BaseParser, works with any parser
    
    Usage:
        parser = get_parser(DocumentType.PDF)
        text = parser.parse(file_path)
    """
    if doc_type not in _parser_instances:
        parser_class = PARSER_REGISTRY.get(doc_type)
        if parser_class is None:
            raise ValueError(f"No parser available for document type: {doc_type}")
        _parser_instances[doc_type] = parser_class()
    
    return _parser_instances[doc_type]


def detect_document_type(filename: str) -> DocumentType:
    """
    Detect document type from filename extension.
    
    WHY EXTENSION-BASED DETECTION?
    ==============================
    Alternatives considered:
    
    1. Magic bytes (file signature): More accurate but complex
       - PDF starts with "%PDF-"
       - DOCX starts with "PK" (it's a ZIP)
       - Requires reading file content
    
    2. MIME type: Requires additional library or OS calls
    
    3. Extension: Simple, fast, usually correct
       - Users name files correctly 99% of the time
       - If wrong, parser will fail with clear error
    
    For a personal knowledge base, extension detection is sufficient.
    """
    extension = Path(filename).suffix.lower()
    
    extension_map = {
        '.pdf': DocumentType.PDF,
        '.docx': DocumentType.DOCX,
        '.doc': DocumentType.DOCX,  # Try DOCX parser for .doc too
        '.md': DocumentType.MARKDOWN,
        '.markdown': DocumentType.MARKDOWN,
        '.txt': DocumentType.TXT,
        '.text': DocumentType.TXT,
        '.log': DocumentType.TXT,
        '.csv': DocumentType.TXT,  # Treat CSV as text for now
        '.json': DocumentType.TXT,  # Treat JSON as text
        '.xml': DocumentType.TXT,   # Treat XML as text
        '.html': DocumentType.TXT,  # Could add HTML parser later
        '.htm': DocumentType.TXT,
    }
    
    doc_type = extension_map.get(extension)
    if doc_type is None:
        raise ValueError(f"Unsupported file type: {extension}")
    
    return doc_type


def parse_document(file_path: Path) -> tuple[str, DocumentType]:
    """
    Convenience function to detect type and parse in one call.
    
    Returns:
        Tuple of (extracted_text, document_type)
    """
    doc_type = detect_document_type(file_path.name)
    parser = get_parser(doc_type)
    text = parser.parse(file_path)
    return text, doc_type


def parse_document_bytes(content: bytes, filename: str) -> tuple[str, DocumentType]:
    """
    Parse document from bytes with automatic type detection.
    
    Returns:
        Tuple of (extracted_text, document_type)
    """
    doc_type = detect_document_type(filename)
    parser = get_parser(doc_type)
    text = parser.parse_bytes(content, filename)
    return text, doc_type

