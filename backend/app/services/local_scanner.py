"""
Local Filesystem Scanner Service.

Scans configured local folders for documents and indexes them.
Supports watching for changes and auto-indexing new/modified files.
"""

import logging
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
import asyncio
from concurrent.futures import ThreadPoolExecutor

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent

from ..config import settings
from ..utils.parsers import detect_document_type, parse_document_bytes
from ..models.documents import DocumentType

logger = logging.getLogger(__name__)

# Supported file extensions for scanning
SCANNABLE_EXTENSIONS = {
    # Documents
    '.pdf', '.docx', '.doc', '.txt', '.text', '.md', '.markdown',
    '.rtf', '.odt',
    # Code/Text
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.xml',
    '.yaml', '.yml', '.csv', '.log',
    # Images (OCR)
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp',
    # Notes
    '.note', '.notes',
}

# Folders to skip
SKIP_FOLDERS = {
    '.git', '.svn', 'node_modules', '__pycache__', '.cache', 
    'venv', '.venv', 'env', '.env', '.idea', '.vscode',
    'Library', 'Caches', 'Logs', '.Trash', 'Applications',
}

# Default folders to scan (macOS)
DEFAULT_SCAN_FOLDERS = [
    "~/Documents",
    "~/Desktop", 
    "~/Downloads",
    "~/Notes",
    # iCloud Drive
    "~/Library/Mobile Documents/com~apple~CloudDocs",
]


@dataclass
class FolderSource:
    """Configuration for a folder to scan."""
    path: str
    enabled: bool = False  # DISABLED BY DEFAULT - requires explicit user action to enable
    recursive: bool = True
    file_types: List[str] = None  # None = all supported types
    last_scan: Optional[str] = None
    file_count: int = 0
    
    def __post_init__(self):
        if self.file_types is None:
            self.file_types = list(SCANNABLE_EXTENSIONS)


@dataclass
class ScannedFile:
    """Metadata for a scanned file."""
    path: str
    filename: str
    extension: str
    size_bytes: int
    modified_at: str
    content_hash: str
    indexed: bool = False
    document_id: Optional[str] = None


