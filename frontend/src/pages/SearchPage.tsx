import React, { useState, useEffect } from 'react';
import { 
  Search, Loader2, FileText, Mail, File, Clock, X, Trash2, 
  ChevronLeft, ChevronRight, Eye, Download, Folder, Database,
  Zap
} from 'lucide-react';
import client, { API_BASE_URL } from '../api/client';
import type { SearchResult } from '../types/index.js';
import clsx from 'clsx';

interface SearchHistoryItem {
  id: string;
  query: string;
  timestamp: string;
  resultCount: number;
  results: SearchResult[];
}

interface DocumentPreview {
  document_id: string;
  filename: string;
  title: string;
  content: string;
}

interface LiveSearchResult {
  path: string;
  filename: string;
  display_path: string;
  relevance_score: number;
  match_type: string;
  preview: string;
  file_size: number;
  extension: string;
  source: string;
}

const HISTORY_KEY = 'pk_search_history';
const MAX_HISTORY = 50;

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [liveResults, setLiveResults] = useState<LiveSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  
  // Search mode: 'indexed' (vector DB) or 'live' (on-demand local files)
  // Default to 'live' to save money (no API calls)
  const [searchMode, setSearchMode] = useState<'indexed' | 'live'>('live');
  
  // History state
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  
  // Document preview
  const [previewDoc, setPreviewDoc] = useState<DocumentPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Load history from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      if (stored) {
        setHistory(JSON.parse(stored));
      }
    } catch (e) {
      console.error('Failed to load search history:', e);
    }
  }, []);

  // Save history to localStorage
  const saveHistory = (newHistory: SearchHistoryItem[]) => {
    setHistory(newHistory);
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory.slice(0, MAX_HISTORY)));
    } catch (e) {
      console.error('Failed to save search history:', e);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);
    setSelectedHistoryId(null);
    setResults([]);
    setLiveResults([]);
    
    try {
      if (searchMode === 'live') {
        // Live search - on-demand local files
        const response = await client.post('/folders/live-search', {
          query: query,
          limit: 15,
          search_content: true
        });
        setLiveResults(response.data.results);
      } else {
        // Indexed search - vector database
        const response = await client.post('/search/hybrid', {
          query: query,
          limit: 10,
          semantic_weight: 0.7
        });
        const searchResults = response.data.results;
        setResults(searchResults);
        
        // Add to history (only for indexed search)
        const historyItem: SearchHistoryItem = {
          id: `search_${Date.now()}`,
          query: query.trim(),
          timestamp: new Date().toISOString(),
          resultCount: searchResults.length,
          results: searchResults,
        };
        
        // Remove duplicate queries and add new one at top
        const filteredHistory = history.filter(h => h.query.toLowerCase() !== query.trim().toLowerCase());
        saveHistory([historyItem, ...filteredHistory]);
        setSelectedHistoryId(historyItem.id);
      }
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadHistoryItem = (item: SearchHistoryItem) => {
    setQuery(item.query);
    setResults(item.results);
    setSearched(true);
    setSelectedHistoryId(item.id);
  };

  const deleteHistoryItem = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newHistory = history.filter(h => h.id !== id);
    saveHistory(newHistory);
    
    if (selectedHistoryId === id) {
      setSelectedHistoryId(null);
      setResults([]);
      setSearched(false);
      setQuery('');
    }
  };

  const clearAllHistory = () => {
    if (!confirm('Clear all search history?')) return;
    saveHistory([]);
    setSelectedHistoryId(null);
    setResults([]);
    setSearched(false);
    setQuery('');
  };

  const getIcon = (docType: string) => {
    if (docType === 'email' || docType === 'msg') return Mail;
    if (docType === 'pdf') return FileText;
    return File;
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return 'Yesterday';
    } else if (days < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  };

  const viewDocument = async (documentId: string, filename: string) => {
    setLoadingPreview(true);
    try {
      const res = await client.get(`/documents/${documentId}/view`);
      setPreviewDoc({
        document_id: documentId,
        filename: filename,
        title: res.data.title || filename,
        content: res.data.content,
      });
    } catch (err) {
      console.error('Failed to load document:', err);
      alert('Failed to load document preview');
    } finally {
      setLoadingPreview(false);
    }
  };

  const downloadDocument = (documentId: string) => {
    window.open(`${API_BASE_URL}/documents/${documentId}/download`, '_blank');
  };

  // View live file content (for live search results)
  const viewLiveFile = async (filePath: string, filename: string) => {
    setLoadingPreview(true);
    try {
      const res = await client.get(`/folders/live-search/file/${encodeURIComponent(filePath)}`);
      setPreviewDoc({
        document_id: filePath,
        filename: filename,
        title: filename,
        content: res.data.content,
      });
    } catch (err) {
      console.error('Failed to load file:', err);
      alert('Failed to load file preview');
    } finally {
      setLoadingPreview(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar - Search History */}
      <div className={clsx(
        'flex flex-col bg-white border border-gray-200 rounded-xl transition-all duration-300',
        historyOpen ? 'w-72' : 'w-12'
      )}>
        {/* Sidebar Header */}
        <div className="p-3 border-b border-gray-200 flex items-center justify-between">
          {historyOpen && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="font-semibold text-gray-700 text-sm">History</span>
            </div>
          )}
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          >
            {historyOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {historyOpen && (
          <>
            {/* Clear All Button */}
            {history.length > 0 && (
              <div className="p-3 border-b border-gray-100">
                <button
                  onClick={clearAllHistory}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors text-xs font-medium"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear All History
                </button>
              </div>
            )}

            {/* History List */}
            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
              {history.length === 0 ? (
                <p className="text-center text-gray-400 text-xs py-8">
                  No search history yet
                </p>
              ) : (
                history.map(item => (
                  <div
                    key={item.id}
                    onClick={() => loadHistoryItem(item)}
                    className={clsx(
                      'group p-3 rounded-lg cursor-pointer transition-colors',
                      item.id === selectedHistoryId
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50 border border-transparent'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {item.query}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {item.resultCount} results • {formatDate(item.timestamp)}
                        </p>
                      </div>
                      <button
                        onClick={(e) => deleteHistoryItem(item.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition-all"
                      >
                        <X className="w-3.5 h-3.5 text-red-500" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Main Search Area */}
      <div className="flex-1 flex flex-col">
        <div className="text-center space-y-3 mb-8">
          <h1 className="text-4xl font-bold gradient-text">Knowledge Search</h1>
          <p className="text-gray-600">Search across your emails, documents, and notes</p>
        </div>

        <div className="flex justify-center gap-3 mb-4">
          <button
            onClick={() => setSearchMode('indexed')}
            className={clsx(
              'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 shadow-sm',
              searchMode === 'indexed'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                : 'bg-white/80 text-gray-600 hover:bg-white hover:shadow-md'
            )}
          >
            <Database className="w-4 h-4" />
            Indexed
          </button>
          <button
            onClick={() => setSearchMode('live')}
            className={clsx(
              'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 shadow-sm',
              searchMode === 'live'
                ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white shadow-lg shadow-emerald-500/30'
                : 'bg-white/80 text-gray-600 hover:bg-white hover:shadow-md'
            )}
          >
            <Zap className="w-4 h-4" />
            Live Local
          </button>
        </div>
        
        {/* Mode description */}
        <p className="text-center text-xs mb-4">
          {searchMode === 'indexed' ? (
            <span className="text-amber-600">
              ⚠️ Uses API calls (costs money) - Search pre-indexed documents
            </span>
          ) : (
            <span className="text-emerald-600">
              ✅ FREE - Search local files on-demand (no API calls, no indexing)
            </span>
          )}
        </p>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="max-w-2xl mx-auto w-full mb-8">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={searchMode === 'live' 
                ? "Search your local files..." 
                : "e.g., 'What did Krish say about the project?'"}
              className="w-full pl-12 pr-24 py-4 rounded-2xl border border-white/40 bg-white/80 backdrop-blur-sm shadow-lg focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className={clsx(
                "absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
                searchMode === 'live' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-blue-600 hover:bg-blue-700'
              )}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
            </button>
          </div>
        </form>

        {/* Results */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto space-y-4 pb-4">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <Loader2 className={clsx(
                  "w-8 h-8 animate-spin",
                  searchMode === 'live' ? 'text-emerald-600' : 'text-blue-600'
                )} />
                {searchMode === 'live' && (
                  <p className="text-sm text-gray-500">Searching local files...</p>
                )}
              </div>
            ) : searchMode === 'live' && liveResults.length > 0 ? (
              // Live search results
              liveResults.map((result, idx) => (
                <div 
                  key={`${result.path}-${idx}`} 
                  className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Folder className="w-4 h-4 text-emerald-600" />
                      <span className="font-medium text-gray-900">
                        {result.filename}
                      </span>
                      <span>•</span>
                      <span className="text-xs">{result.display_path}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        "text-xs px-2 py-1 rounded-full font-medium",
                        result.match_type === 'both' 
                          ? 'bg-emerald-50 text-emerald-700'
                          : result.match_type === 'content'
                          ? 'bg-blue-50 text-blue-700'
                          : 'bg-gray-100 text-gray-700'
                      )}>
                        {result.match_type === 'both' ? '📄+🔍' : result.match_type === 'content' ? '🔍 Content' : '📄 Filename'}
                      </span>
                      <span className="text-xs text-gray-400">{formatFileSize(result.file_size)}</span>
                      <button
                        onClick={() => viewLiveFile(result.path, result.filename)}
                        className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                        title="View file"
                      >
                        <Eye className="w-4 h-4 text-gray-500" />
                      </button>
                    </div>
                  </div>
                  <p className="text-gray-700 leading-relaxed text-sm">
                    {result.preview}
                  </p>
                </div>
              ))
            ) : searchMode === 'indexed' && results.length > 0 ? (
              // Indexed search results
              results.map((result) => {
                const docType = result.metadata?.doc_type || result.filename?.split('.').pop() || 'file';
                const Icon = getIcon(docType);
                return (
                  <div 
                    key={result.chunk_id} 
                    className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Icon className="w-4 h-4" />
                        <span className="font-medium text-gray-900">
                          {result.metadata?.title || result.filename}
                        </span>
                        <span>•</span>
                        <span className="capitalize">{result.metadata?.source || 'Local'}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full font-medium">
                          {Math.round(result.score * 100)}% Match
                        </span>
                        <button
                          onClick={() => viewDocument(result.document_id, result.filename)}
                          className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                          title="View document"
                        >
                          <Eye className="w-4 h-4 text-gray-500" />
                        </button>
                        <button
                          onClick={() => downloadDocument(result.document_id)}
                          className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                          title="Download document"
                        >
                          <Download className="w-4 h-4 text-gray-500" />
                        </button>
                      </div>
                    </div>
                    <p className="text-gray-700 leading-relaxed text-sm">
                      {result.highlighted_content || result.content}
                    </p>
                  </div>
                );
              })
            ) : searched ? (
              <div className="text-center py-12 text-gray-500">
                {searchMode === 'live' 
                  ? 'No local files found. Make sure you have enabled folders in Local Sources.' 
                  : 'No results found. Try a different query.'}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Document Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">{previewDoc.title}</h3>
                <p className="text-sm text-gray-500">{previewDoc.filename}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadDocument(previewDoc.document_id)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Download"
                >
                  <Download className="w-5 h-5 text-gray-600" />
                </button>
                <button
                  onClick={() => setPreviewDoc(null)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                {previewDoc.content || 'No content available'}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Loading overlay for preview */}
      {loadingPreview && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <Loader2 className="w-8 h-8 animate-spin text-white" />
        </div>
      )}
    </div>
  );
}
