"""Unit tests for LLMClient."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from SlicerAICopilotLib.llm_client import LLMClient, LLMResponse


class MockChoice:
    def __init__(self, content="test content", finish_reason="stop", reasoning=None):
        self.message = Mock()
        self.message.content = content
        self.message.reasoning_content = reasoning
        self.finish_reason = finish_reason


class MockUsage:
    def __init__(self, prompt=10, completion=20, total=30):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total


class MockResponse:
    def __init__(self, content="test content", reasoning=None, finish_reason="stop"):
        self.choices = [MockChoice(content, finish_reason, reasoning)]
        self.usage = MockUsage()


class MockStreamChunk:
    def __init__(self, content=None, finish_reason=None, reasoning=None, usage=None):
        choice = Mock()
        delta = Mock()
        delta.content = content
        delta.reasoning_content = reasoning
        choice.delta = delta
        choice.finish_reason = finish_reason
        self.choices = [choice]
        self.usage = usage


class TestLLMResponse(unittest.TestCase):

    def test_basic_response(self):
        resp = LLMResponse(content="hello")
        self.assertEqual(resp.content, "hello")
        self.assertIsNone(resp.reasoning)
        self.assertIsNone(resp.finish_reason)
        self.assertIsNone(resp.usage)

    def test_full_response(self):
        resp = LLMResponse(
            content="hello",
            reasoning="thinking",
            finish_reason="stop",
            usage={"prompt_tokens": 10}
        )
        self.assertEqual(resp.content, "hello")
        self.assertEqual(resp.reasoning, "thinking")
        self.assertEqual(resp.finish_reason, "stop")
        self.assertEqual(resp.usage, {"prompt_tokens": 10})


class TestLLMClient(unittest.TestCase):

    def test_init_without_openai(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', False):
            client = LLMClient(api_key="test-key")
            self.assertFalse(client.is_available())

    def test_init_without_api_key(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key=None)
            self.assertFalse(client.is_available())

    def test_complete_returns_empty_when_unavailable(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', False):
            client = LLMClient(api_key="test-key")
            resp = client.complete([{"role": "user", "content": "hi"}])
            self.assertEqual(resp.content, "")
            self.assertEqual(resp.finish_reason, "error")

    def test_parse_response_basic(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            mock_response = MockResponse(content="hello world")
            resp = client._parse_response(mock_response)
            self.assertEqual(resp.content, "hello world")
            self.assertIsNone(resp.reasoning)
            self.assertEqual(resp.finish_reason, "stop")

    def test_parse_response_with_reasoning(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            mock_response = MockResponse(content="answer", reasoning="thinking...")
            resp = client._parse_response(mock_response)
            self.assertEqual(resp.content, "answer")
            self.assertEqual(resp.reasoning, "thinking...")

    def test_parse_response_with_usage(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            mock_response = MockResponse(content="ok")
            resp = client._parse_response(mock_response)
            self.assertIsNotNone(resp.usage)
            self.assertEqual(resp.usage["prompt_tokens"], 10)

    def test_handle_stream(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            chunks = [
                MockStreamChunk(content="Hello"),
                MockStreamChunk(content=" world"),
                MockStreamChunk(finish_reason="stop"),
            ]
            resp = client._handle_stream(iter(chunks))
            self.assertEqual(resp.content, "Hello world")
            self.assertEqual(resp.finish_reason, "stop")

    def test_handle_stream_with_reasoning(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            chunks = [
                MockStreamChunk(reasoning="thinking"),
                MockStreamChunk(content="answer"),
                MockStreamChunk(finish_reason="stop"),
            ]
            resp = client._handle_stream(iter(chunks))
            self.assertEqual(resp.content, "answer")
            self.assertEqual(resp.reasoning, "thinking")

    def test_complete_calls_client(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = MockResponse(content="result")
            client._client = mock_client
            resp = client.complete(
                [{"role": "user", "content": "test"}],
                temperature=0.5,
                max_tokens=100
            )
            self.assertEqual(resp.content, "result")
            mock_client.chat.completions.create.assert_called_once()

    def test_is_available(self):
        with patch('SlicerAICopilotLib.llm_client.OPENAI_AVAILABLE', True):
            client = LLMClient(api_key="test-key")
            client._client = Mock()
            self.assertTrue(client.is_available())


if __name__ == '__main__':
    unittest.main()
