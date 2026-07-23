"""
ECD/llm/base_client.py
=======================
Abstract interface that every LLM backend (Ollama, Groq, Gemini, etc.) must
implement, so GenerationWorker can swap backends without knowing anything
about the underlying provider.
"""

from abc import ABC, abstractmethod


class LLMClientBase(ABC):
    @abstractmethod
    def prompt_to_structured_data(self, prompt: str, complexity: str = "Neutral") -> dict:
        """
        Must return a dict with this exact shape (matching STRUCTURED_SCHEMA):
            {
                "components": [(id, label), ...],   # list of 2-tuples
                "flags": {
                    "show_neutral": bool, "show_earth": bool, "show_rcd": bool,
                    "show_protection_notes": bool, "show_fault_paths": bool
                },
                "voltage": str,
                "language": "en" | "ja",
                "phase_hint": "single-phase" | "three-phase" | None
            }
        """
        raise NotImplementedError

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
        """
        Plain text chat completion — no JSON schema, no structured output.
        Used by ValidationWorker (semantic validation) and MermaidFixWorker (diagram repair).
        Returns the model's raw text response as a string.
        """
        raise NotImplementedError
