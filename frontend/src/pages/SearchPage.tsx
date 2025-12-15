import React, { useState } from 'react';
import { Search, Loader2, FileText, Mail, File } from 'lucide-react';
import client from '../api/client';
import { SearchResult } from '../types';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);
    try {
      const response = await client.post('/search/hybrid', {
        query: query,
        limit: 10,
        semantic_weight: 0.7
      });
      setResults(response.data.results);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const getIcon = (docType: string) => {
    if (docType === 'email' || docType === 'msg') return Mail;
    if (docType === 'pdf') return FileText;
    return File;
  };

  return (
    <div className="space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold text-gray-900">Knowledge Search</h1>
        <p className="text-gray-500">Search across your emails, documents, and notes</p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., 'What did Krish say about the project?'"
            className="w-full pl-12 pr-4 py-4 rounded-xl border border-gray-200 shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all"
          />
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
          </button>
        </div>
      </form>

      {/* Results */}
      <div className="max-w-3xl mx-auto space-y-4">
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
          </div>
        ) : results.length > 0 ? (
          results.map((result) => {
            const Icon = getIcon(result.doc_metadata?.doc_type || 'file');
            return (
              <div key={result.chunk_id} className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Icon className="w-4 h-4" />
                    <span className="font-medium text-gray-900">
                      {result.doc_metadata?.title || result.doc_metadata?.filename}
                    </span>
                    <span>•</span>
                    <span className="capitalize">{result.doc_metadata?.source || 'Local'}</span>
                  </div>
                  <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full font-medium">
                    {Math.round(result.score * 100)}% Match
                  </span>
                </div>
                <p className="text-gray-700 leading-relaxed text-sm">
                  {result.text}
                </p>
              </div>
            );
          })
        ) : searched ? (
          <div className="text-center py-12 text-gray-500">
            No results found. Try a different query.
          </div>
        ) : null}
      </div>
    </div>
  );
}

