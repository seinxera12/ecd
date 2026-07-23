# ECD/llm/ollama_client.py
import json
import re
import requests
from PySide6.QtCore import QThread, Signal

try:
    from ECD.llm.base_client import LLMClientBase
except ImportError:
    from base_client import LLMClientBase

STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string"
                    },
                    "label": {"type": "string"}
                },
                "required": ["id", "label"],
                "additionalProperties": False
            }
        },
        "flags": {
            "type": "object",
            "properties": {
                "show_neutral":          {"type": "boolean"},
                "show_earth":            {"type": "boolean"},
                "show_rcd":              {"type": "boolean"},
                "show_protection_notes": {"type": "boolean"},
                "show_fault_paths":      {"type": "boolean"}
            },
            "required": ["show_neutral", "show_earth", "show_rcd", "show_protection_notes", "show_fault_paths"],
            "additionalProperties": False
        },
        "voltage":  {"type": "string"},
        "language": {"type": "string", "enum": ["en", "ja"]},
        "phase_hint": {
            "type": ["string", "null"],
            "enum": ["single-phase", "three-phase", None]
        }
    },
    "required": ["components", "flags", "voltage", "language", "phase_hint"],
    "additionalProperties": False
}

class OllamaClient(LLMClientBase):
    def __init__(self, model="mistral:7b-instruct", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    # ── Shared rules text, reused across stages 1 and 2, and by other backends ──
    COMPONENT_MEANINGS = """
=== ALLOWED COMPONENT IDs ===
Standard IDs: supply, maincb, rcd, rcbo, bus, nbar, ebar, loads
Standard Outgoing IDs: outcb_1, outcb_2, outcb_3, outcb_4, outcb_5, outcb_6, outcb_7, outcb_8, outcb_9, outcb_10, outcb_11, outcb_12, outcb_13, outcb_14, outcb_15
Custom IDs: You can use any descriptive ID (e.g., 'ats', 'spd', 'meter', 'contactor') for unrecognized or custom components requested by the user. Do NOT map custom components to standard IDs like rcd or rcbo.

=== COMPONENT MEANINGS ===
supply   = incoming mains / grid source
maincb   = main circuit breaker (MCB / MCCB)
rcd      = residual current device (earth fault protection, monitors leakage)
rcbo     = combined RCD + MCB in one unit
bus      = busbar / distribution bar
nbar     = neutral bar / neutral link
ebar     = earth bar / protective earth bar / safety earth
outcb_N  = outgoing branch circuit breaker (one per named circuit)
loads    = load circuits / consuming devices
"""

    COMPLEXITY_RULES = """
=== COMPLEXITY RULES ===
"Neutral" (prompt-only mode):
  - Include ONLY what the user actually describes. Do not add anything they did not mention.
  - flags must reflect ONLY what the user described.

"Simple":
  - Phase wire only. No neutral, no earth, no RCD, no fault paths.
  - Always include: supply, maincb, loads.
  - show_neutral=false, show_earth=false, show_rcd=false, show_fault_paths=false.
  - Add any extra components the user explicitly names, but never add implicit ones.

"Standard":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include the defaults PLUS anything the user explicitly names.
  - show_neutral=true, show_earth=true, show_rcd=true.
  - show_fault_paths=false unless user asks for fault paths.

"Detailed":
  - Default set: supply, maincb, rcd, bus, nbar, ebar, loads.
  - Always include defaults PLUS every component the user names.
  - For each named circuit add a separate outcb_N with a descriptive label.
  - show_neutral=true, show_earth=true, show_rcd=true, show_fault_paths=true, show_protection_notes=true.

=== EXPLICIT EXCLUSIONS — ALWAYS OVERRIDE COMPLEXITY ===
If the user says "no RCD", "no fault path", "no neutral", "no earth", "simple breaker only":
  Remove that component and set its flag to false. This overrides everything above.
  User prompt is the ultimate source of truth.

=== INFERENCE RULES ===
1. Voltage: extract from prompt. Format: "230V AC" or "415V AC". Default: "unspecified".
2. Language: Japanese text (hiragana/katakana/kanji) -> "ja". Otherwise -> "en".
3. supply label must include voltage. Example: "Main Supply (230V AC)".
4. rcd / rcbo label: use whatever the user names it. If user doesn't name it, use "RCD (Earth Fault Protection)".
5. outcb_N: If the user names distinct circuits OR specifies a quantity of loads, circuits, or breakers (e.g. "three loads", "3 circuits", "4 motors"), generate N outgoing branch breakers (outcb_1..outcb_N) with corresponding labels (e.g. "Load 1", "Load 2", "Load 3" or "Motor 1", "Motor 2", "Motor 3"). Max 15.
6. "standard distribution panel" with no detail at Standard/Detailed complexity -> include full default set.
7. The supply and load should always be present unless user explicitly says "no loads", "direct connection", or "no supply".
"""

    def _call_ollama(self, prompt: str, format_schema=None, num_predict=1024) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
                "num_predict": num_predict,
                "num_ctx": 8192,
            }
        }
        if format_schema is not None:
            payload["format"] = format_schema

        response = requests.post(self.url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("response", "").strip()

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        """Plain text chat via Ollama /api/chat endpoint."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens,
                "num_ctx": 8192,
            },
        }
        chat_url = self.url.replace("/api/generate", "/api/chat")
        response = requests.post(chat_url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()

    # ── Stage 1: Identification ──────────────────────────────────────────────
    def _stage1_identify(self, prompt: str, complexity: str) -> dict:
        schema = {
            "type": "object",
            "properties": {
                "mentioned_components": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "named_circuits": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "explicit_exclusions": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["mentioned_components", "named_circuits", "explicit_exclusions"]
        }

        sys_prompt = f"""You are extracting raw facts from an electrical diagram request. Do NOT apply complexity rules yet — just extract what is literally stated.

{self.COMPONENT_MEANINGS}

List:
- mentioned_components: component IDs the user explicitly names or clearly implies
- named_circuits: distinct outgoing circuit names the user lists (e.g. "lighting", "sockets")
- explicit_exclusions: anything the user says NOT to include (e.g. "no RCD", "no earth")

Complexity level in effect: {complexity}
"""
        raw = self._call_ollama(f"{sys_prompt}\n\nUSER PROMPT:\n{prompt}\n\nJSON:", format_schema=schema, num_predict=256)
        result = self._extract_json(raw)
        return result or {"mentioned_components": [], "named_circuits": [], "explicit_exclusions": []}

    # ── Stage 2: Chain-of-thought reasoning ──────────────────────────────────
    def _stage2_reason(self, prompt: str, complexity: str, stage1: dict) -> str:
        sys_prompt = f"""You are reasoning step-by-step about how to build an electrical diagram's structured data. Do NOT output JSON yet — write plain reasoning.

{self.COMPONENT_MEANINGS}
{self.COMPLEXITY_RULES}

Extracted facts from the prompt (Stage 1):
- Mentioned components: {stage1['mentioned_components']}
- Named circuits: {stage1['named_circuits']}
- Explicit exclusions: {stage1['explicit_exclusions']}

Complexity level in effect: {complexity}

        Walk through, in order:
        1. Final component list — apply the complexity level's rules to the mentioned components, then apply explicit exclusions LAST (they always win, regardless of complexity).
        2. Each flag (show_neutral, show_earth, show_rcd, show_protection_notes, show_fault_paths) — state true/false and cite which rule justifies it.
        3. Voltage — quote what you found in the prompt, or "unspecified".
        4. Language — "en" or "ja", based on whether the prompt contains Japanese text.
        5. Phase Hint — "three-phase" if the user explicitly requests three-phase, "single-phase" if the user explicitly requests single-phase, or "null" if not explicitly mentioned.
        6. Label wording for each component (per the inference rules).
        
        Be explicit and check your work against the EXPLICIT EXCLUSIONS rule before finishing — it overrides complexity defaults.
"""
        return self._call_ollama(f"{sys_prompt}\n\nUSER PROMPT:\n{prompt}\n\nREASONING:", format_schema=None, num_predict=768)

    # ── Stage 3: Final structured assembly ───────────────────────────────────
    def _stage3_assemble(self, prompt: str, reasoning: str) -> dict:
        sys_prompt = f"""Convert the reasoning below into the final structured JSON. Follow the reasoning's conclusions exactly — do not re-derive or second-guess them.

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
{reasoning}
"""
        raw = self._call_ollama(f"{sys_prompt}\n\nORIGINAL PROMPT:\n{prompt}\n\nJSON:", format_schema=STRUCTURED_SCHEMA, num_predict=1024)
        result = self._extract_json(raw)
        if result is None:
            raise ValueError(f"Invalid or missing JSON output:\n{raw[:500]}")
        return result

    # ── Public entry point — implements LLMClientBase ────────────────────────
    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        print(f"[stage 1] identifying components | model={self.model}")
        stage1 = self._stage1_identify(prompt, complexity)

        print(f"[stage 2] reasoning | model={self.model}")
        reasoning = self._stage2_reason(prompt, complexity, stage1)

        print(f"[stage 3] assembling JSON | model={self.model}")
        return self._stage3_assemble(prompt, reasoning)

    def _extract_json(self, text: str) -> dict | None:
        """Try to extract and parse a JSON object from text. Returns dict or None."""
        text = text.strip()
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first { ... last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None
        

class GenerationWorker(QThread):
    """Runs the blocking LLM call (whichever backend and model is configured) on a
    background thread."""
    finished = Signal(dict)       # emits parsed_data on success
    failed   = Signal(str)        # emits error message on failure

    def __init__(self, prompt: str, complexity: str, generator, model_choice: str = "Groq \u2014 Fast (Cloud)"):
        super().__init__()
        self.prompt       = prompt
        self.complexity   = complexity
        self.generator    = generator   # MermaidGenerator instance (thread-safe reads only)
        self.model_choice = model_choice

    def run(self):
        try:
            try:
                from ECD.llm.llm_factory import get_llm_client
            except ImportError:
                from llm_factory import get_llm_client

            client      = get_llm_client(self.model_choice)
            parsed_data = client.prompt_to_structured_data(self.prompt, self.complexity)

            if not isinstance(parsed_data, dict) or "components" not in parsed_data:
                raise ValueError("Invalid LLM output — missing components key")

            # Resolve phase mode and inject into parsed_data
            try:
                from ECD.pin_model import determine_phase_mode
            except ImportError:
                from pin_model import determine_phase_mode
            
            voltage = parsed_data.get("voltage", "")
            phase_hint = parsed_data.get("phase_hint")
            parsed_data["phase_mode"] = determine_phase_mode(voltage, phase_hint)

            # Normalise components to (id, label) tuples — schema now returns
            # objects ({"id":..., "label":...}) rather than 2-element arrays,
            # since object shape compiles more reliably to structured-output
            # constraints across backends (Ollama grammar, Groq/Gemini JSON
            # schema) than tuple-style arrays.
            def _to_tuple(c):
                if isinstance(c, dict) and "id" in c and "label" in c:
                    return (c["id"], c["label"])
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    return (c[0], c[1])
                return (str(c), str(c))

            parsed_data["components"] = [_to_tuple(c) for c in parsed_data["components"]]
            self.finished.emit(parsed_data)

        except Exception as e:
            self.failed.emit(str(e))
