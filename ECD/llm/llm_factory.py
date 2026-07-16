"""
ECD/llm/llm_factory.py
=======================
Single place to switch which LLM backend the app uses.
Set ECD_LLM_BACKEND to "ollama" (default, offline, shipping path),
"groq", or "gemini" (cloud, for dev/testing speed and quality comparisons).
"""

import os

LLM_BACKEND = os.environ.get("ECD_LLM_BACKEND", "ollama")  # "ollama" | "groq" | "gemini"


def get_llm_client():
    if LLM_BACKEND == "groq":
        try:
            from ECD.llm.groq_client import GroqClient
        except ImportError:
            from groq_client import GroqClient
        return GroqClient()

    if LLM_BACKEND == "gemini":
        try:
            from ECD.llm.gemini_client import GeminiClient
        except ImportError:
            from gemini_client import GeminiClient
        return GeminiClient()

    # Default: offline local Ollama path -- unchanged, no behavior difference.
    try:
        from ECD.llm.ollama_client import OllamaClient
    except ImportError:
        from ollama_client import OllamaClient
    return OllamaClient()
