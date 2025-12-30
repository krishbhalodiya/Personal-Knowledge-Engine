"""
Local Folder Sources API Routes.

Manage local folders to scan and index for the knowledge base.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from ..services.local_scanner import LocalScannerService, get_local_scanner, get_scan_manager
from ..services.ingestion import IngestionService, get_ingestion_service
from ..services.live_search import LiveSearchService, get_live_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/folders", tags=["folders"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AddFolderRequest(BaseModel):
    """Request to add a new folder source."""
    path: str = Field(..., description="Path to the folder (can use ~)")
    recursive: bool = Field(True, description="Scan subfolders")


class UpdateFolderRequest(BaseModel):
    """Request to update a folder source."""
    enabled: Optional[bool] = None
    recursive: Optional[bool] = None


class ScanResponse(BaseModel):
    """Response from a folder scan."""
    discovered: int
    new: int
    modified: int
    unchanged: int
    indexed: int
    errors: int


class ScanStatusResponse(BaseModel):
    """Response for scan status."""
    status: str
    total_files: int
    processed_files: int
    current_file: Optional[str]
    progress_percent: float
    files_indexed: int
    errors: int
    estimated_remaining_seconds: Optional[float]
    message: Optional[str]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/sources")
async def list_folder_sources(
    scanner: LocalScannerService = Depends(get_local_scanner),
):
    """
    List all configured folder sources.
    
    Returns folders that can be scanned, including:
    - Default folders (Documents, Desktop, Downloads, iCloud)
    - Custom added folders
    """
    return {
        "sources": scanner.get_sources(),
        "stats": scanner.get_scan_stats(),
    }


@router.post("/sources")
async def add_folder_source(
    request: AddFolderRequest,
    scanner: LocalScannerService = Depends(get_local_scanner),
):
    """
    Add a new folder to scan.
    
    The folder must exist and be accessible.
    Use ~ for home directory (e.g., ~/Documents/MyProject)
    """
    try:
        source = scanner.add_source(request.path, request.recursive)
        return {"message": "Folder added successfully", "source": source}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/sources/{path:path}")
async def update_folder_source(
    path: str,
    request: UpdateFolderRequest,
    scanner: LocalScannerService = Depends(get_local_scanner),
):
    """
    Update a folder source configuration.
    
    Can enable/disable scanning or change recursive setting.
    """
    # Expand path if it starts with ~
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    
    try:
        source = scanner.update_source(
            path,
            enabled=request.enabled,
            recursive=request.recursive,
        )
        return {"message": "Folder updated", "source": source}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/sources/{path:path}")
async def remove_folder_source(
    path: str,
    scanner: LocalScannerService = Depends(get_local_scanner),
):
    """
    Remove a folder from the scan list.
    
    Note: This doesn't delete already indexed documents.
    """
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    
    scanner.remove_source(path)
    return {"message": "Folder removed"}


@router.post("/scan/stop")
async def stop_scan():
    """Stop the current scan operation."""
    manager = get_scan_manager()
    manager.stop_scan()
    return {"message": "Scan stop requested"}


@router.get("/scan/status")
async def get_scan_status():
    """Get the current status of the scan operation."""
    manager = get_scan_manager()
    status = manager.get_status()
    # Convert enum to string for JSON serialization
    if 'status' in status and hasattr(status['status'], 'value'):
        status['status'] = status['status'].value
    return status


@router.post("/scan/{path:path}")
async def scan_folder(
    path: str,
    background_tasks: BackgroundTasks,
    scanner: LocalScannerService = Depends(get_local_scanner),
    ingestion: IngestionService = Depends(get_ingestion_service),
):
    """
    Scan a folder and index new/modified files.
    
    This will:
    1. Discover all supported files in the folder
    2. Check which files are new or modified
    3. Index new/modified files
    4. Skip unchanged files
    
    Returns immediately and runs scan in background.
    Use /folders/scan/status to check progress.
    """
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    
    async def _run_scan():
        try:
            await scanner.scan_folder(path, ingestion, is_background=True)
        except Exception as e:
            logger.error(f"Background scan failed: {e}")
            manager = get_scan_manager()
            manager.fail_scan(str(e))
    
    background_tasks.add_task(_run_scan)
    return {"message": "Scan started in background", "status_endpoint": "/api/folders/scan/status"}


@router.post("/scan-all")
async def scan_all_folders(
    background_tasks: BackgroundTasks,
    scanner: LocalScannerService = Depends(get_local_scanner),
    ingestion: IngestionService = Depends(get_ingestion_service),
):
    """
    Scan all enabled folder sources in the background.
    """
    manager = get_scan_manager()
    
    async def _run_scan_all():
        total_stats = {
            "discovered": 0,
            "new": 0,
            "modified": 0,
            "unchanged": 0,
            "indexed": 0,
            "errors": 0,
            "folders_scanned": 0,
        }
        
        # Calculate total files first for progress bar
        all_files = []
        for source in scanner.sources:
            if source.enabled:
                files = scanner.discover_files(source)
                all_files.extend(files)
        
        manager.start_scan(total_files=len(all_files))
        
        for source in scanner.sources:
            if source.enabled and not manager.should_stop:
                try:
                    # Pass is_background=False so it doesn't reset the manager
                    stats = await scanner.scan_folder(source.path, ingestion, is_background=False)
                    for key in ["discovered", "new", "modified", "unchanged", "indexed", "errors"]:
                        total_stats[key] += stats[key]
                    total_stats["folders_scanned"] += 1
                except Exception as e:
                    logger.error(f"Failed to scan {source.path}: {e}")
                    total_stats["errors"] += 1
        
        if not manager.should_stop:
            manager.complete_scan()
        else:
            manager.state.status = "stopped"
            
    background_tasks.add_task(_run_scan_all)
    
    return {"message": "Background scan started"}


@router.get("/suggestions")
async def get_folder_suggestions():
    """
    Get suggested folders to add based on the system.
    
    Returns common locations where users might have documents.
    """
    home = Path.home()
    
    suggestions = []
    
    # Standard folders
    standard = [
        ("Documents", home / "Documents"),
        ("Desktop", home / "Desktop"),
        ("Downloads", home / "Downloads"),
    ]
    
    for name, path in standard:
        if path.exists():
            suggestions.append({
                "name": name,
                "path": str(path),
                "display": f"~/{name}",
                "type": "standard",
            })
    
    # iCloud
    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if icloud.exists():
        suggestions.append({
            "name": "iCloud Drive",
            "path": str(icloud),
            "display": "iCloud Drive",
            "type": "cloud",
        })
    
    # Common cloud storage
    cloud_folders = [
        ("Dropbox", home / "Dropbox"),
        ("OneDrive", home / "OneDrive"),
        ("Google Drive", home / "Google Drive"),
    ]
    
    for name, path in cloud_folders:
        if path.exists():
            suggestions.append({
                "name": name,
                "path": str(path),
                "display": name,
                "type": "cloud",
            })
    
    # Obsidian vaults (common notes app)
    obsidian_config = home / ".obsidian"
    if obsidian_config.exists():
        # Try to find vaults
        try:
            config_file = home / ".obsidian.json" 
            # This is simplified - Obsidian stores vault locations differently
            pass
        except:
            pass
    
    # Check for common project folders
    project_folders = [
        ("Projects", home / "Projects"),
        ("Code", home / "Code"),
        ("Development", home / "Development"),
        ("Notes", home / "Notes"),
    ]
    
    for name, path in project_folders:
        if path.exists():
            suggestions.append({
                "name": name,
                "path": str(path),
                "display": f"~/{name}",
                "type": "projects",
            })
    
    return {"suggestions": suggestions}


@router.get("/preview/{path:path}")
async def preview_folder(
    path: str,
    scanner: LocalScannerService = Depends(get_local_scanner),
):
    """
    Preview what files would be scanned in a folder.
    
    Useful before enabling a large folder.
    """
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    
    from ..services.local_scanner import FolderSource
    
    # Create temporary source for preview
    source = FolderSource(path=path, enabled=True, recursive=True)
    
    try:
        files = scanner.discover_files(source)
        
        # Group by extension
        by_ext = {}
        total_size = 0
        
        for f in files:
            ext = f.suffix.lower()
            if ext not in by_ext:
                by_ext[ext] = {"count": 0, "size": 0, "samples": []}
            by_ext[ext]["count"] += 1
            try:
                size = f.stat().st_size
                by_ext[ext]["size"] += size
                total_size += size
            except:
                pass
            
            if len(by_ext[ext]["samples"]) < 3:
                by_ext[ext]["samples"].append(f.name)
        
        return {
            "path": path,
            "total_files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_extension": by_ext,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Live Search (On-Demand)
# ============================================================================

class LiveSearchRequest(BaseModel):
    """Request for live local file search."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=50, description="Max results")
    search_content: bool = Field(True, description="Search inside file contents")


