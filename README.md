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
│  │ • OpenAI Ada    │         │ • GPT-4 (cloud)         │   │
│  └─────────────────┘         └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Local Option | Cloud Option |
|-----------|--------------|--------------|
| Embeddings | sentence-transformers (MiniLM) | OpenAI Ada-002 |
| LLM | llama.cpp (Mistral-7B) | OpenAI GPT-4 |
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

# =========================
# Google APIs (for Gmail/Drive)
# =========================
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

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

**Option 1: Cloud (Easiest, Best Quality)**
```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
```

**Option 2: Local (Privacy, No API Costs)**
```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
LLM_MODEL_PATH=./data/models/mistral-7b.gguf
```

**Option 3: Hybrid (Local embeddings, Cloud LLM)**
```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/search?q=...` | Semantic search |
| POST | `/api/search/hybrid` | Hybrid search |
| POST | `/api/chat` | Q&A chat |
| POST | `/api/chat/stream` | Streaming Q&A |
| GET | `/api/settings` | Get current settings |
| PUT | `/api/settings` | Update providers |

### Coming Soon
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/gmail/auth` | Gmail OAuth |
| POST | `/api/gmail/sync` | Sync emails |
| GET | `/api/drive/auth` | Drive OAuth |
| POST | `/api/drive/sync` | Sync documents |

## Development

```bash
# Run tests
cd backend && pytest tests/ -v

# Run with auto-reload
uvicorn app.main:app --reload --port 8000
```

## License

MIT

