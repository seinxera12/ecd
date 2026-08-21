"""
tests/test_qfind_client.py
===========================
Unit tests for QFindClient implementation.
"""

import unittest
from unittest.mock import patch, MagicMock
from ECD.llm.qfind_client import QFindClient
from ECD.llm.llm_factory import get_llm_client


class TestQFindClient(unittest.TestCase):

    def test_qfind_client_init_defaults(self):
        client = QFindClient()
        self.assertEqual(client.model, "qfind-chat")
        self.assertTrue(client.url.endswith("/v1/chat/completions"))

    def test_qfind_client_factory_lookup(self):
        client = get_llm_client("QFind (Custom Model)")
        self.assertIsInstance(client, QFindClient)
        self.assertEqual(client.model, "qfind-chat")

    @patch("requests.post")
    def test_qfind_client_call_success(self, mock_post):
        """Stage 1 → Stage 2 → Stage 3 pipeline produces a valid diagram dict."""

        # Helper to build a mock response with given body text
        def make_resp(body: str):
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {"choices": [{"message": {"content": body}}]}
            return m

        stage1_json = '{"mentioned_components": ["supply", "maincb"], "named_circuits": [], "explicit_exclusions": []}'
        stage2_text = "Stage 2 reasoning: supply is grid source, maincb is 100A breaker, no RCD needed."
        stage3_json = (
            '{"components": [{"id": "supply", "label": "Main Supply (230V AC)"}, '
            '{"id": "maincb", "label": "100A Main Breaker"}], '
            '"flags": {"show_neutral": false, "show_earth": false, "show_rcd": false, '
            '"show_protection_notes": false, "show_fault_paths": false}, '
            '"voltage": "230V AC", "language": "en", "phase_hint": "single-phase"}'
        )

        mock_post.side_effect = [make_resp(stage1_json), make_resp(stage2_text), make_resp(stage3_json)]

        client = QFindClient()
        res = client.prompt_to_structured_data("Single phase panel with main supply and 100A main breaker.")
        self.assertIn("components", res)
        self.assertEqual(len(res["components"]), 2)
        self.assertEqual(res["voltage"], "230V AC")



if __name__ == "__main__":
    unittest.main()
