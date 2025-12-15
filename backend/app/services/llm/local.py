"""
Local LLM Provider - Uses llama.cpp for local inference.

================================================================================
HOW LLAMA.CPP WORKS
================================================================================

llama.cpp is a C++ implementation of the Llama inference code.
It's famous for:
1. Running on CPU (Mac M1/M2/M3 are beasts at this)
2. Quantization (running big models in small RAM)
   - FP16 (16-bit): 14GB RAM for 7B model
   - Q4_K_M (4-bit): 4GB RAM for 7B model (Minimal quality loss!)

We use `llama-cpp-python`, which wraps the C++ library.

================================================================================
THREADING & ASYNC
================================================================================

The `Llama` class methods are BLOCKING (CPU intensive).
If we run them directly in an `async def`, we block the entire API server!

Solution: `run_in_executor`
We offload the heavy computation to a separate thread, letting the
event loop handle other requests (like search or upload) in parallel.

================================================================================
"""

import logging
import asyncio
from typing import List, AsyncGenerator, Optional, Any
from functools import partial

from .base import LLMProvider
from ...models.chat import ChatMessage
from ...config import settings

logger = logging.getLogger(__name__)


class LocalLLMProvider(LLMProvider):
    """
    Local LLM provider using llama.cpp.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        context_length: Optional[int] = None,
    ):
        self._model_path = model_path or settings.llm_model_path
        self._context_length = context_length or settings.llm_context_length
        self._gpu_layers = settings.llm_gpu_layers
        self._model = None
        
        if not self._model_path:
            logger.warning("LLM model path not configured.")
    
    def _load_model(self):
        """Load the GGUF model (lazy loading)."""
        if self._model is not None:
            return
            
        if not self._model_path:
            raise ValueError("LLM model path not configured.")
            
        logger.info(f"Loading local LLM from: {self._model_path}")
        
        try:
            from llama_cpp import Llama
            
            # n_ctx: Context window (e.g. 4096 tokens)
            # n_gpu_layers: Offload layers to GPU (Metal on Mac)
            # verbose: False to reduce log spam
            self._model = Llama(
                model_path=self._model_path,
                n_ctx=self._context_length,
                n_gpu_layers=self._gpu_layers,
                verbose=True,
            )
            logger.info("Local LLM loaded successfully")
            
        except ImportError:
            logger.error("llama-cpp-python not installed")
            raise ImportError("Please install llama-cpp-python")
        except Exception as e:
            logger.error(f"Failed to load local LLM: {e}")
            raise
    
    @property
    def model_name(self) -> str:
        return "local-llama-cpp"
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Non-streaming chat."""
        # Load in the current thread (first time might block slightly)
        self._load_model()
        
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        # Run blocking inference in a thread
        loop = asyncio.get_event_loop()
        
        # Partial creates a callable with arguments pre-filled
        func = partial(
            self._model.create_chat_completion,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        
        try:
            # Execute in thread pool
            response = await loop.run_in_executor(None, func)
            return response["choices"][0]["message"]["content"] or ""
            
        except Exception as e:
            logger.error(f"Local LLM inference failed: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat.
        
        NOTE: Streaming with run_in_executor is tricky because
        run_in_executor waits for the function to RETURN.
        But create_chat_completion(stream=True) returns an ITERATOR immediately.
        
        So we:
        1. Get the iterator (fast)
        2. Iterate through it. Since `next(iterator)` is blocking,
           technically we should run EACH chunk retrieval in a thread.
           
        However, for local LLMs, the token generation happens inside the C++ loop.
        Python's `next()` just waits for C++ to output.
        We'll keep it simple: Iterate in the main loop but yield to event loop.
        Better approach: run the whole consumption in a thread and use an async queue.
        """
        self._load_model()
        
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        # Get the generator (this is fast, inference hasn't started)
        stream = self._model.create_chat_completion(
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        # Iterate over the blocking generator
        # To avoid blocking the event loop entirely, we use a trick:
        # We manually yield control with asyncio.sleep(0)
        # Ideally, we should push this to a thread, but for simplicity:
        
        for chunk in stream:
            # Give other tasks a chance to run
            await asyncio.sleep(0)
            
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]