@router.post("/live-search")
async def live_search_local_files(
    request: LiveSearchRequest,
    live_search: LiveSearchService = Depends(get_live_search_service),
):
    """
    Search local files on-demand without pre-indexing.
    
    This is memory-efficient - files are searched in real-time
    only when you make a query, instead of being pre-indexed.
    
    Great for:
    - One-time searches
    - Very large folders that would be expensive to index
    - Files that change frequently
    
    Searches:
    - File names (fast)
    - File contents for text files (slower but more comprehensive)
    
    Returns:
    - Relevant files with previews
    - Relevance scores
    - Match type (filename, content, or both)
    """
    try:
        results = await live_search.search(
            query=request.query,
            limit=request.limit,
            search_content=request.search_content,
        )
        return {
            "query": request.query,
            "results": results,
            "total": len(results),
            "mode": "live",
        }
    except Exception as e:
        logger.error(f"Live search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live-search/file/{path:path}")
async def get_live_file_content(
    path: str,
    live_search: LiveSearchService = Depends(get_live_search_service),
):
    """
    Get the full content of a local file.
    
    Used to view files found via live search.
    """
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    
    content = await live_search.get_file_content(path)
    
    if content is None:
        raise HTTPException(status_code=404, detail="File not found or unreadable")
    
    return {
        "path": path,
        "filename": Path(path).name,
        "content": content,
    }
