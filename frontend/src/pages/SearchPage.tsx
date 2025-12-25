import React, { useState, useEffect } from 'react';
import { 
  Search, Loader2, FileText, Mail, File, Clock, X, Trash2, 
  ChevronLeft, ChevronRight, Eye, Download, Folder, Database,
  Zap, AlertCircle, Image as ImageIcon
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
  is_image?: boolean;
  original_file_url?: string;
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
  const [error, setError] = useState<string | null>(null);
  const [searchMode, setSearchMode] = useState<'indexed' | 'live'>('live');
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<DocumentPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      if (stored) setHistory(JSON.parse(stored));
    } catch (e) {
      console.error('Failed to load search history:', e);
    }
  }, []);

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
    setError(null);
    setSelectedHistoryId(null);
    setResults([]);
    setLiveResults([]);
    
    try {
      if (searchMode === 'live') {
        const response = await client.post('/folders/live-search', {
          query: query,
          limit: 15,
          search_content: true
        });
        setLiveResults(response.data.results);
      } else {
        const response = await client.post('/search/hybrid', {
          query: query,
          limit: 10,
          semantic_weight: 0.7
        });
        const searchResults = response.data.results;
        setResults(searchResults);
        
        const historyItem: SearchHistoryItem = {
          id: `search_${Date.now()}`,
          query: query.trim(),
          timestamp: new Date().toISOString(),
          resultCount: searchResults.length,
          results: searchResults,
        };
        
        const filteredHistory = history.filter(h => h.query.toLowerCase() !== query.trim().toLowerCase());
        saveHistory([historyItem, ...filteredHistory]);
        setSelectedHistoryId(historyItem.id);
      }
    } catch (error: any) {
      console.error('Search failed:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Search failed';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const loadHistoryItem = (item: SearchHistoryItem) => {
    setQuery(item.query);
    setResults(item.results);
    setSearched(true);
    setSelectedHistoryId(item.id);
    setSearchMode('indexed');
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
    if (days === 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (days === 1) return 'Yesterday';
    if (days < 7) return date.toLocaleDateString([], { weekday: 'short' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const viewDocument = async (documentId: string, filename: string) => {
    setLoadingPreview(true);
    try {
      const res = await client.get(`/documents/${documentId}/view`);
      setPreviewDoc({
        document_id: documentId,
        filename,
        title: res.data.title || filename,
        content: res.data.content,
        is_image: res.data.is_image,
        original_file_url: res.data.original_file_url,
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

  const viewLiveFile = async (filePath: string, filename: string) => {
    setLoadingPreview(true);
    try {
      const res = await client.get(`/folders/live-search/file/${encodeURIComponent(filePath)}`);
      setPreviewDoc({
        document_id: filePath,
        filename,
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
    <div className="flex h-[calc(100vh-6rem)] gap-4">
      {/* Sidebar */}
      <div className={clsx(
        'flex flex-col bg-white/90 backdrop-blur-sm border border-gray-200/50 rounded-2xl shadow-lg transition-all duration-300',
        historyOpen ? 'w-80' : 'w-14'
      )}>
        <div className="p-3 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white rounded-t-2xl">
          {historyOpen && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="font-semibold text-gray-800 text-sm">Search History</span>
            </div>
          )}
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="p-2 hover:bg-gray-100 rounded-xl transition-colors"
          >
            {historyOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {historyOpen && (
          <>
            {history.length > 0 && (
              <div className="p-3 border-b border-gray-100">
                <button
                  onClick={clearAllHistory}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-red-600 hover:bg-red-50 rounded-xl transition-colors text-xs font-medium"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear All
                </button>
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5">
              {history.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <Search className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                  <p className="text-gray-400 text-sm">No search history</p>
                </div>
              ) : (
                history.map(item => (
                  <div
                    key={item.id}
                    onClick={() => loadHistoryItem(item)}
                    className={clsx(
                      'group p-3 rounded-xl cursor-pointer transition-all',
                      item.id === selectedHistoryId
                        ? 'bg-blue-50 border-2 border-blue-200'
                        : 'hover:bg-gray-50 border-2 border-transparent'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{item.query}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {item.resultCount} results • {formatDate(item.timestamp)}
                        </p>
                      </div>
                      <button
                        onClick={(e) => deleteHistoryItem(item.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 rounded-lg transition-all"
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

      {/* Main Search */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-2">
            Knowledge Search
          </h1>
          <p className="text-gray-500 text-sm">Search across your emails, documents, and notes</p>
        </div>

        {/* Mode Toggle */}
        <div className="flex justify-center gap-2 mb-4">
          <button
            onClick={() => setSearchMode('indexed')}
            className={clsx(
              'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
              searchMode === 'indexed'
                ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
            )}
          >
            <Database className="w-4 h-4" />
            Indexed
          </button>
          <button
            onClick={() => setSearchMode('live')}
            className={clsx(
              'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
              searchMode === 'live'
                ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-lg'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
            )}
          >
            <Zap className="w-4 h-4" />
            Live Local
          </button>
        </div>
        
        <p className="text-center text-xs mb-5 px-4">
          {searchMode === 'indexed' ? (
            <span className="text-amber-600 bg-amber-50 px-3 py-1 rounded-full">
              ⚠️ Uses API calls • Searches pre-indexed documents
            </span>
          ) : (
            <span className="text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
              ✅ FREE • Searches local files on-demand
            </span>
          )}
        </p>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="max-w-2xl mx-auto w-full mb-6 px-4">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={searchMode === 'live' ? "Search your local files..." : "Ask anything about your documents..."}
              className="w-full pl-12 pr-24 py-4 rounded-2xl border-2 border-gray-200 bg-white shadow-sm focus:border-blue-400 focus:ring-4 focus:ring-blue-100 outline-none transition-all text-sm"
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className={clsx(
                "absolute right-2.5 top-1/2 -translate-y-1/2 px-5 py-2 text-white rounded-xl text-sm font-medium disabled:opacity-40 transition-all shadow-md",
                searchMode === 'live' 
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700' 
                  : 'bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700'
              )}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
            </button>
          </div>
        </form>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-4">
          <div className="max-w-2xl mx-auto space-y-3 pb-4">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-medium text-red-900 mb-1">Search Error</h3>
                    <p className="text-sm text-red-700">{error}</p>
                    {error.includes('quota') && (
                      <p className="text-xs text-red-600 mt-2">
                        💡 Switch to "Live Local" mode or change to local embeddings in Settings.
                      </p>
                    )}
                  </div>
                  <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
            
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Loader2 className={clsx(
                  "w-10 h-10 animate-spin",
                  searchMode === 'live' ? 'text-emerald-600' : 'text-blue-600'
                )} />
                <p className="text-sm text-gray-500">
                  {searchMode === 'live' ? 'Scanning local files...' : 'Searching knowledge base...'}
                </p>
              </div>
            ) : searchMode === 'live' && liveResults.length > 0 ? (
              liveResults.map((result, idx) => (
                <div 
                  key={`${result.path}-${idx}`} 
                  className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md hover:border-emerald-200 transition-all cursor-pointer group"
                  onClick={() => viewLiveFile(result.path, result.filename)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
                        <Folder className="w-5 h-5 text-emerald-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">{result.filename}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{result.display_path}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        "text-xs px-2.5 py-1 rounded-full font-medium",
                        result.match_type === 'both' ? 'bg-emerald-100 text-emerald-700' :
                        result.match_type === 'content' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                      )}>
                        {result.match_type === 'both' ? 'Name + Content' : result.match_type === 'content' ? 'Content' : 'Filename'}
                      </span>
                      <span className="text-xs text-gray-400">{formatFileSize(result.file_size)}</span>
                    </div>
                  </div>
                  <p className="text-gray-600 text-sm leading-relaxed line-clamp-2">
                    {result.preview}
                  </p>
                </div>
              ))
            ) : searchMode === 'indexed' && results.length > 0 ? (
              results.map((result) => {
                const docType = result.metadata?.doc_type || result.filename?.split('.').pop() || 'file';
                const Icon = getIcon(docType);
                return (
                  <div 
                    key={result.chunk_id} 
                    className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md hover:border-blue-200 transition-all cursor-pointer group"
                    onClick={() => viewDocument(result.document_id, result.filename)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                          <Icon className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900 text-sm">
                            {result.metadata?.title || result.filename}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5 capitalize">
                            {result.metadata?.source || 'Local'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs bg-blue-100 text-blue-700 px-2.5 py-1 rounded-full font-medium">
                          {Math.round(result.score * 100)}% Match
                        </span>
                        <button
                          onClick={(e) => { e.stopPropagation(); downloadDocument(result.document_id); }}
                          className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                          title="Download"
                        >
                          <Download className="w-4 h-4 text-gray-500" />
                        </button>
                      </div>
                    </div>
                    <p className="text-gray-600 text-sm leading-relaxed line-clamp-3">
                      {result.highlighted_content || result.content}
                    </p>
                  </div>
                );
              })
            ) : searched ? (
              <div className="text-center py-16">
                <Search className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500 text-sm">
                  {searchMode === 'live' 
                    ? 'No local files found. Enable folders in Local Sources first.' 
                    : 'No indexed documents found. Try a different query.'}
                </p>
              </div>
            ) : (
              <div className="text-center py-16">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center mx-auto mb-4">
                  <Search className="w-8 h-8 text-blue-500" />
                </div>
                <p className="text-gray-500 text-sm">Enter a query to search your knowledge base</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden">
            <div className="p-5 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
              <div className="min-w-0">
                <h3 className="font-semibold text-gray-900 truncate">{previewDoc.title}</h3>
                <p className="text-sm text-gray-500 flex items-center gap-1.5 mt-0.5">
                  {previewDoc.is_image ? <ImageIcon className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
                  {previewDoc.filename}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {!previewDoc.document_id.startsWith('/') && (
                  <button
                    onClick={() => downloadDocument(previewDoc.document_id)}
                    className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors"
                    title="Download"
                  >
                    <Download className="w-5 h-5 text-gray-600" />
                  </button>
                )}
                <button
                  onClick={() => setPreviewDoc(null)}
                  className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {previewDoc.is_image && previewDoc.original_file_url ? (
                <div className="flex items-center justify-center">
                  <img 
                    src={`${API_BASE_URL}${previewDoc.original_file_url}`}
                    alt={previewDoc.filename}
                    className="max-w-full max-h-[60vh] rounded-xl shadow-lg"
                  />
                </div>
              ) : (
                <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono bg-gray-50 p-4 rounded-xl">
                  {previewDoc.content || 'No content available'}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}

      {loadingPreview && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 shadow-xl">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        </div>
      )}
    </div>
  );
}
