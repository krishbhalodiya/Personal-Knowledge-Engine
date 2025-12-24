import logging
import asyncio
from typing import List, AsyncGenerator, Optional, Any
from functools import partial

from .base import LLMProvider
from ...models.chat import ChatMessage
from ...config import settings

logger = logging.getLogger(__name__)


class LocalLLMProvider(LLMProvider):
    
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
        if self._model is not None:
            return
            
        if not self._model_path:
            raise ValueError("LLM model path not configured.")
            
        logger.info(f"Loading local LLM from: {self._model_path}")
        
        try:
            from llama_cpp import Llama
            
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
        self._load_model()
        
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        loop = asyncio.get_event_loop()
        func = partial(
            self._model.create_chat_completion,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        
        try:
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
        self._load_model()
        
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        stream = self._model.create_chat_completion(
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        for chunk in stream:
            await asyncio.sleep(0)
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                yield delta["content"]

