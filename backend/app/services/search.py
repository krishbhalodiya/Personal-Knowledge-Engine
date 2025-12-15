"""
Search Service - Implements Semantic, Keyword, and Hybrid Search.

================================================================================
SEARCH ARCHITECTURE
================================================================================

We implement three types of search:

1. SEMANTIC SEARCH (Vector Similarity)
   ───────────────────────────────────
   - Converts query to embedding vector
   - Finds nearest neighbors in ChromaDB
   - Good for: Concept matching, natural language questions
   - Bad for: Exact keywords, ID lookups, specific names

2. KEYWORD SEARCH (BM25)
   ─────────────────────
   - Uses probabilistic term matching
   - Good for: Exact phrasing, specific terminology, names
   - Bad for: Synonyms, concept exploration

3. HYBRID SEARCH (The Best of Both)
   ────────────────────────────────
   - Runs both searches in parallel
   - Normalizes scores (0-1 range)
   - Combines results using weighted average (Reciprocal Rank Fusion or Linear)
   - Re-ranks final results

================================================================================
RANKING ALGORITHM
================================================================================

Hybrid Score = (Semantic_Score * α) + (Keyword_Score * (1 - α))

Where α (alpha) is the semantic weight (default 0.7).

- α = 1.0: Pure semantic search
- α = 0.0: Pure keyword search
- α = 0.7: Bias towards meaning, but respect exact matches

Why 0.7?
In RAG systems, retrieving the *contextually* relevant chunks is usually
more important than exact keyword matches, but we still want some keyword signal.
"""

import logging
from typing import List, Dict, Any, Optional
import time

