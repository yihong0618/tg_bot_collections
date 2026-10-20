"""Offline request-boundary coverage using the installed SDKs and mock HTTP."""

import copy
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import httpx

# Isolate Telegram rendering and unrelated handlers, but load the real settings,
# MiniMax handler and SDKs. No provider or Telegram request leaves this process.
with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test"}, clear=True):
    import config

PACKAGE = "_minimax_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = []
utils = types.ModuleType(f"{PACKAGE}._utils")
utils.bot_reply_first = Mock()
utils.bot_reply_markdown = Mock(return_value=True)
utils.enrich_text_with_urls = lambda text: text
utils.logger = logging.getLogger(__name__)
spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.minimax", Path(__file__).resolve().parents[1] / "handlers/minimax.py"
)
minimax = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE] = package
sys.modules[f"{PACKAGE}._utils"] = utils
try:
    spec.loader.exec_module(minimax)
finally:
    sys.modules.pop(PACKAGE)
    sys.modules.pop(f"{PACKAGE}._utils")


TOOL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "lookup", "arguments": '{"value":1}'},
}
BLOCKS = [
    {"type": "thinking", "thinking": "private reasoning", "signature": "signature"},
    {"type": "text", "text": "answer"},
    {"type": "tool_use", "id": "call_1", "name": "lookup", "input": {"value": 1}},
]


def response_data(protocol):
    if protocol == "openai":
        return {
            "id": "completion",
            "object": "chat.completion",
            "created": 1,
            "model": "MiniMax-M3.1-Flash",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "answer",
                        "reasoning_content": "private reasoning",
                        "tool_calls": [TOOL],
                    },
                }
            ],
        }
    return {
        "id": "message",
        "type": "message",
        "role": "assistant",
        "model": "MiniMax-M3.1-Flash",
        "content": BLOCKS,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def stream_data(protocol):
    if protocol == "openai":
        deltas = [
            {"role": "assistant", "reasoning_content": "private "},
            {"reasoning_content": "reasoning"},
            {"content": "ans"},
            {"content": "wer"},
            {
                "tool_calls": [
                    {
                        "index": 0,
                        **{
                            **TOOL,
                            "function": {"name": "lookup", "arguments": '{"value":'},
                        },
                    }
                ]
            },
            {"tool_calls": [{"index": 0, "function": {"arguments": "1}"}}]},
        ]
        chunks = [
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "MiniMax-M3.1-Flash",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            for delta in deltas
        ]
        chunks.append(
            {
                "id": "completion",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "MiniMax-M3.1-Flash",
                "choices": [],
            }
        )
        return (
            "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            + "data: [DONE]\n\n"
        )
    message = {**response_data(protocol), "content": [], "stop_reason": None}
    events = [{"type": "message_start", "message": message}]
    for index, block in enumerate(BLOCKS):
        empty = dict(block)
        if block["type"] == "thinking":
            empty.update(thinking="", signature="")
            deltas = [
                {"type": "thinking_delta", "thinking": "private "},
                {"type": "thinking_delta", "thinking": "reasoning"},
                {"type": "signature_delta", "signature": "signature"},
            ]
        elif block["type"] == "text":
            empty["text"] = ""
            deltas = [
                {"type": "text_delta", "text": "ans"},
                {"type": "text_delta", "text": "wer"},
            ]
        else:
            empty["input"] = {}
            deltas = [
                {"type": "input_json_delta", "partial_json": '{"value":'},
                {"type": "input_json_delta", "partial_json": "1}"},
            ]
        events.append(
            {"type": "content_block_start", "index": index, "content_block": empty}
        )
        events.extend(
            {"type": "content_block_delta", "index": index, "delta": delta}
            for delta in deltas
        )
        events.append({"type": "content_block_stop", "index": index})
    events.extend(
        [
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": 1},
            },
            {"type": "message_stop"},
        ]
    )
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    )


class MiniMaxTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        minimax.minimax_player_dict.clear()
        minimax.minimax_pro_player_dict.clear()

    def configure(self, protocol, model=None, base=None):
        env = {
            "TELEGRAM_BOT_TOKEN": "test",
            "MINIMAX_API_KEY": "test",
            "MINIMAX_API_TYPE": protocol,
        }
        if model is not None:
            env["MINIMAX_MODEL"] = model
        if base is not None:
            env["MINIMAX_BASE_URL"] = base
        with patch.dict(os.environ, env, clear=True):
            settings = config.Settings(_env_file=None)
        self.enterContext(patch.object(minimax, "settings", settings))
        self.enterContext(
            patch.object(minimax, "MINIMAX_MODEL", settings.minimax_model)
        )
        sdk = minimax._create_client()
        sdk._client.close()
        sdk._client = httpx.Client(transport=httpx.MockTransport(self.handle))
        self.addCleanup(sdk.close)
        self.enterContext(patch.object(minimax, "client", sdk))

    def handle(self, request):
        body = json.loads(request.content)
        self.requests.append((str(request.url), body))
        protocol = minimax.settings.minimax_api_type
        if body.get("stream"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=stream_data(protocol),
            )
        return httpx.Response(200, json=response_data(protocol))

    def test_without_api_key_keeps_handler_disabled(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test"}, clear=True):
            settings = config.Settings(_env_file=None)
        with patch.object(minimax, "settings", settings):
            self.assertIsNone(minimax._create_client())

    def test_default_and_explicit_models_at_http_boundary(self):
        for protocol in ("openai", "anthropic"):
            for model in (None, "MiniMax-M3", "MiniMax-M2.7", "custom-model"):
                suffix = "/v1" if protocol == "openai" else "/anthropic"
                for base in (
                    None,
                    f"https://api.minimax.cn{suffix}",
                    f"https://api.minimaxi.com{suffix}",
                    f"https://custom.invalid{suffix}",
                ):
                    with self.subTest(protocol=protocol, model=model, base=base):
                        self.configure(protocol, model, base)
                        for streaming in (False, True):
                            messages = [{"role": "user", "content": "hello"}]
                            if streaming:
                                text, _ = minimax._stream(
                                    messages, Mock(), "MiniMax", Mock()
                                )
                            else:
                                text, _ = minimax._complete(messages)
                            self.assertEqual(text, "answer")
                            url, body = self.requests[-1]
                            expected_base = base or (
                                minimax.OPENAI_BASE_URL
                                if protocol == "openai"
                                else minimax.ANTHROPIC_BASE_URL
                            )
                            self.assertEqual(
                                url,
                                expected_base
                                + (
                                    "/chat/completions"
                                    if protocol == "openai"
                                    else "/v1/messages"
                                ),
                            )
                            self.assertEqual(
                                body["model"], model or "MiniMax-M3.1-Flash"
                            )
                            self.assertEqual(body["messages"], messages)
                            for key in (
                                "thinking",
                                "reasoning_effort",
                                "output_config",
                                "service_tier",
                                "reasoning_split",
                            ):
                                self.assertNotIn(key, body)

    def test_history_tools_and_images_survive_http_serialization(self):
        for protocol in ("openai", "anthropic"):
            for streaming in (False, True):
                with self.subTest(protocol=protocol, streaming=streaming):
                    self.configure(protocol)
                    if protocol == "openai":
                        image = {
                            "type": "image_url",
                            "image_url": {
                                "url": "https://example.com/image.png",
                                "detail": "high",
                            },
                        }
                        result = {
                            "role": "tool",
                            "tool_call_id": "call_1",
                            "content": "done",
                        }
                    else:
                        image = {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "aW1hZ2U=",
                            },
                        }
                        result = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_1",
                                    "content": "done",
                                }
                            ],
                        }
                    messages = [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "describe"}, image],
                        }
                    ]
                    original = copy.deepcopy(messages)
                    if streaming:
                        text, assistant = minimax._stream(
                            messages, Mock(), "MiniMax", Mock()
                        )
                    else:
                        text, assistant = minimax._complete(messages)
                    self.assertEqual(text, "answer")
                    self.assertEqual(messages, original)
                    minimax._complete([*messages, assistant, result])
                    sent = self.requests[-1][1]["messages"]
                    self.assertEqual(sent[0], original[0])
                    self.assertEqual(sent[2], result)
                    if protocol == "openai":
                        self.assertEqual(
                            sent[1]["reasoning_content"], "private reasoning"
                        )
                        self.assertEqual(sent[1]["tool_calls"], [TOOL])
                    else:
                        self.assertEqual(sent[1]["content"], BLOCKS)

    def test_handlers_keep_reasoning_on_next_turn(self):
        for protocol in ("openai", "anthropic"):
            for handler in (minimax.minimax_handler, minimax.minimax_pro_handler):
                with self.subTest(protocol=protocol, handler=handler.__name__):
                    self.configure(protocol)
                    message = types.SimpleNamespace(
                        text="hello", from_user=types.SimpleNamespace(id=42)
                    )
                    handler(message, Mock())
                    handler(message, Mock())
                    sent = self.requests[-1][1]["messages"]
                    self.assertEqual(len(sent), 3)
                    if protocol == "openai":
                        self.assertEqual(
                            sent[1]["reasoning_content"], "private reasoning"
                        )
                    else:
                        self.assertEqual(sent[1]["content"], BLOCKS)
                    message.text = "clear"
                    handler(message, Mock())


if __name__ == "__main__":
    unittest.main()
