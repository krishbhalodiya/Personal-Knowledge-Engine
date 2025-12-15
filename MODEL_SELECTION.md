# Model Selection Guide

## Why Multiple Models Matter

Different models excel at different tasks. This guide helps you choose the right model for your use case.

---

## Embedding Models

### OpenAI Embeddings Comparison

| Model | Dimensions | Quality | Speed | Cost | Best For |
|-------|------------|---------|-------|------|----------|
| **text-embedding-3-small** | 1536 | ⭐⭐⭐⭐ | Fast | $0.02/1M | **Most use cases** (recommended) |
| **text-embedding-3-large** | 3072 | ⭐⭐⭐⭐⭐ | Medium | $0.13/1M | Critical applications, multilingual |
| **text-embedding-ada-002** | 1536 | ⭐⭐⭐ | Fast | $0.10/1M | Legacy compatibility |

### When to Use Each

**text-embedding-3-small** (Recommended)
- ✅ Best quality-to-price ratio
- ✅ 1536 dimensions (good balance)
- ✅ Faster than large model
- ✅ Great for: General knowledge bases, mixed content

**text-embedding-3-large** (Premium)
- ✅ Highest quality embeddings
- ✅ 3072 dimensions (more semantic space)
- ✅ Better for: Multilingual content, technical documents, code
- ⚠️ More expensive, slower

**text-embedding-ada-002** (Legacy)
- ✅ Reliable, well-tested
- ⚠️ Older architecture
- ⚠️ More expensive than 3-small
- Use only if: You have existing embeddings in this format

### Local Embeddings (sentence-transformers)

**all-MiniLM-L6-v2** (Default)
- ✅ Free, private, offline
- ✅ 384 dimensions (compact)
- ✅ Fast inference (~10ms)
- ⚠️ Lower quality than OpenAI
- Best for: Privacy-first, offline use, small datasets

**all-mpnet-base-v2** (Better Quality)
- ✅ Better quality than MiniLM
- ✅ 768 dimensions
- ⚠️ Slower (~30ms)
- Best for: Better quality while staying local

---

## LLM Models

### OpenAI GPT Models

| Model | Context | Quality | Speed | Cost | Best For |
|-------|---------|---------|-------|------|----------|
| **gpt-4o** | 128K | ⭐⭐⭐⭐⭐ | Fast | $$ | **Latest & best** (recommended) |
| **gpt-4-turbo** | 128K | ⭐⭐⭐⭐⭐ | Fast | $$ | High-quality Q&A |
| **gpt-3.5-turbo** | 16K | ⭐⭐⭐ | Very Fast | $ | Simple tasks, cost-sensitive |

**gpt-4o** (Recommended)
- ✅ Latest model (as of 2024)
- ✅ Optimized for speed and quality
- ✅ 128K context window
- ✅ Best for: Complex reasoning, RAG, Q&A

**gpt-4-turbo**
- ✅ Excellent quality
- ✅ 128K context (can handle long documents)
- ✅ Great for: Long-form content, multi-step reasoning

**gpt-3.5-turbo**
- ✅ Fast and cheap
- ✅ Good for: Simple Q&A, summarization
- ⚠️ Lower quality than GPT-4

### Google Gemini Models

| Model | Context | Quality | Speed | Cost | Best For |
|-------|---------|---------|-------|------|----------|
| **gemini-2.0-flash-exp** | 1M | ⭐⭐⭐⭐⭐ | Very Fast | Free tier | **Latest experimental** |
| **gemini-1.5-pro** | 1M | ⭐⭐⭐⭐⭐ | Medium | Free tier | Long context, complex tasks |
| **gemini-1.5-flash** | 1M | ⭐⭐⭐⭐ | Fast | Free tier | Fast responses |

**gemini-2.0-flash-exp** (Recommended)
- ✅ Latest experimental model
- ✅ Very fast inference
- ✅ 1M token context (huge!)
- ✅ Free tier: 60 req/min, 1M tokens/day
- ✅ Best for: Most tasks, especially long documents

**gemini-1.5-pro**
- ✅ Highest quality Gemini model
- ✅ 1M token context (can process entire books!)
- ✅ Great for: Complex reasoning, long documents
- ⚠️ Slower than flash

**gemini-1.5-flash**
- ✅ Fast and efficient
- ✅ Good quality
- ✅ Best for: Quick responses, cost-sensitive

### Local LLMs (llama.cpp)

**Mistral-7B-Instruct** (Recommended)
- ✅ Free, private, offline
- ✅ Good quality for 7B model
- ✅ Quantized versions (4-bit) fit in 4GB RAM
- ⚠️ Lower quality than GPT-4/Gemini
- Best for: Privacy-first, offline use

**Llama 3 8B/70B**
- ✅ Better quality than Mistral
- ✅ Larger models available
- ⚠️ Requires more RAM/VRAM

---

## Recommended Configurations

### Best Quality (Cloud)
```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
LLM_PROVIDER=openai
OPENAI_CHAT_MODEL=gpt-4o
```

### Best Value (Cloud)
```env
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
LLM_PROVIDER=gemini
GOOGLE_GEMINI_MODEL=gemini-2.0-flash-exp
```

### Privacy-First (Local)
```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=local
LLM_MODEL_PATH=./data/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

### Hybrid (Local Embeddings, Cloud LLM)
```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=openai
OPENAI_CHAT_MODEL=gpt-4o
```

---

## Model Selection by Use Case

### Personal Knowledge Base (Mixed Content)
- **Embeddings**: `text-embedding-3-small` (good balance)
- **LLM**: `gpt-4o` or `gemini-2.0-flash-exp`

### Technical Documentation
- **Embeddings**: `text-embedding-3-large` (better for code/technical)
- **LLM**: `gpt-4o` (better reasoning)

### Long Documents (Books, Research Papers)
- **Embeddings**: `text-embedding-3-large` (more dimensions = better)
- **LLM**: `gemini-1.5-pro` (1M token context!)

### Privacy-Sensitive (Medical, Legal)
- **Embeddings**: `local` (all-MiniLM-L6-v2)
- **LLM**: `local` (Mistral-7B)

### Cost-Sensitive
- **Embeddings**: `text-embedding-3-small` (cheapest good option)
- **LLM**: `gemini-2.0-flash-exp` (free tier available)

---

## Future Models

The system is designed to easily add new models. When new models are released:

1. **OpenAI**: Update `OPENAI_EMBEDDING_MODEL` or `OPENAI_CHAT_MODEL` in `.env`
2. **Gemini**: Update `GOOGLE_GEMINI_MODEL` in `.env`
3. **New Providers**: Add to `config.py` and create provider class

The abstraction layer means you can switch models without changing code!

