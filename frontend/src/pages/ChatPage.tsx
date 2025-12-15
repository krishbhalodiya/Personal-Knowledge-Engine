import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, BookOpen } from 'lucide-react';
import { API_BASE_URL } from '../api/client';
import { ChatMessage, SourceCitation } from '../types';
import clsx from 'clsx';

interface Message extends ChatMessage {
  sources?: SourceCitation[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    // Create a placeholder for the assistant response
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Process all complete lines
        buffer = lines.pop() || ''; // Keep the last incomplete line in buffer

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            
            setMessages(prev => {
              const newMsgs = [...prev];
              const lastMsg = newMsgs[newMsgs.length - 1];
              
              if (data.chunk) {
                lastMsg.content += data.chunk;
              }
              if (data.sources) {
                lastMsg.sources = data.sources;
              }
              return newMsgs;
            });
          } catch (e) {
            console.error('Error parsing stream:', e);
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev.slice(0, -1), // Remove the empty assistant message
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex-1 overflow-y-auto space-y-6 pr-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Ask me anything about your documents.</p>
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
              'p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-br-none' 
                : 'bg-white border border-gray-200 shadow-sm rounded-bl-none text-gray-800'
            )}>
              {msg.content}
              
              {/* Citations */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100/20">
                  <div className="flex items-center gap-2 text-xs font-semibold opacity-70 mb-2">
                    <BookOpen className="w-3 h-3" />
                    <span>Sources</span>
                  </div>
                  <div className="space-y-2">
                    {msg.sources.map((source, idx) => (
                      <div key={idx} className="text-xs opacity-80 bg-black/5 p-2 rounded">
                        <span className="font-medium block mb-1">{source.filename}</span>
                        <span className="italic block truncate">{source.content_preview}</span>
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
  );
}

