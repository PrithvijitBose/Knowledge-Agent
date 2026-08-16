import os
import unittest
from unittest.mock import patch, MagicMock
import httpx

import providers


class TestMultiLLMProviders(unittest.TestCase):

    def test_provider_registry(self):
        """Verify all supported providers are registered."""
        for expected in ["mistral", "openai", "anthropic", "gemini", "groq", "ollama", "mock"]:
            self.assertIn(expected, providers.PROVIDER_REGISTRY)

    def test_provider_auto_detection_and_priority(self):
        """Verify get_provider auto-detects based on env vars or explicit arguments."""
        # 1. Explicit selection
        p = providers.get_provider("openai")
        self.assertIsInstance(p, providers.OpenAIProvider)

        # 2. Env var selection
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            p = providers.get_provider()
            self.assertIsInstance(p, providers.AnthropicProvider)

        # 3. Auto-detection from GROQ_API_KEY
        with patch.dict(os.environ, {"LLM_PROVIDER": "", "MISTRAL_API_KEY": "", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GROQ_API_KEY": "gsk_test"}):
            p = providers.get_provider()
            self.assertIsInstance(p, providers.GroqProvider)

        # 4. Auto-detection from GEMINI_API_KEY
        with patch.dict(os.environ, {"LLM_PROVIDER": "", "MISTRAL_API_KEY": "", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "AIzaSy_test", "GROQ_API_KEY": ""}):
            p = providers.get_provider()
            self.assertIsInstance(p, providers.GeminiProvider)

    @patch.object(httpx.Client, "post")
    def test_mistral_provider_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Mistral context answer"}}]
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"MISTRAL_API_KEY": "mistral_key_123"}):
            provider = providers.MistralProvider(model="mistral-small-2506")
            ans = provider.generate("System rule", "User query")
            self.assertEqual(ans, "Mistral context answer")
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertIn("Bearer mistral_key_123", kwargs["headers"]["Authorization"])
            self.assertEqual(kwargs["json"]["model"], "mistral-small-2506")

    @patch.object(httpx.Client, "post")
    def test_openai_provider_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "OpenAI context answer"}}]
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
            provider = providers.OpenAIProvider(model="gpt-4o-mini")
            ans = provider.generate("System rule", "User query")
            self.assertEqual(ans, "OpenAI context answer")
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertIn("Bearer sk-openai-test", kwargs["headers"]["Authorization"])
            self.assertEqual(kwargs["json"]["model"], "gpt-4o-mini")

    @patch.object(httpx.Client, "post")
    def test_anthropic_provider_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "Claude context answer"}]
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            provider = providers.AnthropicProvider(model="claude-3-5-haiku-20241022")
            ans = provider.generate("System rule", "User query")
            self.assertEqual(ans, "Claude context answer")
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs["headers"]["x-api-key"], "sk-ant-test")
            self.assertEqual(kwargs["json"]["system"], "System rule")

    @patch.object(httpx.Client, "post")
    def test_gemini_provider_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Gemini context answer"}]}}]
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key-123"}):
            provider = providers.GeminiProvider(model="gemini-1.5-flash")
            ans = provider.generate("System rule", "User query")
            self.assertEqual(ans, "Gemini context answer")
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertIn("key=gemini-key-123", args[0])
            self.assertEqual(kwargs["json"]["contents"][0]["parts"][0]["text"], "User query")

    @patch.object(httpx.Client, "post")
    def test_ollama_provider_generation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "Ollama local answer"}
        }
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"OLLAMA_HOST": "http://localhost:11434"}):
            provider = providers.OllamaProvider(model="llama3.2:latest")
            ans = provider.generate("System rule", "User query")
            self.assertEqual(ans, "Ollama local answer")
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(args[0], "http://localhost:11434/api/chat")
            self.assertEqual(kwargs["json"]["model"], "llama3.2:latest")

    def test_mock_provider_generation(self):
        provider = providers.MockProvider(canned_response="Hermetic mock test response")
        self.assertTrue(provider.is_configured())
        ans = provider.generate("system", "user")
        self.assertEqual(ans, "Hermetic mock test response")

    def test_list_providers(self):
        info = providers.list_providers()
        self.assertIn("mistral", info)
        self.assertIn("openai", info)
        self.assertIn("anthropic", info)
        self.assertIn("gemini", info)
        self.assertIn("groq", info)
        self.assertIn("ollama", info)


if __name__ == "__main__":
    unittest.main()
