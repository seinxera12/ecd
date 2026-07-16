"""
ECD/llm/gemini_client.py
=========================
Gemini-backed implementation of LLMClientBase, using Gemini's free-tier
API with native response_schema structured output.

Get a free API key (no credit card) at https://aistudio.google.com/apikey
Set it as the GEMINI_API_KEY environment variable (or in ECD/.env) before running.

Note: Google's free tier trains on your prompts by default outside the
EU/UK/EEA -- keep this in mind if any real client-derived prompts are ever
used for testing, given this project's otherwise offline/private design.
"""

import os
import json
import requests

try:
    from ECD.llm.ollama_client import OllamaClient
except ImportError:
    from ollama_client import OllamaClient

try:
    from ECD.llm.base_client import LLMClientBase
except ImportError:
    from base_client import LLMClientBase


# Gemini's response_schema uses a subset of the OpenAPI schema format --
# no "enum: [..., null]" mixed-type shorthand like STRUCTURED_SCHEMA uses
# for phase_hint, so it's expressed slightly differently here.
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "components": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "label": {"type": "STRING"},
                },
                "required": ["id", "label"],
            },
        },
        "flags": {
            "type": "OBJECT",
            "properties": {
                "show_neutral": {"type": "BOOLEAN"},
                "show_earth": {"type": "BOOLEAN"},
                "show_rcd": {"type": "BOOLEAN"},
                "show_protection_notes": {"type": "BOOLEAN"},
                "show_fault_paths": {"type": "BOOLEAN"},
            },
            "required": ["show_neutral", "show_earth", "show_rcd",
                         "show_protection_notes", "show_fault_paths"],
        },
        "voltage": {"type": "STRING"},
        "language": {"type": "STRING", "enum": ["en", "ja"]},
        "phase_hint": {"type": "STRING", "enum": ["single-phase", "three-phase", "none"]},
    },
    "required": ["components", "flags", "voltage", "language", "phase_hint"],
}


class GeminiClient(LLMClientBase):
    def __init__(self, model: str = "gemini-3.5-flash", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_SCHEMA,
            },
        }
        resp = requests.post(self.url, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        rules = OllamaClient.COMPONENT_MEANINGS + OllamaClient.COMPLEXITY_RULES

        system_prompt = f"""You are generating structured JSON data for an electrical
distribution panel diagram, following these rules exactly:

{rules}

Complexity level in effect: {complexity}
"""

        print(f"[gemini] generating structured data | model={self.model}")
        raw = self._call(system_prompt, prompt, max_tokens=4096)
        result = json.loads(raw)

        # Gemini schema uses "none" (a real enum string) instead of null,
        # since response_schema doesn't support nullable enums the same
        # way -- normalize back to None/null to match STRUCTURED_SCHEMA's
        # contract that the rest of the app expects.
        if result.get("phase_hint") == "none":
            result["phase_hint"] = None

        return result