from rank_bm25 import BM25Okapi
from ..config import settings
from ..models.search import SearchResult, SearchResponse
from .embeddings import get_embedding_provider
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for executing search queries against the knowledge base.
    """
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.embedding_provider = get_embedding_provider()
        
        # BM25 Index (In-memory cache)
        # In a production system, this would be Elasticsearch/Solr
        # For local use, we rebuild it lazily or keep it in memory
        self._bm25 = None
        self._bm25_doc_ids = []  # Map index -> chunk_id
        self._bm25_corpus = []   # Tokenized corpus
        self._last_index_update = 0
    
    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchResponse:
        """
        Execute semantic search using vector similarity.
        
        PROCESS:
        1. Embed the query string
        2. Query ChromaDB for nearest neighbors
        3. Format results
        """
        start_time = time.time()
        
        # 1. Generate query embedding
        try:
            query_vector = self.embedding_provider.embed(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise ValueError(f"Embedding generation failed: {e}")
        
        # 2. Query Vector Store
        # ChromaDB returns distances (lower is better for L2, higher is better for Cosine)
        # We assume Cosine similarity (1.0 = identical)
        try:
            results = self.vector_store.query(
                query_embedding=query_vector,
                n_results=top_k,
                where=filter_metadata,
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            raise ValueError(f"Vector search failed: {e}")
        
        # 3. Process Results
        search_results = []
        
        # Check if we got any results
        if results and results['ids'] and results['ids'][0]:
            # ChromaDB returns list of lists (for batched queries)
            # We only sent one query, so we take the first list
            ids = results['ids'][0]
            distances = results['distances'][0]  # Or 'similarities' depending on metric
            metadatas = results['metadatas'][0]
            documents = results['documents'][0]
            
            for i in range(len(ids)):
                # Skip if score is below threshold (if using cosine similarity)
                # Note: ChromaDB default is L2 distance (lower is better)
                # If using cosine, distance is 1 - similarity (0 to 2)
                # We normalize to 0-1 score where 1 is best
                
                # Assuming L2 distance for now: Score = 1 / (1 + distance)
                # This is a common heuristic to convert distance to similarity score
                score = 1 / (1 + distances[i])
                
                if score < score_threshold:
                    continue
                
                metadata = metadatas[i] or {}
                
                search_results.append(SearchResult(
                    chunk_id=ids[i],
                    document_id=metadata.get('document_id', 'unknown'),
                    filename=metadata.get('filename', 'unknown'),
                    content=documents[i],
                    score=score,
                    chunk_index=metadata.get('chunk_index', 0),
                    metadata=metadata,
                ))
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Semantic search found {len(search_results)} results in {elapsed_ms:.2f}ms")
        
        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=elapsed_ms
        )

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> SearchResponse:
        """
        Execute hybrid search combining Semantic + Keyword (BM25).
        
        ALGORITHM:
        1. Run Semantic Search -> Get top K*2 results
        2. Run Keyword Search (BM25) -> Get top K*2 results
        3. Normalize scores from both methods (0 to 1)
        4. Combine scores: Final = (Sem * W) + (Key * (1-W))
        5. Sort and return top K
        """
        start_time = time.time()
        
        # Fetch more candidates than needed for re-ranking
        candidate_k = top_k * 2
        
        # 1. Run Semantic Search
        semantic_response = await self.semantic_search(
            query=query,
            top_k=candidate_k,
            filter_metadata=filter_metadata
        )
        
        # 2. Run Keyword Search
        keyword_results = self._keyword_search_bm25(
            query=query,
            top_k=candidate_k
        )
        
        # 3. Merge and Rank
        # Map: chunk_id -> {semantic_score, keyword_score, result_obj}
        merged_results = {}
        
        # Process Semantic Results
        for res in semantic_response.results:
            merged_results[res.chunk_id] = {
                "semantic_score": res.score,
                "keyword_score": 0.0,
                "result": res
            }
            
        # Process Keyword Results
        # Note: Keyword search might return chunks not in semantic results
        # We need to fetch their metadata/content if they are new
        missing_ids = []
        for res in keyword_results:
            if res.chunk_id in merged_results:
                merged_results[res.chunk_id]["keyword_score"] = res.score
            else:
                merged_results[res.chunk_id] = {
                    "semantic_score": 0.0,
                    "keyword_score": res.score,
                    "result": None # Placeholder, need to fetch
                }
                missing_ids.append(res.chunk_id)
        
        # Fetch missing documents from ChromaDB
        if missing_ids:
            fetched_docs = self._fetch_documents(missing_ids)
            for doc in fetched_docs:
                merged_results[doc.chunk_id]["result"] = doc
        
        # 4. Calculate Final Scores
        final_results = []
        
        for chunk_id, data in merged_results.items():
            result_obj = data["result"]
            if not result_obj:
                continue # Skip if we couldn't fetch details
                
            sem_score = data["semantic_score"]
            key_score = data["keyword_score"]
            
            # Weighted Combination
            final_score = (sem_score * semantic_weight) + (key_score * (1.0 - semantic_weight))
            
            # Update score on the object
            result_obj.score = final_score
            # Add debug info to metadata
            result_obj.metadata["_debug_score"] = {
                "semantic": sem_score,
                "keyword": key_score,
                "combined": final_score
            }
            
            final_results.append(result_obj)
            
        # 5. Sort by Final Score
        final_results.sort(key=lambda x: x.score, reverse=True)
        
        # Top K
        top_results = final_results[:top_k]
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Hybrid search combined {len(merged_results)} candidates into {len(top_results)} results in {elapsed_ms:.2f}ms")
        
        return SearchResponse(
            query=query,
            results=top_results,
            total_results=len(top_results),
            search_time_ms=elapsed_ms
        )

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenizer that removes punctuation and lowercases.
        """
        import re
        # Remove non-alphanumeric chars (keep spaces)
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        return text.lower().split()

    def _keyword_search_bm25(self, query: str, top_k: int) -> List[SearchResult]:
        """
        Perform BM25 keyword search on in-memory index.
        """
        # Ensure index is built/updated
        self._ensure_bm25_index()
        
        if not self._bm25 or not self._bm25_doc_ids:
            return []
            
        # Tokenize query using same method as corpus
        tokenized_query = self._tokenize(query)
        
        # Get scores
        scores = self._bm25.get_scores(tokenized_query)
        
        # Get top N indices
        # argsort returns indices of sorted array (ascending), so we reverse
        top_indices = scores.argsort()[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = scores[idx]
            if score <= 0:
                continue
                
            chunk_id = self._bm25_doc_ids[idx]
            
            # Create a partial result
            results.append(SearchResult(
                chunk_id=chunk_id,
                document_id="unknown", # Placeholder
                filename="unknown",    # Placeholder
                content="",           # Placeholder
                score=self._normalize_bm25_score(score),
                chunk_index=0,
                metadata={}
            ))
            
        return results

    def _ensure_bm25_index(self):
        """
        Builds or updates the BM25 index.
        """
        # Only build if empty
        if self._bm25 is not None:
            return

        logger.info("Building BM25 index...")
        
        try:
            all_docs = self.vector_store.get_all_documents(limit=10000)
            
            if not all_docs or not all_docs['ids']:
                logger.warning("No documents to index for BM25")
                return

            self._bm25_doc_ids = all_docs['ids']
            documents = all_docs['documents']
            
            # Tokenize properly
            self._bm25_corpus = [self._tokenize(doc) for doc in documents]
            
            # Build BM25
            self._bm25 = BM25Okapi(self._bm25_corpus)
            logger.info(f"BM25 index built with {len(self._bm25_doc_ids)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            self._bm25 = None

    def _normalize_bm25_score(self, score: float) -> float:
        """
        Normalize BM25 score to 0-1 range roughly.
        BM25 is unbounded (can be 10, 20, etc.), unlike Cosine (0-1).
        
        Simple Sigmoid-like normalization:
        score = 1 - exp(-score/k) 
        
        Or Min-Max if we knew the max.
        We'll use a simple scaling for now.
        """
        # Heuristic scaling
        return 1.0 - (1.0 / (1.0 + score * 0.1))

    def _fetch_documents(self, chunk_ids: List[str]) -> List[SearchResult]:
        """Helper to fetch full document details from ChromaDB by IDs."""
        if not chunk_ids:
            return []
            
        try:
            results = self.vector_store.collection.get(
                ids=chunk_ids,
                include=["documents", "metadatas"]
            )
            
            fetched = []
            if results['ids']:
                for i, cid in enumerate(results['ids']):
                    meta = results['metadatas'][i] or {}
                    fetched.append(SearchResult(
                        chunk_id=cid,
                        document_id=meta.get('document_id', 'unknown'),
                        filename=meta.get('filename', 'unknown'),
                        content=results['documents'][i],
                        score=0.0, # Will be set by caller
                        chunk_index=meta.get('chunk_index', 0),
                        metadata=meta
                    ))
            return fetched
            
        except Exception as e:
            logger.error(f"Failed to fetch documents: {e}")
            return []

# Singleton
_search_service: Optional[SearchService] = None

def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service

