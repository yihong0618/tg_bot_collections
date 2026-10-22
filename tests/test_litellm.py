"""Offline coverage for the LiteLLM handler using the installed SDK's mock responses."""

import copy
import importlib.util
import logging
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test"}, clear=True):
    import config

PACKAGE = "_litellm_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = []
utils = types.ModuleType(f"{PACKAGE}._utils")
utils.bot_reply_first = Mock()
utils.bot_reply_markdown = Mock(return_value=True)
utils.enrich_text_with_urls = lambda text: text
utils.logger = logging.getLogger(__name__)
spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.litellm", Path(__file__).resolve().parents[1] / "handlers/litellm.py"
)
handler = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE] = package
sys.modules[f"{PACKAGE}._utils"] = utils
try:
    spec.loader.exec_module(handler)
finally:
    sys.modules.pop(PACKAGE)
    sys.modules.pop(f"{PACKAGE}._utils")


@unittest.skipIf(handler.litellm is None, "litellm is not installed")
class LiteLLMTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        handler.litellm_player_dict.clear()
        handler.litellm_pro_player_dict.clear()
        real_completion = handler.litellm.completion

        def completion(**kwargs):
            self.calls.append({**kwargs, "messages": copy.deepcopy(kwargs["messages"])})
            # Real LiteLLM response objects, no network.
            return real_completion(**kwargs, mock_response="answer")

        self.enterContext(patch.object(handler.litellm, "completion", completion))

    def configure(self, model="anthropic/claude-sonnet-4-6", key=None, base=None):
        env = {"TELEGRAM_BOT_TOKEN": "test"}
        if model is not None:
            env["LITELLM_MODEL"] = model
        if key is not None:
            env["LITELLM_API_KEY"] = key
        if base is not None:
            env["LITELLM_API_BASE"] = base
        with patch.dict(os.environ, env, clear=True):
            settings = config.Settings(_env_file=None)
        self.enterContext(patch.object(handler, "settings", settings))
        self.enterContext(
            patch.object(handler, "LITELLM_MODEL", settings.litellm_model)
        )

    def test_requires_model(self):
        self.configure(model=None)
        with self.assertRaises(RuntimeError):
            handler._request_kwargs()

    def test_credentials_are_left_to_provider_env_vars(self):
        self.configure()
        self.assertEqual(
            handler._request_kwargs(),
            {"model": "anthropic/claude-sonnet-4-6", "drop_params": True},
        )

    def test_credentials_and_base_are_forwarded_when_set(self):
        self.configure("hosted_vllm/llama", key="sk-test", base="http://vllm:8000/v1")
        kwargs = handler._request_kwargs()
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertEqual(kwargs["api_base"], "http://vllm:8000/v1")

    def test_complete_and_stream_return_text_and_history_message(self):
        self.configure()
        messages = [{"role": "user", "content": "hello"}]
        text, assistant = handler._complete(messages)
        self.assertEqual(text, "answer")
        self.assertEqual(assistant, {"role": "assistant", "content": "answer"})
        self.assertEqual(self.calls[-1]["max_tokens"], 4096)

        bot, reply = Mock(), Mock()
        text, assistant = handler._stream(messages, reply, "LiteLLM", bot)
        self.assertEqual(text, "answer")
        self.assertEqual(assistant, {"role": "assistant", "content": "answer"})
        self.assertTrue(self.calls[-1]["stream"])

    def test_handlers_keep_history_and_clear(self):
        for fn in (handler.litellm_handler, handler.litellm_pro_handler):
            with self.subTest(handler=fn.__name__):
                self.configure()
                message = types.SimpleNamespace(
                    text="hello", from_user=types.SimpleNamespace(id=42)
                )
                fn(message, Mock())
                fn(message, Mock())
                sent = self.calls[-1]["messages"]
                self.assertEqual(
                    [m["role"] for m in sent], ["user", "assistant", "user"]
                )
                message.text = "clear"
                bot = Mock()
                fn(message, bot)
                bot.reply_to.assert_called_once()

    def test_reasoning_and_tool_calls_are_kept_for_the_next_turn(self):
        message = handler._assistant_message(
            "answer",
            "private reasoning",
            [{"type": "thinking", "thinking": "t", "signature": "s"}],
            [{"id": "call_1", "type": "function", "function": {"name": "f"}}],
        )
        self.assertEqual(message["reasoning_content"], "private reasoning")
        self.assertEqual(message["thinking_blocks"][0]["signature"], "s")
        self.assertEqual(message["tool_calls"][0]["id"], "call_1")


if __name__ == "__main__":
    unittest.main()
