"""Offline coverage for the URL enrichment request boundary."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from telegramify_markdown import customize

spec = importlib.util.spec_from_file_location(
    "_url_enrichment_utils",
    Path(__file__).resolve().parents[1] / "handlers/_utils.py",
)
utils = importlib.util.module_from_spec(spec)
with patch.object(
    customize,
    "get_runtime_config",
    return_value=SimpleNamespace(markdown_symbol=SimpleNamespace()),
    create=True,
):
    spec.loader.exec_module(utils)


class TestUrlEnrichment(unittest.TestCase):
    @patch.dict(os.environ, {"MONID_API_KEY": "test"}, clear=True)
    @patch.object(utils.requests, "get")
    @patch.object(utils.requests, "post")
    def test_monid_enriches_two_urls_with_only_monid_key(self, post, get):
        urls = ["https://example.com/中文", "https://example.org/"]
        post.side_effect = [
            Mock(status_code=200, json=Mock(return_value={"output": {"content": text}}))
            for text in ("# First", "# Second")
        ]
        with patch.object(utils, "extract_url_from_text", return_value=urls):
            result = utils.enrich_text_with_urls("Read " + " and ".join(urls))

        self.assertEqual(
            result,
            "Read \n```markdown\n# First\n```\n and \n```markdown\n# Second\n```\n",
        )
        self.assertEqual(post.call_count, 2)
        for request, url in zip(post.call_args_list, urls):
            self.assertEqual(request.args, ("https://api.monid.ai/v1/run",))
            self.assertEqual(
                request.kwargs["headers"],
                {
                    "Authorization": "Bearer test",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            self.assertIn(url.encode("utf-8"), request.kwargs["data"])
            self.assertEqual(
                json.loads(request.kwargs["data"]),
                {
                    "provider": "litescrape",
                    "endpoint": "/web/fetch",
                    "input": {
                        "body": {
                            "url": url,
                            "respond_with": "markdown",
                            "token_budget": 20000,
                        }
                    },
                },
            )
        get.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    @patch.object(utils.requests, "post")
    @patch.object(utils.requests, "get")
    def test_jina_reader_passes_through_http_error_body(self, get, post):
        get.return_value = Mock(status_code=404, text='{"message": "not found"}')
        url = "https://example.com/missing"
        self.assertEqual(
            utils.get_text_from_jina_reader(url), '{"message": "not found"}'
        )
        get.assert_called_once_with(f"https://r.jina.ai/{url}")
        post.assert_not_called()

    @patch.dict(os.environ, {"MONID_API_KEY": "test"}, clear=True)
    @patch.object(utils.requests, "post")
    def test_monid_passes_through_provider_error_body(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {
            "status": "COMPLETED",
            "providerResponse": {"httpStatus": 404, "error": {"message": "not found"}},
        }
        self.assertEqual(
            utils.get_text_from_jina_reader("https://example.com/missing"),
            '{"message": "not found"}',
        )

    @patch.dict(os.environ, {"MONID_API_KEY": "test"}, clear=True)
    @patch.object(utils.time, "sleep")
    @patch.object(utils.requests, "get")
    @patch.object(utils.requests, "post")
    def test_monid_polls_using_initial_run_id(self, post, get, sleep):
        post.return_value = Mock(status_code=202)
        post.return_value.json.return_value = {"runId": "123"}
        pending = Mock()
        pending.json.return_value = {"status": "RUNNING"}
        completed = Mock()
        completed.json.return_value = {
            "status": "COMPLETED",
            "output": {"content": "# Page"},
        }
        get.side_effect = [pending, completed]
        self.assertEqual(utils.get_text_from_jina_reader("example.com"), "# Page")
        self.assertEqual(
            [request.args for request in get.call_args_list],
            [("https://api.monid.ai/v1/runs/123",)] * 2,
        )
        self.assertEqual(sleep.call_args_list, [call(2), call(2)])
