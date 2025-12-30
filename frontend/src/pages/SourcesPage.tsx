import React, { useEffect, useState } from 'react';
import { 
  Folder, FolderPlus, RefreshCw, Trash2, Loader2, 
  Cloud, HardDrive, Check, X, AlertCircle, Eye,
  ChevronDown, ChevronRight, FileText, Image, Code,
  StopCircle
} from 'lucide-react';
import client from '../api/client';
import clsx from 'clsx';

interface FolderSource {
  path: string;
  display_name: string;
  enabled: boolean;
  recursive: boolean;
  exists: boolean;
  file_count: number;
  last_scan: string | null;
}

interface Suggestion {
  name: string;
  path: string;
  display: string;
  type: string;
}

interface PreviewData {
  path: string;
  total_files: number;
  total_size_mb: number;
  by_extension: Record<string, { count: number; size: number; samples: string[] }>;
}

interface ScanProgress {
  status: 'idle' | 'running' | 'stopping' | 'stopped' | 'completed' | 'failed';
  total_files: number;
  processed_files: number;
  current_file: string | null;
  progress_percent: number;
  files_indexed: number;
  errors: number;
  estimated_remaining_seconds: number | null;
  message: string | null;
}

export default function SourcesPage() {
  const [sources, setSources] = useState<FolderSource[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState<string | null>(null);
  const [scanningAll, setScanningAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Scan Progress
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [showScanModal, setShowScanModal] = useState(false);
  
  // Preview modal
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  
  // Add custom folder
  const [showAddFolder, setShowAddFolder] = useState(false);
  const [customPath, setCustomPath] = useState('');
  
  // Folder picker ref
  const folderInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadSources();
    loadSuggestions();
  }, []);

  // Polling for scan status
  useEffect(() => {
    let interval: any;

    if (scanningAll || showScanModal || scanning) {
      // Start polling immediately
      const pollStatus = async () => {
        try {
          const res = await client.get('/folders/scan/status');
          const progress = res.data;
          setScanProgress(progress);
          
          if (progress.status === 'completed' || progress.status === 'stopped' || progress.status === 'failed' || progress.status === 'idle') {
             // If we were scanning, refresh sources to show new counts
             if (scanningAll || scanning) {
               loadSources();
               if (scanningAll) setScanningAll(false);
               if (scanning) setScanning(null);
               setShowScanModal(false);
               if (progress.status === 'completed') {
                 setSuccess(`Scan completed: ${progress.files_indexed || 0} files indexed.`);
               } else if (progress.status === 'stopped') {
                 setError('Scan stopped by user.');
               } else if (progress.status === 'failed') {
                 setError(progress.message || 'Scan failed.');
               }
             }
          }
        } catch (err) {
          console.error("Failed to poll status", err);
        }
      };
      
      // Poll immediately, then every second
      pollStatus();
      interval = setInterval(pollStatus, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [scanningAll, showScanModal, scanning]);

  const loadSources = async () => {
    try {
      const res = await client.get('/folders/sources');
      setSources(res.data.sources);
      setStats(res.data.stats);
    } catch (err) {
      console.error(err);
      setError('Failed to load folder sources');
    } finally {
      setLoading(false);
    }
  };

  const loadSuggestions = async () => {
    try {
      const res = await client.get('/folders/suggestions');
      setSuggestions(res.data.suggestions);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleSource = async (path: string, enabled: boolean) => {
    try {
      await client.patch(`/folders/sources/${encodeURIComponent(path)}`, { enabled });
      setSources(prev => prev.map(s => 
        s.path === path ? { ...s, enabled } : s
      ));
    } catch (err) {
      console.error(err);
      setError('Failed to update folder');
    }
  };

  const scanFolder = async (path: string) => {
    setScanning(path);
    setShowScanModal(true);
    setError(null);
    setSuccess(null);
    
    try {
      await client.post(`/folders/scan/${encodeURIComponent(path)}`);
      // Scan runs in background, polling will handle updates
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Scan failed');
      setScanning(null);
      setShowScanModal(false);
    }
  };

  const scanAllFolders = async () => {
    const enabledCount = sources.filter(s => s.enabled).length;
    if (!confirm(
      `WARNING: Scanning ${enabledCount} enabled folder(s) will use API calls (costs money).\n\n` +
      `For large folders, this can be VERY expensive.\n\n` +
      `Consider using "Live Local" search instead (free, no indexing).\n\n` +
      `Continue anyway?`
    )) {
      return;
    }
    
    setScanningAll(true);
    setShowScanModal(true);
    setError(null);
    setSuccess(null);
    
    try {
      await client.post('/folders/scan-all');
      // Success is handled by polling
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Scan failed');
      setScanningAll(false);
      setShowScanModal(false);
    }
  };

  const stopScan = async () => {
    try {
      await client.post('/folders/scan/stop');
      // Status update will be handled by polling
    } catch (err) {
      console.error('Failed to stop scan:', err);
    }
  };

  const addFolder = async (path: string) => {
    try {
      await client.post('/folders/sources', { path, recursive: true });
      setSuccess(`Added folder: ${path}`);
      setShowAddFolder(false);
      setCustomPath('');
      loadSources();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to add folder');
    }
  };

  // Handle native folder picker
  const handleFolderSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    // Get the common path from the selected files
    // The webkitRelativePath gives us paths like "FolderName/subfolder/file.txt"
    const firstFile = files[0];
    const relativePath = (firstFile as any).webkitRelativePath;
    
    if (relativePath) {
      // Extract the folder name (first part of the path)
      const folderName = relativePath.split('/')[0];
      
      // Browser security prevents getting full system paths
      // Show modal with suggested path that user can edit
      setCustomPath(`~/Documents/${folderName}`);
      setShowAddFolder(true);
      setSuccess(`Selected folder: ${folderName}. Please verify and correct the path below if needed.`);
    } else {
      // No relative path - just open the modal for manual entry
      setShowAddFolder(true);
      setSuccess('Please enter the full path to the folder you want to add.');
    }
    
    // Reset the input
    if (folderInputRef.current) {
      folderInputRef.current.value = '';
    }
  };

  const removeFolder = async (path: string) => {
    if (!confirm('Remove this folder from sources?')) return;
    
    try {
      await client.delete(`/folders/sources/${encodeURIComponent(path)}`);
      loadSources();
    } catch (err) {
      console.error(err);
      setError('Failed to remove folder');
    }
  };

  const previewFolder = async (path: string) => {
    setPreviewPath(path);
    setLoadingPreview(true);
    
    try {
      const res = await client.get(`/folders/preview/${encodeURIComponent(path)}`);
      setPreviewData(res.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to preview folder');
      setPreviewPath(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  const getTypeIcon = (type: string) => {
    if (type === 'cloud') return Cloud;
    if (type === 'projects') return Code;
    return Folder;
  };

  const getExtIcon = (ext: string) => {
    if (['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext)) return Image;
    if (['.py', '.js', '.ts', '.tsx', '.jsx'].includes(ext)) return Code;
    return FileText;
  };

  // Filter out suggestions that are already added
  const availableSuggestions = suggestions.filter(
    s => !sources.some(src => src.path === s.path)
  );

  const formatTime = (seconds: number | null) => {
    if (seconds === null) return 'Calculating...';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.ceil(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Local Sources</h1>
          <p className="text-gray-500">Index your local files and cloud folders</p>
        </div>
        
        <div className="flex gap-3">
          <button
            onClick={scanAllFolders}
            disabled={scanningAll || sources.filter(s => s.enabled).length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {scanningAll ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Scan All
          </button>
        </div>
      </div>

      {/* API Cost Warning */}
      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-800">
        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="font-semibold text-sm mb-1">API Costs Warning</p>
          <p className="text-xs">
            <strong>Scanning/Indexing uses API calls</strong> (OpenAI embeddings) which cost money. 
            For large folders, this can be expensive. 
            <strong className="block mt-1">Tip: Use "Live Local" search mode instead</strong> - it searches files on-demand without indexing (free, no API calls)!
          </p>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      
      {success && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl text-green-800">
          <Check className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{success}</p>
          <button onClick={() => setSuccess(null)} className="ml-auto">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">{stats.total_files}</div>
            <div className="text-sm text-gray-500">Files Indexed</div>
          </div>
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">{stats.total_size_mb} MB</div>
            <div className="text-sm text-gray-500">Total Size</div>
          </div>
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <div className="text-3xl font-bold text-gray-900">
              {sources.filter(s => s.enabled).length}
            </div>
            <div className="text-sm text-gray-500">Active Sources</div>
          </div>
        </div>
      )}

      {/* Hidden folder input for native picker */}
      <input
        ref={folderInputRef}
        type="file"
        /* @ts-ignore - webkitdirectory is a non-standard attribute */
        webkitdirectory=""
        directory=""
        multiple
        className="hidden"
        onChange={handleFolderSelect}
      />

      {/* Configured Sources */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Configured Folders</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => folderInputRef.current?.click()}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200"
              title="Browse and select a folder"
            >
              <Folder className="w-4 h-4" />
              Browse
            </button>
            <button
              onClick={() => setShowAddFolder(true)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100"
            >
              <FolderPlus className="w-4 h-4" />
              Add Path
            </button>
          </div>
        </div>
        
        {loading ? (
          <div className="p-8 flex justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : sources.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No folders configured. Add folders below to start indexing.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {sources.map(source => (
              <div key={source.path} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      'p-2 rounded-lg',
                      source.enabled ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-400'
                    )}>
                      <Folder className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{source.display_name}</div>
                      <div className="text-xs text-gray-500">
                        {source.file_count} files indexed
                        {source.last_scan && ` • Last scan: ${new Date(source.last_scan).toLocaleDateString()}`}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {/* Preview */}
                    <button
                      onClick={() => previewFolder(source.path)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
                      title="Preview files"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    
                    {/* Scan */}
                    <button
                      onClick={() => {
                        if (!confirm(`WARNING: Scanning "${source.display_name}" will use API calls (costs money).\n\nFor large folders, this can be expensive.\n\nConsider using "Live Local" search instead (free, no indexing).\n\nContinue anyway?`)) {
                          return;
                        }
                        scanFolder(source.path);
                      }}
                      disabled={!source.enabled || scanning === source.path || scanningAll}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                      title="Scan folder (uses API calls - costs money)"
                    >
                      <RefreshCw className={clsx('w-4 h-4', (scanning === source.path || showScanModal) && 'animate-spin')} />
                    </button>
                    
                    {/* Toggle */}
                    <button
                      onClick={() => toggleSource(source.path, !source.enabled)}
                      className={clsx(
                        'w-12 h-6 rounded-full transition-colors relative',
                        source.enabled ? 'bg-blue-600' : 'bg-gray-300'
                      )}
                    >
                      <div className={clsx(
                        'w-5 h-5 rounded-full bg-white shadow absolute top-0.5 transition-transform',
                        source.enabled ? 'translate-x-6' : 'translate-x-0.5'
                      )} />
                    </button>
                    
                    {/* Remove */}
                    <button
                      onClick={() => removeFolder(source.path)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                      title="Remove folder"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Suggestions */}
      {availableSuggestions.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h2 className="font-semibold text-gray-900">Suggested Folders</h2>
            <p className="text-sm text-gray-500">Common locations where your documents might be</p>
          </div>
          
          <div className="divide-y divide-gray-200">
            {availableSuggestions.map(suggestion => {
              const Icon = getTypeIcon(suggestion.type);
              return (
                <div key={suggestion.path} className="p-4 flex items-center justify-between hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      'p-2 rounded-lg',
                      suggestion.type === 'cloud' ? 'bg-purple-50 text-purple-600' : 'bg-gray-100 text-gray-600'
                    )}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{suggestion.name}</div>
                      <div className="text-xs text-gray-500">{suggestion.display}</div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => previewFolder(suggestion.path)}
                      className="px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200"
                    >
                      Preview
                    </button>
                    <button
                      onClick={() => addFolder(suggestion.path)}
                      className="px-3 py-1.5 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                    >
                      Add
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Add Custom Folder Modal */}
      {showAddFolder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Add Custom Folder</h3>
              <button onClick={() => setShowAddFolder(false)}>
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Folder Path
                </label>
                <input
                  type="text"
                  value={customPath}
                  onChange={(e) => setCustomPath(e.target.value)}
                  placeholder="~/Documents/MyFolder or /absolute/path"
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Use ~ for home directory. Example: ~/Documents/Projects
                </p>
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowAddFolder(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={() => addFolder(customPath)}
                  disabled={!customPath.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  Add Folder
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewPath && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">Folder Preview</h3>
                <p className="text-sm text-gray-500">{previewPath}</p>
              </div>
              <button onClick={() => { setPreviewPath(null); setPreviewData(null); }}>
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4">
              {loadingPreview ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              ) : previewData ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">{previewData.total_files}</div>
                      <div className="text-sm text-gray-500">Scannable Files</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">{previewData.total_size_mb} MB</div>
                      <div className="text-sm text-gray-500">Total Size</div>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2">Files by Type</h4>
                    <div className="space-y-2">
                      {Object.entries(previewData.by_extension)
                        .sort(([,a], [,b]) => b.count - a.count)
                        .map(([ext, data]) => {
                          const Icon = getExtIcon(ext);
                          return (
                            <div key={ext} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                              <div className="flex items-center gap-2">
                                <Icon className="w-4 h-4 text-gray-400" />
                                <span className="font-mono text-sm">{ext}</span>
                              </div>
                              <div className="text-sm text-gray-500">
                                {data.count} files ({(data.size / (1024 * 1024)).toFixed(2)} MB)
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  No preview data available
                </div>
              )}
            </div>
            
            {previewData && (
              <div className="p-4 border-t border-gray-200 flex justify-end gap-3">
                <button
                  onClick={() => { setPreviewPath(null); setPreviewData(null); }}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Close
                </button>
                {!sources.some(s => s.path === previewPath) && (
                  <button
                    onClick={() => { addFolder(previewPath!); setPreviewPath(null); setPreviewData(null); }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Add & Enable
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Scan Progress Modal */}
      {showScanModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[60] p-6">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <RefreshCw className={clsx("w-5 h-5", scanProgress?.status === 'running' && "animate-spin text-blue-600")} />
              Scanning Documents
            </h3>
            
            {scanProgress ? (
              <div className="space-y-4">
                {/* Progress Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Progress ({Math.round(scanProgress.progress_percent || 0)}%)</span>
                    <span>{scanProgress.processed_files || 0} / {scanProgress.total_files || 0} files</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-blue-600 transition-all duration-300 ease-out"
                      style={{ width: `${scanProgress.progress_percent || 0}%` }}
                    />
                  </div>
                </div>

                {/* Current Status */}
                <div className="bg-gray-50 p-4 rounded-xl space-y-3">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">Current File:</span>
                    <span className="font-mono text-gray-800 truncate max-w-[200px]" title={scanProgress.current_file || ''}>
                      {scanProgress.current_file || 'Preparing...'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">Indexed:</span>
                    <span className="text-green-600 font-medium">{scanProgress.files_indexed || 0} files</span>
                  </div>
                  {scanProgress.estimated_remaining_seconds !== null && scanProgress.estimated_remaining_seconds !== undefined && (
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-gray-500">Est. Remaining:</span>
                      <span className="text-gray-800">{formatTime(scanProgress.estimated_remaining_seconds)}</span>
                    </div>
                  )}
                </div>

                {/* Controls */}
                <div className="flex justify-end pt-2">
                  {(scanProgress.status === 'completed' || scanProgress.status === 'stopped' || scanProgress.status === 'failed' || scanProgress.status === 'idle') ? (
                    <button
                      onClick={() => { setShowScanModal(false); setScanProgress(null); setScanning(null); }}
                      className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                    >
                      Close
                    </button>
                  ) : (
                    <button
                      onClick={stopScan}
                      className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      <StopCircle className="w-4 h-4" />
                      Stop Scanning
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-4" />
                <p className="text-gray-500">Initializing scan...</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
