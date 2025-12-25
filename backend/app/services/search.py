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
        start_time = time.time()
        
        try:
            query_vector = self.embedding_provider.embed(query)
        except ValueError as e:
            # Check if it's a quota error - try fallback to local
            error_str = str(e)
            if "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
                logger.warning(f"OpenAI quota error detected, checking collection dimension before fallback: {e}")
                
                # Check collection dimension before falling back
                collection_dim = self.vector_store.get_collection_dimension()
                if collection_dim and collection_dim != 384:
                    # Collection was created with different dimension, can't use local fallback
                    logger.error(
                        f"Cannot fallback to local embeddings: Collection uses {collection_dim}-dimensional embeddings, "
                        f"but local embeddings are 384-dimensional. Please switch to matching provider or reset collection."
                    )
                    raise ValueError(
                        f"OpenAI quota exceeded, but cannot fallback to local embeddings: "
                        f"Collection was created with {collection_dim}-dimensional embeddings (likely OpenAI), "
                        f"while local embeddings are 384-dimensional. "
                        f"To fix: Switch to OpenAI provider in Settings, or reset the collection and re-index with local embeddings."
                    )
                
                # Safe to fallback - collection is empty or uses 384 dims
                try:
                    from .embeddings import get_local_embedding_provider
                    local_provider = get_local_embedding_provider()
                    query_vector = local_provider.embed(query)
                    logger.info("Successfully used local embeddings as fallback")
                except Exception as fallback_error:
                    logger.error(f"Fallback to local embeddings also failed: {fallback_error}")
                    raise ValueError(f"Embedding generation failed. OpenAI quota exceeded and local fallback failed: {fallback_error}")
            else:
                logger.error(f"Failed to embed query: {e}")
                raise ValueError(f"Embedding generation failed: {e}")
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise ValueError(f"Embedding generation failed: {e}")
        
        try:
            results = self.vector_store.query(
                query_embedding=query_vector,
                n_results=top_k,
                where=filter_metadata,
            )
        except ValueError as e:
            # Dimension mismatch or other validation errors
            error_str = str(e)
            if "dimension mismatch" in error_str.lower():
                logger.error(f"Dimension mismatch in vector search: {e}")
                raise ValueError(
                    f"Vector search failed due to embedding dimension mismatch. "
                    f"The collection was created with a different embedding dimension than what you're currently using. "
                    f"{error_str}"
                )
            raise
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            raise ValueError(f"Vector search failed: {e}")
        
        search_results = []
        
        if results and results['ids'] and results['ids'][0]:
            ids = results['ids'][0]
            distances = results['distances'][0]
            metadatas = results['metadatas'][0]
            documents = results['documents'][0]
            
            for i in range(len(ids)):
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
        start_time = time.time()
        
        candidate_k = top_k * 2
        
        semantic_response = await self.semantic_search(
            query=query,
            top_k=candidate_k,
            filter_metadata=filter_metadata
        )
        
        keyword_results = self._keyword_search_bm25(
            query=query,
            top_k=candidate_k
        )
        
        merged_results = {}
        
        for res in semantic_response.results:
            merged_results[res.chunk_id] = {
                "semantic_score": res.score,
                "keyword_score": 0.0,
                "result": res
            }
            
        missing_ids = []
        for res in keyword_results:
            if res.chunk_id in merged_results:
                merged_results[res.chunk_id]["keyword_score"] = res.score
            else:
                merged_results[res.chunk_id] = {
                    "semantic_score": 0.0,
                    "keyword_score": res.score,
                    "result": None
                }
                missing_ids.append(res.chunk_id)
        
        if missing_ids:
            fetched_docs = self._fetch_documents(missing_ids)
            for doc in fetched_docs:
                merged_results[doc.chunk_id]["result"] = doc
        
        final_results = []
        
        for chunk_id, data in merged_results.items():
            result_obj = data["result"]
            if not result_obj:
                continue
                
            sem_score = data["semantic_score"]
            key_score = data["keyword_score"]
            
            final_score = (sem_score * semantic_weight) + (key_score * (1.0 - semantic_weight))
            
            result_obj.score = final_score
            result_obj.metadata["_debug_score"] = {
                "semantic": sem_score,
                "keyword": key_score,
                "combined": final_score
            }
            
            final_results.append(result_obj)
            
        final_results.sort(key=lambda x: x.score, reverse=True)
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
        import re
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        return text.lower().split()

    def _keyword_search_bm25(self, query: str, top_k: int) -> List[SearchResult]:
        self._ensure_bm25_index()
        
        if not self._bm25 or not self._bm25_doc_ids:
            return []
            
        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
        top_indices = scores.argsort()[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = scores[idx]
            if score <= 0:
                continue
                
            chunk_id = self._bm25_doc_ids[idx]
            
            results.append(SearchResult(
                chunk_id=chunk_id,
                document_id="unknown",
                filename="unknown",
                content="",
                score=self._normalize_bm25_score(score),
                chunk_index=0,
                metadata={}
            ))
            
        return results

    def _ensure_bm25_index(self):
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
            self._bm25_corpus = [self._tokenize(doc) for doc in documents]
            self._bm25 = BM25Okapi(self._bm25_corpus)
            logger.info(f"BM25 index built with {len(self._bm25_doc_ids)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            self._bm25 = None

    def _normalize_bm25_score(self, score: float) -> float:
        return 1.0 - (1.0 / (1.0 + score * 0.1))

    def _fetch_documents(self, chunk_ids: List[str]) -> List[SearchResult]:
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

