"""
ECD/llm/groq_client.py
=======================
Groq-backed implementation of LLMClientBase, using Groq's
openai/gpt-oss-20b model with native JSON-schema structured output.

Get a free API key (no credit card) at https://console.groq.com/keys
Set it as the GROQ_API_KEY environment variable (or in ECD/.env) before running.

Reuses OllamaClient.COMPONENT_MEANINGS / COMPLEXITY_RULES / STRUCTURED_SCHEMA
unchanged -- the electrical-diagram rules and JSON shape don't change,
only which model produces them.
"""

import os
import json
import requests

try:
    from ECD.llm.ollama_client import OllamaClient, STRUCTURED_SCHEMA
except ImportError:
    from ollama_client import OllamaClient, STRUCTURED_SCHEMA

try:
    from ECD.llm.base_client import LLMClientBase
except ImportError:
    from base_client import LLMClientBase


class GroqClient(LLMClientBase):
    def __init__(self, model: str = "openai/gpt-oss-20b", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Get a free key at https://console.groq.com/keys"
            )
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def _call(self, system_prompt: str, user_prompt: str, schema: dict | None = None,
              max_tokens: int = 2048) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "diagram_schema", "schema": schema, "strict": True},
            }



        resp = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        if resp.status_code != 200:
            print("\n========== GROQ ERROR ==========")
            print("Status:", resp.status_code)
            print(resp.text)
            print("================================\n")

        resp.raise_for_status()
        resp_json = resp.json()
        
        # Safe debug print
        print("[groq] API response received.")
        
        message = resp_json["choices"][0]["message"]
        content = message.get("content")
        if content is None:
            refusal = message.get("refusal")
            if refusal:
                raise ValueError(f"Groq API model refusal: {refusal}")
            raise ValueError(f"Groq API response choice message content is null. Full response: {resp_json}")
            
        return content

    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        rules = OllamaClient.COMPONENT_MEANINGS + OllamaClient.COMPLEXITY_RULES

        system_prompt = f"""You are generating structured JSON data for an electrical
distribution panel diagram, following these rules exactly:

{rules}

Complexity level in effect: {complexity}

Return ONLY valid JSON matching the required schema -- no explanation, no markdown.
"""

        print(f"[groq] generating structured data | model={self.model}")
        raw = self._call(system_prompt, prompt, schema=STRUCTURED_SCHEMA, max_tokens=2048)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end <= start:
                raise ValueError(f"Invalid or missing JSON output:\n{raw[:500]}")
            result = json.loads(raw[start:end])

        return result
