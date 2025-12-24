# Personal Knowledge Engine

A hybrid personal knowledge engine with **configurable local/cloud processing**. Index your documents, emails, and notes with semantic search and RAG-powered Q&A.

## Features

- **Document Indexing**: Upload and index PDF, DOCX, Markdown, and text files
- **Semantic Search**: Natural language queries with hybrid ranking (semantic + BM25)
- **RAG-Powered Q&A**: Ask questions with source citations
- **Configurable Providers**: Choose local (privacy) or cloud (quality) for embeddings/LLM
- **Google Integration**: Sync Gmail and Google Drive (coming soon)
- **Chrome Extension**: Index browser history (coming soon)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Controls                            │
│         Choose: Local (Privacy) ←→ Cloud (Quality)         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Provider Layer                            │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │ Embeddings      │         │ LLM                     │   │
│  │ • MiniLM (local)│         │ • llama.cpp (local)     │   │
│  │ • OpenAI Ada    │         │ • GPT-5 (cloud)         │   │
│  └─────────────────┘         └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Project Roadmap

- [x] **Phase 1: Backend Setup** (FastAPI, Project Structure)
- [x] **Phase 2: Document Processing** (Parsers, Chunking, Ingestion)
- [x] **Phase 3: Embeddings** (Local/OpenAI abstraction)
- [x] **Phase 4: Search Engine** (Semantic + Hybrid Search)
- [x] **Phase 5: LLM Integration** (RAG Pipeline, Streaming Chat)
- [x] **Phase 6: Google Integration** (OAuth, Gmail & Drive Sync)
- [ ] **Phase 7: Frontend Interface** (React, Search UI, Chat UI)
- [ ] **Phase 8: Polish & Deployment** (Docker, Final Testing)

## Tech Stack

| Component | Local Option | Cloud Option |
|-----------|--------------|--------------|
| Embeddings | sentence-transformers (MiniLM) | OpenAI text-embedding-3-large (3072 dim) |
| LLM | llama.cpp (Mistral-7B) | OpenAI GPT-5.2 Pro / Gemini 3.0 Pro Preview |
| Vector Store | ChromaDB | ChromaDB |
| Backend | Python 3.11+, FastAPI | - |
| Frontend | React, TypeScript, TailwindCSS | - |

## Project Structure

```
personal-knowledge-engine/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings (provider selection)
│   │   ├── models/              # Pydantic schemas
│   │   ├── routers/             # API endpoints
│   │   ├── services/            # Business logic
│   │   │   ├── embeddings/      # Embedding providers
│   │   │   ├── llm/             # LLM providers
│   │   │   └── vector_store.py  # ChromaDB
│   │   └── utils/               # Chunking, parsing
│   ├── requirements.txt
│   └── tests/
├── frontend/                    # React frontend
├── chrome-extension/            # Browser history (coming soon)
├── data/                        # Local storage (gitignored)
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

API: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### Environment Variables

Create `backend/.env`:

```env
# =========================
# Provider Selection
# =========================
EMBEDDING_PROVIDER=local        # local | openai
LLM_PROVIDER=local              # local | openai

# =========================
# OpenAI (if using cloud)
# =========================
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_CHAT_MODEL=gpt-4o

# =========================
# Google APIs (for Gmail/Drive + Gemini)
# =========================
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_GEMINI_API_KEY=...
GOOGLE_GEMINI_MODEL=gemini-1.5-flash

# =========================
# Local LLM (if using local)
# =========================
LLM_MODEL_PATH=./data/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
LLM_GPU_LAYERS=0                # Set > 0 for GPU acceleration

# =========================
# Application
# =========================
DEBUG=true
CHUNK_SIZE=512
CHUNK_OVERLAP=50
SEARCH_TOP_K=5
```

### Quick Start Options

**Option 1: Unlimited Power (Best Quality)**
```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

**Option 2: Google Ecosystem (Gemini 3.0 + Gmail/Drive)**
```env
EMBEDDING_PROVIDER=openai # or local
LLM_PROVIDER=gemini
OPENAI_API_KEY=sk-...
GOOGLE_GEMINI_API_KEY=AIza...
GOOGLE_GEMINI_MODEL=gemini-1.5-flash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

**Option 3: Local Privacy (No API Costs)**
```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
LLM_MODEL_PATH=./data/models/mistral-7b.gguf
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/documents/{id}/chunks` | View document chunks |
| GET | `/api/search?q=...` | Semantic search (vector only) |
| POST | `/api/search/hybrid` | Hybrid search (vector + keyword) |
| POST | `/api/chat` | Q&A chat |
| POST | `/api/chat/stream` | Streaming Q&A |
| GET | `/api/settings` | Get current settings |
| GET | `/api/settings/providers` | List available providers |
| POST | `/api/settings/test-embedding` | Test embedding generation |

### Google Integration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/google/url` | Get OAuth authorization URL |
| GET | `/api/auth/google/status` | Check auth status |
| GET | `/api/gmail/auth/status` | Check Gmail auth status |
| POST | `/api/gmail/sync` | Sync recent emails |
| GET | `/api/drive/auth/status` | Check Drive auth status |
| POST | `/api/drive/sync` | Sync recent Drive files |

## Development

```bash
# Run tests
cd backend && pytest tests/ -v

# Run with auto-reload
uvicorn app.main:app --reload --port 8000
```

## License

MIT

