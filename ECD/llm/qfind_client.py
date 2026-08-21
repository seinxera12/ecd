"""
ECD/llm/qfind_client.py
=======================
Custom LLM client for qfind-chat backend endpoint (https://ubuntu.tailcd8da4.ts.net).
Provides structured JSON diagram generation and chat completions compatible with OpenAI standard API format.

Uses a 3-stage chain-of-thought pipeline (identical to OllamaClient) for consistent diagram quality:
  Stage 1 — Component Identification (extract raw facts from prompt)
  Stage 2 — Chain-of-Thought Reasoning (apply complexity rules, resolve flags)
  Stage 3 — Structured JSON Assembly (convert reasoning to final JSON)
"""

import os
import json
import re
import requests

try:
    from ECD.llm.base_client import LLMClientBase
    from ECD.llm.ollama_client import OllamaClient, STRUCTURED_SCHEMA
except ImportError:
    from base_client import LLMClientBase
    from ollama_client import OllamaClient, STRUCTURED_SCHEMA


class QFindClient(LLMClientBase):
    """Client interface for the qfind-chat LLM model hosted at https://ubuntu.tailcd8da4.ts.net."""

    def __init__(self, model: str = "qfind-chat", api_key: str | None = None, base_url: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("QFIND_API_KEY", "")
        self.base_url = base_url or os.environ.get("QFIND_URL", "https://ubuntu.tailcd8da4.ts.net")

        clean_url = self.base_url.rstrip("/")
        if clean_url.endswith("/v1/chat/completions") or clean_url.endswith("/chat/completions"):
            self.url = clean_url
        elif clean_url.endswith("/v1"):
            self.url = f"{clean_url}/chat/completions"
        else:
            self.url = f"{clean_url}/v1/chat/completions"

    # ── Core HTTP call ─────────────────────────────────────────────────────────
    def _call(self, system_prompt: str, user_prompt: str, schema: dict | None = None, max_tokens: int = 2048) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }

        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "diagram_schema", "schema": schema, "strict": True},
            }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(self.url, headers=headers, json=payload, timeout=90)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            # Fallback: retry without response_format if proxy rejects it
            if schema is not None and "response_format" in payload:
                del payload["response_format"]
                resp = requests.post(self.url, headers=headers, json=payload, timeout=90)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            raise e

    # ── JSON helper ────────────────────────────────────────────────────────────
    def _extract_json(self, text: str) -> dict | None:
        """Strip markdown fencing and parse JSON. Returns dict or None."""
        text = text.strip()
        # Remove ```json … ``` fences
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: find first {...} block
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        return None

    # ── Stage 1: Component identification ─────────────────────────────────────
    def _stage1_identify(self, prompt: str, complexity: str) -> dict:
        """Extract raw facts from the prompt without applying complexity rules."""
        stage1_schema = {
            "type": "object",
            "properties": {
                "mentioned_components": {"type": "array", "items": {"type": "string"}},
                "named_circuits":       {"type": "array", "items": {"type": "string"}},
                "explicit_exclusions":  {"type": "array", "items": {"type": "string"}},
            },
            "required": ["mentioned_components", "named_circuits", "explicit_exclusions"],
            "additionalProperties": False,
        }

        system_prompt = f"""You are extracting raw facts from an electrical diagram request. Do NOT apply complexity rules yet — just extract what is literally stated.

{OllamaClient.COMPONENT_MEANINGS}

List:
- mentioned_components: component IDs the user explicitly names or clearly implies
- named_circuits: ALL distinct outgoing loads, devices, or circuits the user names — include any device with a distinct name OR a specific rating (e.g. "5.5kW induction motor", "7.5kW pump motor", "3kW HVAC load", "lighting", "sockets"). Each separately named device = one entry. NEVER merge multiple named devices into one entry.
- explicit_exclusions: anything the user says NOT to include (e.g. "no RCD", "no earth")

IMPORTANT: If the user lists N devices with separate names or ratings (e.g. "5.5kW motor, 7.5kW pump, 3kW HVAC"), named_circuits must have N entries — one per device.

Complexity level in effect: {complexity}

Return ONLY valid JSON. No explanation, no markdown."""

        raw = self._call(system_prompt, f"USER PROMPT:\n{prompt}\n\nJSON:", schema=stage1_schema, max_tokens=512)
        result = self._extract_json(raw)
        return result or {"mentioned_components": [], "named_circuits": [], "explicit_exclusions": []}

    # ── Stage 2: Chain-of-thought reasoning ────────────────────────────────────
    def _stage2_reason(self, prompt: str, complexity: str, stage1: dict) -> str:
        """Produce plain-text reasoning that Stage 3 will convert to JSON."""
        # Build the named load expansion block to inject into the stage 2 prompt
        named = stage1.get('named_circuits', [])
        named_count = len(named)
        if named_count >= 2:
            load_expansion_rule = f"""
=== NAMED LOAD EXPANSION — MANDATORY ===
The prompt contains {named_count} DISTINCT named loads/devices: {named}
You MUST generate one separate outcb_N + loads_N pair for EACH one (outcb_1..outcb_{named_count}).
Do NOT collapse them into a single 'loads' entry. Each outcb_N label = the device name/rating. Max 15.
"""
        else:
            load_expansion_rule = ""

        system_prompt = f"""You are reasoning step-by-step about how to build an electrical diagram's structured data. Do NOT output JSON yet — write plain reasoning.

{OllamaClient.COMPONENT_MEANINGS}
{OllamaClient.COMPLEXITY_RULES}
{load_expansion_rule}
Extracted facts from the prompt (Stage 1):
- Mentioned components: {stage1['mentioned_components']}
- Named circuits: {stage1['named_circuits']}
- Explicit exclusions: {stage1['explicit_exclusions']}

Complexity level in effect: {complexity}

Walk through, in order:
1. Final component list — apply the complexity level's rules to the mentioned components, then apply explicit exclusions LAST (they always win).
   - CRITICAL: If there are {named_count} named devices above, produce exactly {named_count} outcb_N entries (outcb_1 through outcb_{named_count}), each with a label matching the device name.
2. Each flag (show_neutral, show_earth, show_rcd, show_protection_notes, show_fault_paths) — state true/false and cite which rule justifies it.
3. Voltage — quote what you found in the prompt, or "unspecified".
4. Language — "en" or "ja", based on whether the prompt contains Japanese text.
5. Phase Hint — "three-phase" / "single-phase" / null.
6. Label wording for each component (per the inference rules).

Be explicit and check your work against the EXPLICIT EXCLUSIONS rule before finishing."""

        return self._call(system_prompt, f"USER PROMPT:\n{prompt}\n\nREASONING:", schema=None, max_tokens=1024)

    # ── Stage 3: Structured assembly ───────────────────────────────────────────
    def _stage3_assemble(self, prompt: str, reasoning: str) -> dict:
        """Convert the reasoning from Stage 2 into the final structured JSON."""
        system_prompt = f"""Convert the reasoning below into the final structured JSON. Follow the reasoning's conclusions exactly — do not re-derive or second-guess them.

Return ONLY valid JSON matching the schema. No explanation, no markdown.

=== OUTPUT SCHEMA ===
{{
  "components": [{{"id": "supply", "label": "label"}}, ...],
  "flags": {{
    "show_neutral": true, "show_earth": true, "show_rcd": true,
    "show_protection_notes": true, "show_fault_paths": true
  }},
  "voltage": "230V AC",
  "language": "en",
  "phase_hint": "three-phase" or "single-phase" or null
}}

=== REASONING TO FOLLOW ===
{reasoning}"""

        raw = self._call(system_prompt, f"ORIGINAL PROMPT:\n{prompt}\n\nJSON:", schema=STRUCTURED_SCHEMA, max_tokens=2048)
        result = self._extract_json(raw)
        if result is None:
            raise ValueError(f"[qfind] Stage 3 produced invalid JSON:\n{raw[:500]}")
        return result

    # ── Public entry point ─────────────────────────────────────────────────────
    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        print(f"[qfind] stage 1 — identifying components | model={self.model}")
        stage1 = self._stage1_identify(prompt, complexity)

        print(f"[qfind] stage 2 — reasoning | model={self.model}")
        reasoning = self._stage2_reason(prompt, complexity, stage1)

        print(f"[qfind] stage 3 — assembling JSON | model={self.model}")
        return self._stage3_assemble(prompt, reasoning)

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        """Plain text chat completion required by LLMClientBase."""
        return self._call(system_prompt, user_prompt, schema=None, max_tokens=max_tokens)
