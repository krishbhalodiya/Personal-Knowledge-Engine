"""
Live/On-Demand Local File Search Service.

Searches local files in real-time without pre-indexing.
This saves memory and storage while providing comprehensive search.
"""

import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes

from ..config import settings
from ..utils.parsers import detect_document_type, parse_document_bytes
from .local_scanner import get_local_scanner, SKIP_FOLDERS, SCANNABLE_EXTENSIONS

logger = logging.getLogger(__name__)

# Extensions we can quickly scan for content
QUICK_SCAN_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.py', '.js', '.ts', '.tsx', '.jsx',
    '.html', '.css', '.json', '.yaml', '.yml', '.csv', '.log',
    '.xml', '.rst', '.note', '.notes',
}

# Max file size to read in live search (1MB)
MAX_LIVE_SCAN_SIZE = 1 * 1024 * 1024

# Max files to scan per query
MAX_FILES_PER_QUERY = 100


@dataclass
class LiveSearchResult:
    """Result from live local file search."""
    path: str
    filename: str
    display_path: str
    relevance_score: float
    match_type: str  # "filename", "content", "both"
    preview: str
    file_size: int
    extension: str


class LiveSearchService:
    """Service for searching local files on-demand."""
    
    def __init__(self):
        self.scanner = get_local_scanner()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def _tokenize_query(self, query: str) -> Set[str]:
        """Break query into searchable tokens."""
        # Simple tokenization - split on non-alphanumeric
        words = re.findall(r'\w+', query.lower())
        # Filter out very short words
        return {w for w in words if len(w) > 2}
    
    def _score_filename_match(self, filename: str, tokens: Set[str]) -> float:
        """Score how well a filename matches the query tokens."""
        filename_lower = filename.lower()
        filename_tokens = set(re.findall(r'\w+', filename_lower))
        
        if not tokens:
            return 0.0
        
        # Check for exact substring matches
        matches = sum(1 for t in tokens if t in filename_lower)
        
        # Check for token overlap
        overlap = len(tokens & filename_tokens)
        
        # Combined score
        score = (matches * 0.5 + overlap * 0.5) / len(tokens)
        return min(score, 1.0)
    
    def _score_content_match(self, content: str, tokens: Set[str]) -> tuple[float, str]:
        """Score how well content matches and extract preview."""
        content_lower = content.lower()
        
        if not tokens:
            return 0.0, ""
        
        # Count token occurrences
        total_matches = 0
        first_match_pos = -1
        
        for token in tokens:
            count = content_lower.count(token)
            total_matches += min(count, 10)  # Cap to avoid over-weighting
            
            if first_match_pos == -1 and count > 0:
                first_match_pos = content_lower.find(token)
        
        if total_matches == 0:
            return 0.0, ""
        
        # Extract preview around first match
        preview = ""
        if first_match_pos >= 0:
            start = max(0, first_match_pos - 100)
            end = min(len(content), first_match_pos + 200)
            preview = content[start:end].strip()
            if start > 0:
                preview = "..." + preview
            if end < len(content):
                preview = preview + "..."
        
        # Score based on match density
        score = min(total_matches / (len(tokens) * 3), 1.0)
        
        return score, preview
    
    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content for searching."""
        try:
            # Check size
            if file_path.stat().st_size > MAX_LIVE_SCAN_SIZE:
                return None
            
            ext = file_path.suffix.lower()
            
            # For text files, read directly
            if ext in QUICK_SCAN_EXTENSIONS:
                try:
                    return file_path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        return file_path.read_text(encoding='latin-1')
                    except:
                        return None
            
            # For other supported files, use parsers
            if ext in SCANNABLE_EXTENSIONS:
                try:
                    content = file_path.read_bytes()
                    text, _ = parse_document_bytes(content, file_path.name)
                    return text
                except:
                    return None
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to read {file_path}: {e}")
            return None
    
    def _search_file(
        self, 
        file_path: Path, 
        tokens: Set[str],
        search_content: bool = True
    ) -> Optional[LiveSearchResult]:
        """Search a single file and return result if relevant."""
        try:
            filename = file_path.name
            ext = file_path.suffix.lower()
            
            # Score filename match
            filename_score = self._score_filename_match(filename, tokens)
            
            # Score content match
            content_score = 0.0
            preview = ""
            
            if search_content and ext in QUICK_SCAN_EXTENSIONS:
                content = self._read_file_content(file_path)
                if content:
                    content_score, preview = self._score_content_match(content, tokens)
            
            # Combined relevance
            if filename_score == 0 and content_score == 0:
                return None
            
            # Determine match type
            if filename_score > 0 and content_score > 0:
                match_type = "both"
                relevance = filename_score * 0.4 + content_score * 0.6
            elif filename_score > 0:
                match_type = "filename"
                relevance = filename_score * 0.7
            else:
                match_type = "content"
                relevance = content_score * 0.8
            
            # Skip very low relevance
            if relevance < 0.1:
                return None
            
            # Get display path
            home = str(Path.home())
            display_path = str(file_path)
            if display_path.startswith(home):
                display_path = "~" + display_path[len(home):]
            
            # Get preview from content or filename
            if not preview:
                preview = f"File: {filename}"
            
            return LiveSearchResult(
                path=str(file_path),
                filename=filename,
                display_path=display_path,
                relevance_score=relevance,
                match_type=match_type,
                preview=preview[:300],
                file_size=file_path.stat().st_size,
                extension=ext,
            )
            
        except Exception as e:
            logger.debug(f"Error searching file {file_path}: {e}")
            return None
    
    def _discover_searchable_files(self) -> List[Path]:
        """Get list of files from enabled sources."""
        files = []
        
        for source in self.scanner.sources:
            if not source.enabled:
                continue
            
            root = Path(source.path)
            if not root.exists():
                continue
            
            try:
                if source.recursive:
                    for item in root.rglob('*'):
                        if item.is_file():
                            # Skip folders
                            skip = False
                            for parent in item.parents:
                                if parent == root:
                                    break
                                if parent.name in SKIP_FOLDERS or parent.name.startswith('.'):
                                    skip = True
                                    break
                            
                            if not skip:
                                ext = item.suffix.lower()
                                if ext in SCANNABLE_EXTENSIONS or ext in QUICK_SCAN_EXTENSIONS:
                                    files.append(item)
                else:
                    for item in root.iterdir():
                        if item.is_file():
                            ext = item.suffix.lower()
                            if ext in SCANNABLE_EXTENSIONS or ext in QUICK_SCAN_EXTENSIONS:
                                files.append(item)
                                
            except PermissionError:
                continue
        
        return files
    
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        search_content: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search local files on-demand without pre-indexing.
        
        Args:
            query: Search query
            limit: Max results to return
            search_content: Whether to search inside file contents
            
        Returns:
            List of matching files with relevance scores
        """
        tokens = self._tokenize_query(query)
        
        if not tokens:
            return []
        
        logger.info(f"Live searching local files for: {query} (tokens: {tokens})")
        
        # Discover files to search
        files = self._discover_searchable_files()
        logger.info(f"Found {len(files)} files to search")
        
        # Limit files to prevent timeout
        if len(files) > MAX_FILES_PER_QUERY:
            # Prioritize by extension and size
            files.sort(key=lambda f: (
                0 if f.suffix.lower() in QUICK_SCAN_EXTENSIONS else 1,
                f.stat().st_size if f.exists() else float('inf')
            ))
            files = files[:MAX_FILES_PER_QUERY]
        
        # Search files in parallel
        results: List[LiveSearchResult] = []
        
        futures = {
            self.executor.submit(self._search_file, f, tokens, search_content): f 
            for f in files
        }
        
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Search task failed: {e}")
        
        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        # Return top results
        return [
            {
                "path": r.path,
                "filename": r.filename,
                "display_path": r.display_path,
                "relevance_score": round(r.relevance_score, 3),
                "match_type": r.match_type,
                "preview": r.preview,
                "file_size": r.file_size,
                "extension": r.extension,
                "source": "local_live",
            }
            for r in results[:limit]
        ]
    
    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get full content of a specific file."""
        path = Path(file_path)
        if not path.exists():
            return None
        
        return self._read_file_content(path)


# Singleton instance
_live_search_service: Optional[LiveSearchService] = None


def get_live_search_service() -> LiveSearchService:
    """Get singleton live search service instance."""
    global _live_search_service
    if _live_search_service is None:
        _live_search_service = LiveSearchService()
    return _live_search_service

