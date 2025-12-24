import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Loader2, Bot, User, BookOpen, Plus, MessageSquare, 
  Trash2, Download, Eye, X, ChevronLeft, ChevronRight 
} from 'lucide-react';
import client, { API_BASE_URL } from '../api/client';
import type { SourceCitation } from '../types/index.js';
import clsx from 'clsx';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceCitation[];
}

interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

interface DocumentPreview {
  document_id: string;
  filename: string;
  title: string;
  content: string;
}

export default function ChatPage() {
  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  
  // History state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  
  // Document preview state
  const [previewDoc, setPreviewDoc] = useState<DocumentPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  
  const scrollRef = useRef<HTMLDivElement>(null);

  // Load conversation history on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    setLoadingHistory(true);
    try {
      const res = await client.get('/chat/conversations');
      setConversations(res.data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadConversation = async (convId: string) => {
    try {
      const res = await client.get(`/chat/conversations/${convId}`);
      setConversationId(convId);
      setMessages(res.data.messages.map((m: any) => ({
        role: m.role,
        content: m.content,
        sources: m.sources,
      })));
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  };

  const startNewChat = async () => {
    try {
      const res = await client.post('/chat/conversations/new');
      setConversationId(res.data.id);
      setMessages([]);
      loadConversations(); // Refresh list
    } catch (err) {
      console.error('Failed to create conversation:', err);
      // Fallback to local-only
      setConversationId(`local_${Date.now()}`);
      setMessages([]);
    }
  };

  const deleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    
    try {
      await client.delete(`/chat/conversations/${convId}`);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (conversationId === convId) {
        setConversationId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const saveMessage = async (role: 'user' | 'assistant', content: string, sources?: any[]) => {
    if (!conversationId) return;
    
    try {
      await client.post(`/chat/conversations/${conversationId}/message`, {
        conversation_id: conversationId,
        role,
        content,
        sources,
      });
    } catch (err) {
      console.error('Failed to save message:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    
    // Create conversation if needed
    if (!conversationId) {
      try {
        const res = await client.post('/chat/conversations/new');
        setConversationId(res.data.id);
      } catch {
        setConversationId(`local_${Date.now()}`);
      }
    }

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    saveMessage('user', userMsg);
    setLoading(true);

    // Create placeholder for assistant
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, stream: true })
      });

      if (!response.ok) throw new Error(response.statusText);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';
      let sources: any[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            
            if (data.type === 'chunk' && data.content) {
              fullContent += data.content;
              setMessages(prev => {
                const newMsgs = [...prev];
                newMsgs[newMsgs.length - 1].content = fullContent;
                return newMsgs;
              });
            }
            
            if (data.type === 'sources' && data.data) {
              sources = data.data.map((s: any) => ({
                document_id: s.document_id,
                filename: s.filename,
                chunk_id: s.chunk_id,
                content_preview: s.preview,
                relevance_score: s.score
              }));
              setMessages(prev => {
                const newMsgs = [...prev];
                newMsgs[newMsgs.length - 1].sources = sources;
                return newMsgs;
              });
            }
            
            if (data.type === 'error') {
              fullContent = `Error: ${data.content}`;
              setMessages(prev => {
                const newMsgs = [...prev];
                newMsgs[newMsgs.length - 1].content = fullContent;
                return newMsgs;
              });
            }
          } catch (e) {
            console.error('Error parsing stream:', e);
          }
        }
      }

      // Save assistant message
      saveMessage('assistant', fullContent, sources);
      loadConversations(); // Refresh to update preview

    } catch (err) {
      console.error(err);
      const errorMsg = 'Sorry, I encountered an error. Please try again.';
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = errorMsg;
        return newMsgs;
      });
    } finally {
      setLoading(false);
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

  const downloadDocument = (documentId: string, filename: string) => {
    window.open(`${API_BASE_URL}/documents/${documentId}/download`, '_blank');
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar - Conversation History */}
      <div className={clsx(
        'flex flex-col bg-white border border-gray-200 rounded-xl transition-all duration-300',
        historyOpen ? 'w-72' : 'w-12'
      )}>
        {/* Sidebar Header */}
        <div className="p-3 border-b border-gray-200 flex items-center justify-between">
          {historyOpen && <span className="font-semibold text-gray-700 text-sm">Conversations</span>}
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          >
            {historyOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {historyOpen && (
          <>
            {/* New Chat Button */}
            <div className="p-3">
              <button
                onClick={startNewChat}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                <Plus className="w-4 h-4" />
                New Chat
              </button>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
              {loadingHistory ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                </div>
              ) : conversations.length === 0 ? (
                <p className="text-center text-gray-400 text-xs py-8">
                  No conversations yet
                </p>
              ) : (
                conversations.map(conv => (
                  <div
                    key={conv.id}
                    onClick={() => loadConversation(conv.id)}
                    className={clsx(
                      'group p-3 rounded-lg cursor-pointer transition-colors',
                      conv.id === conversationId
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50 border border-transparent'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {conv.title}
                        </p>
                        <p className="text-xs text-gray-500 truncate mt-0.5">
                          {conv.preview}
                        </p>
                      </div>
                      <button
                        onClick={(e) => deleteConversation(conv.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-red-500" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto space-y-6 pr-4 mb-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-20">
              <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="mb-2">Ask me anything about your documents.</p>
              <button
                onClick={startNewChat}
                className="text-blue-600 hover:underline text-sm"
              >
                Start a new conversation
              </button>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div
              key={i}
              className={clsx(
                'flex gap-4 max-w-3xl',
                msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''
              )}
            >
              <div className={clsx(
                'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-emerald-600 text-white'
              )}>
                {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
              </div>
              
              <div className={clsx(
                'p-4 rounded-2xl text-sm leading-relaxed',
                msg.role === 'user' 
                  ? 'bg-blue-600 text-white rounded-br-none' 
                  : 'bg-white border border-gray-200 shadow-sm rounded-bl-none text-gray-800'
              )}>
                <div className="whitespace-pre-wrap">{msg.content}</div>
                
                {/* Clickable Sources */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
                      <BookOpen className="w-3 h-3" />
                      <span>Sources</span>
                    </div>
                    <div className="space-y-2">
                      {msg.sources.map((source, idx) => (
                        <div 
                          key={idx} 
                          className="bg-gray-50 p-3 rounded-lg border border-gray-100 hover:border-gray-300 transition-colors"
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="font-medium text-gray-900 text-xs truncate">
                              {source.filename}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => viewDocument(source.document_id, source.filename)}
                                className="p-1 hover:bg-gray-200 rounded transition-colors"
                                title="View document"
                              >
                                <Eye className="w-3.5 h-3.5 text-gray-600" />
                              </button>
                              <button
                                onClick={() => downloadDocument(source.document_id, source.filename)}
                                className="p-1 hover:bg-gray-200 rounded transition-colors"
                                title="Download document"
                              >
                                <Download className="w-3.5 h-3.5 text-gray-600" />
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-gray-600 italic line-clamp-2">
                            {source.content_preview}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={scrollRef} />
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="relative max-w-3xl mx-auto w-full">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your question..."
            className="w-full pl-6 pr-12 py-4 rounded-xl border border-gray-200 shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
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
                  onClick={() => downloadDocument(previewDoc.document_id, previewDoc.filename)}
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
