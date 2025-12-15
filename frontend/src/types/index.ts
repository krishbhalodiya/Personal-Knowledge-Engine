export interface Document {
  id: string;
  filename: string;
  title: string;
  doc_type: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, any>;
}

export interface SearchResult {
  document_id: string;
  chunk_id: string;
  text: string;
  score: number;
  metadata: Record<string, any>;
  doc_metadata: Record<string, any>;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface SourceCitation {
  document_id: string;
  filename: string;
  chunk_id: string;
  content_preview: string;
  relevance_score: number;
}

export interface ChatResponse {
  message: string;
  conversation_id: string;
  sources: SourceCitation[];
  model_used: string;
  response_time_ms: number;
}

export interface ProviderInfo {
  name: string;
  type: string;
  model: string;
  status: string;
  dimension?: number;
}

export interface Settings {
  embedding: {
    current: string;
    options: Record<string, ProviderInfo>;
  };
  llm: {
    current: string;
    options: Record<string, ProviderInfo>;
  };
}

export interface GoogleAuthStatus {
  authenticated: boolean;
  scopes?: string[];
}

