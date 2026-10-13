"""LLM Client - OpenAI-compatible client for multiple providers."""

import os
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    AsyncOpenAI = None

logger = logging.getLogger(__name__)

PROVIDER_CONFIGS = {
    "modelscope": {
        "base_url": "https://api-inference.modelscope.ai/v1",
        "model": "Qwen/Qwen3.5-9B",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
}


@dataclass
class LLMResponse:
    content: str
    reasoning: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict] = None


class LLMClient:
    """OpenAI-compatible LLM client for multiple providers."""
    
    def __init__(
        self,
        provider: str = None,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: float = 120.0
    ):
        self.provider = provider or os.getenv("LLM_PROVIDER", "gemini")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.timeout = timeout
        
        config = PROVIDER_CONFIGS.get(self.provider, {})
        self.base_url = base_url or os.getenv("LLM_BASE_URL", config.get("base_url", ""))
        self.model = model or os.getenv("LLM_MODEL", config.get("model", ""))
        
        self._client = None
        self._async_client = None
        
        if not OPENAI_AVAILABLE:
            logger.warning("openai package not installed. Install with: pip install openai")
        
        self._init_clients()
    
    def _init_clients(self):
        """Initialize sync and async clients."""
        if not OPENAI_AVAILABLE or not self.api_key:
            return
        
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        self._async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
    
    def is_available(self) -> bool:
        """Check if client is configured and ready."""
        return OPENAI_AVAILABLE and self._client is not None and self.api_key is not None
    
    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
        response_format: Optional[Dict] = None
    ) -> LLMResponse:
        """Synchronous completion."""
        if not self.is_available():
            return LLMResponse(
                content="",
                finish_reason="error",
                usage=None
            )
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
            
            if response_format:
                kwargs["response_format"] = response_format
            
            response = self._client.chat.completions.create(**kwargs)
            
            if stream:
                return self._handle_stream(response)
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            return LLMResponse(content="", finish_reason="error", usage=None)
    
    async def acomplete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
        response_format: Optional[Dict] = None
    ) -> LLMResponse:
        """Asynchronous completion."""
        if not self.is_available() or not self._async_client:
            return LLMResponse(content="", finish_reason="error", usage=None)
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
            
            if response_format:
                kwargs["response_format"] = response_format
            
            response = await self._async_client.chat.completions.create(**kwargs)
            
            if stream:
                return await self._handle_stream_async(response)
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"LLM async completion failed: {e}")
            return LLMResponse(content="", finish_reason="error", usage=None)
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse standard (non-streaming) response."""
        choice = response.choices[0]
        message = choice.message
        
        reasoning = None
        if hasattr(message, 'reasoning_content') and message.reasoning_content:
            reasoning = message.reasoning_content
        
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        return LLMResponse(
            content=message.content or "",
            reasoning=reasoning,
            finish_reason=choice.finish_reason,
            usage=usage
        )
    
    def _handle_stream(self, stream) -> LLMResponse:
        """Handle streaming response synchronously."""
        content_parts = []
        reasoning_parts = []
        finish_reason = None
        usage = None
        
        for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta
                
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_parts.append(delta.reasoning_content)
                
                if delta.content:
                    content_parts.append(delta.content)
                
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
        
        return LLMResponse(
            content="".join(content_parts),
            reasoning="".join(reasoning_parts) if reasoning_parts else None,
            finish_reason=finish_reason,
            usage=usage
        )
    
    async def _handle_stream_async(self, stream) -> LLMResponse:
        """Handle streaming response asynchronously."""
        content_parts = []
        reasoning_parts = []
        finish_reason = None
        usage = None
        
        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta
                
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_parts.append(delta.reasoning_content)
                
                if delta.content:
                    content_parts.append(delta.content)
                
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
        
        return LLMResponse(
            content="".join(content_parts),
            reasoning="".join(reasoning_parts) if reasoning_parts else None,
            finish_reason=finish_reason,
            usage=usage
        )
    
    def stream_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ):
        """Generator for streaming completions."""
        if not self.is_available():
            yield ""
            return
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        try:
            stream = self._client.chat.completions.create(**kwargs)
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            yield ""


_llm_client_instance = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance