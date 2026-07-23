"""
ECD/llm/llm_factory.py
=======================
Single place to switch which LLM backend and model the app uses.
Supported UI choices:
- "Groq (Fast)"  -> GroqClient(model="openai/gpt-oss-20b")  [Default]
- "Groq (Large)" -> GroqClient(model="openai/gpt-oss-120b")
- "Gemini"       -> GeminiClient(model="gemini-3.5-flash")
- "Mistral"      -> OllamaClient(model="mistral:7b-instruct")
- "Qwen (Local)" -> OllamaClient(model="qwen2.5:7b-instruct")
"""

import os

MODEL_CONFIGS = {
    # New sidebar labels
    "Groq - Fast (Limited Daily Use)":                  ("groq",   "openai/gpt-oss-20b"),
    "Groq - Large (Higher Quality, Limited Daily Use)": ("groq",   "openai/gpt-oss-120b"),
    "Gemini (Limited)":                                 ("gemini", "gemini-3.5-flash"),
    "Mistral (Unlimited, Offline)":                     ("ollama", "mistral:7b-instruct"),
    "Qwen (Unlimited, Offline)":                        ("ollama", "qwen2.5:7b-instruct"),

    # Legacy aliases for backwards compatibility
    "Groq — Fast (Cloud)":                             ("groq",   "openai/gpt-oss-20b"),
    "Groq — Large (Cloud, Higher Quality)":            ("groq",   "openai/gpt-oss-120b"),
    "Gemini (Cloud)":                                  ("gemini", "gemini-3.5-flash"),
    "Mistral (Local, Offline)":                         ("ollama", "mistral:7b-instruct"),
    "Qwen (Local, Offline)":                            ("ollama", "qwen2.5:7b-instruct"),
}

LLM_BACKEND = os.environ.get("ECD_LLM_BACKEND", "groq")


def get_llm_client(model_choice: str | None = None):
    """
    Instantiates and returns an LLM client dynamically based on model_choice.
    If model_choice is not provided or recognized, falls back to ECD_LLM_BACKEND or Groq (Fast).
    """
    if model_choice and model_choice in MODEL_CONFIGS:
        backend, model_name = MODEL_CONFIGS[model_choice]
    else:
        env_backend = (os.environ.get("ECD_LLM_BACKEND") or "groq").lower()
        if env_backend == "gemini":
            backend, model_name = "gemini", "gemini-3.5-flash"
        elif env_backend == "ollama":
            backend, model_name = "ollama", "qwen2.5:7b-instruct"
        else:
            backend, model_name = "groq", "openai/gpt-oss-20b"

    print(f"[llm_factory] Instantiating client: choice='{model_choice}' -> backend='{backend}', model='{model_name}'")

    if backend == "groq":
        try:
            from ECD.llm.groq_client import GroqClient
        except ImportError:
            from groq_client import GroqClient
        return GroqClient(model=model_name)

    if backend == "gemini":
        try:
            from ECD.llm.gemini_client import GeminiClient
        except ImportError:
            from gemini_client import GeminiClient
        return GeminiClient(model=model_name)

    # Ollama backend
    try:
        from ECD.llm.ollama_client import OllamaClient
    except ImportError:
        from ollama_client import OllamaClient
    return OllamaClient(model=model_name)