class LocalScannerService:
    """Service for scanning and watching local folders."""
    
    def __init__(self):
        self.config_path = settings.data_dir / "folder_sources.json"
        self.scan_state_path = settings.data_dir / "scan_state.json"
        self.sources: List[FolderSource] = []
        self.scan_state: Dict[str, ScannedFile] = {}  # path -> ScannedFile
        self.observer: Optional[Observer] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._load_config()
        self._load_scan_state()
    
    def _load_config(self):
        """Load folder sources configuration."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                self.sources = [FolderSource(**s) for s in data.get("sources", [])]
                logger.info(f"Loaded {len(self.sources)} folder sources")
            except Exception as e:
                logger.error(f"Failed to load folder config: {e}")
                self._init_default_sources()
        else:
            self._init_default_sources()
    
    def _init_default_sources(self):
        """Initialize with default folder sources."""
        self.sources = []
        for folder in DEFAULT_SCAN_FOLDERS:
            expanded = Path(folder).expanduser()
            if expanded.exists():
                self.sources.append(FolderSource(
                    path=str(expanded),
                    enabled=False,  # Disabled by default - user must enable
                ))
        self._save_config()
        logger.info(f"Initialized {len(self.sources)} default folder sources")
    
    def _save_config(self):
        """Save folder sources configuration."""
        try:
            data = {"sources": [asdict(s) for s in self.sources]}
            self.config_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save folder config: {e}")
    
    def _load_scan_state(self):
        """Load scan state (indexed files tracking)."""
        if self.scan_state_path.exists():
            try:
                data = json.loads(self.scan_state_path.read_text())
                self.scan_state = {
                    k: ScannedFile(**v) for k, v in data.items()
                }
                logger.info(f"Loaded scan state with {len(self.scan_state)} files")
            except Exception as e:
                logger.error(f"Failed to load scan state: {e}")
                self.scan_state = {}
    
    def _save_scan_state(self):
        """Save scan state."""
        try:
            data = {k: asdict(v) for k, v in self.scan_state.items()}
            self.scan_state_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save scan state: {e}")
    
    def get_sources(self) -> List[Dict[str, Any]]:
        """Get all configured folder sources."""
        result = []
        for source in self.sources:
            path = Path(source.path)
            result.append({
                **asdict(source),
                "exists": path.exists(),
                "display_name": self._get_display_name(source.path),
            })
        return result
    
    def _get_display_name(self, path: str) -> str:
        """Get a user-friendly display name for a path."""
        home = str(Path.home())
        if path.startswith(home):
            # Check for special folders
            if "Mobile Documents/com~apple~CloudDocs" in path:
                subpath = path.split("com~apple~CloudDocs")[-1]
                return f"iCloud Drive{subpath}" if subpath else "iCloud Drive"
            return path.replace(home, "~")
        return path
    
    def add_source(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Add a new folder source."""
        expanded = Path(path).expanduser().resolve()
        
        if not expanded.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        if not expanded.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        # Check if already exists
        for source in self.sources:
            if Path(source.path).resolve() == expanded:
                raise ValueError(f"Folder already added: {path}")
        
        source = FolderSource(
            path=str(expanded),
            enabled=True,
            recursive=recursive,
        )
        self.sources.append(source)
        self._save_config()
        
        return {
            **asdict(source),
            "exists": True,
            "display_name": self._get_display_name(str(expanded)),
        }
    
    def update_source(self, path: str, enabled: Optional[bool] = None, recursive: Optional[bool] = None):
        """Update a folder source configuration."""
        for source in self.sources:
            if source.path == path:
                if enabled is not None:
                    source.enabled = enabled
                if recursive is not None:
                    source.recursive = recursive
                self._save_config()
                return asdict(source)
        raise ValueError(f"Source not found: {path}")
    
    def remove_source(self, path: str):
        """Remove a folder source."""
        self.sources = [s for s in self.sources if s.path != path]
        self._save_config()
    
    def _should_scan_file(self, file_path: Path, source: FolderSource) -> bool:
        """Check if a file should be scanned."""
        # Check extension
        ext = file_path.suffix.lower()
        if ext not in SCANNABLE_EXTENSIONS:
            return False
        
        if source.file_types and ext not in source.file_types:
            return False
        
        # Skip hidden files
        if file_path.name.startswith('.'):
            return False
        
        # Skip very large files (> 50MB)
        try:
            if file_path.stat().st_size > 50 * 1024 * 1024:
                return False
        except OSError:
            return False
        
        return True
    
    def _should_skip_folder(self, folder: Path) -> bool:
        """Check if a folder should be skipped."""
        return folder.name in SKIP_FOLDERS or folder.name.startswith('.')
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute content hash for a file."""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def discover_files(self, source: FolderSource) -> List[Path]:
        """Discover scannable files in a source folder."""
        files = []
        root = Path(source.path)
        
        if not root.exists():
            logger.warning(f"Source path does not exist: {source.path}")
            return files
        
        try:
            if source.recursive:
                for item in root.rglob('*'):
                    if item.is_file():
                        # Check parent folders
                        skip = False
                        for parent in item.parents:
                            if parent == root:
                                break
                            if self._should_skip_folder(parent):
                                skip = True
                                break
                        
                        if not skip and self._should_scan_file(item, source):
                            files.append(item)
            else:
                for item in root.iterdir():
                    if item.is_file() and self._should_scan_file(item, source):
                        files.append(item)
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {source.path}: {e}")
        
        return files
    
    async def scan_folder(
        self, 
        source_path: str,
        ingestion_service,  # Avoid circular import
        progress_callback=None,
    ) -> Dict[str, int]:
        """Scan a folder and index new/modified files."""
        
        # Find the source
        source = None
        for s in self.sources:
            if s.path == source_path:
                source = s
                break
        
        if not source:
            raise ValueError(f"Source not found: {source_path}")
        
        if not source.enabled:
            raise ValueError(f"Source is disabled: {source_path}")
        
        stats = {
            "discovered": 0,
            "new": 0,
            "modified": 0,
            "unchanged": 0,
            "indexed": 0,
            "errors": 0,
        }
        
        # Discover files
        files = self.discover_files(source)
        stats["discovered"] = len(files)
        
        logger.info(f"Discovered {len(files)} files in {source_path}")
        
        # Process files
        for i, file_path in enumerate(files):
            try:
                str_path = str(file_path)
                file_stat = file_path.stat()
                content_hash = self._compute_hash(file_path)
                
                # Check if already indexed
                existing = self.scan_state.get(str_path)
                
                if existing:
                    if existing.content_hash == content_hash:
                        stats["unchanged"] += 1
                        continue
                    else:
                        stats["modified"] += 1
                        # Delete old document if exists
                        if existing.document_id:
                            try:
                                await ingestion_service.delete_document(existing.document_id)
                            except Exception:
                                pass
                else:
                    stats["new"] += 1
                
                # Read and index file
                content = file_path.read_bytes()
                
                # Ingest with source metadata
                doc = await ingestion_service.ingest_bytes(
                    content=content,
                    filename=file_path.name,
                    title=file_path.stem,
                    metadata={
                        "source": "local_folder",
                        "source_path": source_path,
                        "full_path": str_path,
                        "display_path": self._get_display_name(str_path),
                    }
                )
                
                # Update scan state
                self.scan_state[str_path] = ScannedFile(
                    path=str_path,
                    filename=file_path.name,
                    extension=file_path.suffix.lower(),
                    size_bytes=file_stat.st_size,
                    modified_at=datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    content_hash=content_hash,
                    indexed=True,
                    document_id=doc.id,
                )
                
                stats["indexed"] += 1
                
                if progress_callback:
                    progress_callback(i + 1, len(files), file_path.name)
                    
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
                stats["errors"] += 1
        
        # Update source stats
        source.last_scan = datetime.utcnow().isoformat()
        source.file_count = stats["indexed"] + stats["unchanged"]
        self._save_config()
        self._save_scan_state()
        
        logger.info(f"Scan complete: {stats}")
        return stats
    
    def get_scan_stats(self) -> Dict[str, Any]:
        """Get overall scan statistics."""
        total_files = len(self.scan_state)
        total_size = sum(f.size_bytes for f in self.scan_state.values())
        
        by_extension = {}
        for f in self.scan_state.values():
            ext = f.extension
            if ext not in by_extension:
                by_extension[ext] = 0
            by_extension[ext] += 1
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_extension": by_extension,
            "sources": [
                {
                    "path": s.path,
                    "display_name": self._get_display_name(s.path),
                    "enabled": s.enabled,
                    "file_count": s.file_count,
                    "last_scan": s.last_scan,
                }
                for s in self.sources
            ]
        }


# Singleton instance
_scanner_service: Optional[LocalScannerService] = None


def get_local_scanner() -> LocalScannerService:
    """Get singleton scanner service instance."""
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = LocalScannerService()
    return _scanner_service

