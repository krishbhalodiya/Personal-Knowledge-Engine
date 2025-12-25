import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Loader2, Bot, User, BookOpen, Plus, 
  Trash2, Download, Eye, X, ChevronLeft, ChevronRight,
  Edit2, Check, FileText, Image as ImageIcon
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
  is_image?: boolean;
  original_file_url?: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [previewDoc, setPreviewDoc] = useState<DocumentPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (editingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [editingTitle]);

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
      loadConversations();
    } catch (err) {
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

  const startEditingTitle = (convId: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTitle(convId);
    setEditTitle(currentTitle);
  };

  const saveTitle = async (convId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!editTitle.trim()) {
      setEditingTitle(null);
      return;
    }
    
    try {
      await client.patch(`/chat/conversations/${convId}/rename`, { title: editTitle.trim() });
      setConversations(prev => prev.map(c => 
        c.id === convId ? { ...c, title: editTitle.trim() } : c
      ));
    } catch (err) {
      console.error('Failed to rename:', err);
    }
    setEditingTitle(null);
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
    
    if (!conversationId) {
      try {
        const res = await client.post('/chat/conversations/new');
        setConversationId(res.data.id);
      } catch {
        setConversationId(`local_${Date.now()}`);
      }
    }

    const newMessages = [...messages, { role: 'user' as const, content: userMsg }];
    setMessages(newMessages);
    saveMessage('user', userMsg);
    setLoading(true);
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      // Build history for context
      const history = newMessages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
      }));

      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userMsg, 
          stream: true,
          top_k_context: 5,
          history: history.slice(0, -1), // Exclude current message
        })
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

      saveMessage('assistant', fullContent, sources);
      loadConversations();

    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = 'Sorry, I encountered an error. Please try again.';
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

  const currentConv = conversations.find(c => c.id === conversationId);

  return (
    <div className="flex h-[calc(100vh-6rem)] gap-4">
      {/* Sidebar */}
      <div className={clsx(
        'flex flex-col bg-white/90 backdrop-blur-sm border border-gray-200/50 rounded-2xl shadow-lg transition-all duration-300 overflow-hidden',
        historyOpen ? 'w-80' : 'w-14'
      )}>
        <div className="p-3 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
          {historyOpen && (
            <span className="font-semibold text-gray-800 text-sm tracking-tight">Conversations</span>
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
            <div className="p-3">
              <button
                onClick={startNewChat}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl hover:from-blue-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg text-sm font-medium"
              >
                <Plus className="w-4 h-4" />
                New Chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5">
              {loadingHistory ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <Bot className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                  <p className="text-gray-400 text-sm">No conversations yet</p>
                </div>
              ) : (
                conversations.map(conv => (
                  <div
                    key={conv.id}
                    onClick={() => loadConversation(conv.id)}
                    className={clsx(
                      'group p-3 rounded-xl cursor-pointer transition-all',
                      conv.id === conversationId
                        ? 'bg-blue-50 border-2 border-blue-200 shadow-sm'
                        : 'hover:bg-gray-50 border-2 border-transparent'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        {editingTitle === conv.id ? (
                          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                            <input
                              ref={titleInputRef}
                              type="text"
                              value={editTitle}
                              onChange={e => setEditTitle(e.target.value)}
                              onKeyDown={e => e.key === 'Enter' && saveTitle(conv.id)}
                              className="text-sm font-medium w-full px-2 py-0.5 rounded border border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-200"
                            />
                            <button
                              onClick={(e) => saveTitle(conv.id, e)}
                              className="p-1 hover:bg-blue-100 rounded"
                            >
                              <Check className="w-3.5 h-3.5 text-blue-600" />
                            </button>
                          </div>
                        ) : (
                          <p className="text-sm font-medium text-gray-800 truncate">
                            {conv.title}
                          </p>
                        )}
                        <p className="text-xs text-gray-500 truncate mt-1">
                          {conv.preview || 'Empty conversation'}
                        </p>
                      </div>
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={(e) => startEditingTitle(conv.id, conv.title, e)}
                          className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                          title="Rename"
                        >
                          <Edit2 className="w-3.5 h-3.5 text-gray-500" />
                        </button>
                        <button
                          onClick={(e) => deleteConversation(conv.id, e)}
                          className="p-1.5 hover:bg-red-100 rounded-lg transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-red-500" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Main Chat */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        {currentConv && (
          <div className="pb-3 mb-3 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-800 truncate">
              {currentConv.title}
            </h2>
            <p className="text-xs text-gray-500">
              {currentConv.message_count} messages
            </p>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pb-4 pr-2">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center mb-4 shadow-lg">
                <Bot className="w-9 h-9 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">Personal Knowledge Assistant</h3>
              <p className="text-gray-500 text-sm max-w-md mb-6">
                Ask me anything about your documents, emails, and files. I'll search through your knowledge base to find answers.
              </p>
              <button
                onClick={startNewChat}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium hover:underline"
              >
                Start a new conversation →
              </button>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div
              key={i}
              className={clsx(
                'flex gap-3',
                msg.role === 'user' ? 'flex-row-reverse' : ''
              )}
            >
              <div className={clsx(
                'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm',
                msg.role === 'user' 
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
                  : 'bg-gradient-to-br from-emerald-500 to-teal-600'
              )}>
                {msg.role === 'user' 
                  ? <User className="w-5 h-5 text-white" /> 
                  : <Bot className="w-5 h-5 text-white" />
                }
              </div>
              
              <div className={clsx(
                'max-w-[75%] rounded-2xl text-sm leading-relaxed shadow-sm',
                msg.role === 'user' 
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white px-5 py-3' 
                  : 'bg-white border border-gray-100 text-gray-800 px-5 py-4'
              )}>
                <div className="whitespace-pre-wrap">{msg.content || (loading && i === messages.length - 1 ? '...' : '')}</div>
                
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-gray-200/50">
                    <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
                      <BookOpen className="w-3.5 h-3.5" />
                      <span>Sources ({msg.sources.length})</span>
                    </div>
                    <div className="grid gap-2">
                      {msg.sources.map((source, idx) => (
                        <div 
                          key={idx} 
                          className="bg-gray-50 p-3 rounded-xl border border-gray-100 hover:border-blue-200 hover:bg-blue-50/50 transition-all cursor-pointer group"
                          onClick={() => viewDocument(source.document_id, source.filename)}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="font-medium text-gray-800 text-xs truncate flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-gray-400" />
                              {source.filename}
                            </span>
                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={(e) => { e.stopPropagation(); viewDocument(source.document_id, source.filename); }}
                                className="p-1 hover:bg-blue-100 rounded-lg transition-colors"
                                title="View"
                              >
                                <Eye className="w-3.5 h-3.5 text-blue-600" />
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); downloadDocument(source.document_id); }}
                                className="p-1 hover:bg-blue-100 rounded-lg transition-colors"
                                title="Download"
                              >
                                <Download className="w-3.5 h-3.5 text-blue-600" />
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 line-clamp-2">
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

        {/* Input */}
        <form onSubmit={handleSubmit} className="relative mt-auto">
          <div className="relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about your documents..."
              className="w-full pl-5 pr-14 py-4 rounded-2xl border-2 border-gray-200 bg-white shadow-sm focus:border-blue-400 focus:ring-4 focus:ring-blue-100 outline-none transition-all text-sm"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl hover:from-blue-600 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
        </form>
      </div>

      {/* Document Preview Modal */}
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
                <button
                  onClick={() => downloadDocument(previewDoc.document_id)}
                  className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors"
                  title="Download"
                >
                  <Download className="w-5 h-5 text-gray-600" />
                </button>
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
