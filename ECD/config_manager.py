"""
ECD/config_manager.py
=====================
3-Layer configuration manager for electrical diagram generator.
Maintains hierarchy: Defaults -> .env (immutable dev/deploy file) -> %AppData%\\ECD\\config.json (user overrides).
"""

import os
import json
from dotenv import dotenv_values

try:
    from ECD.settings_page import HAS_BUNDLED_DEFAULTS
except ImportError:
    from settings_page import HAS_BUNDLED_DEFAULTS

BACKEND_DISPLAY_MAP = {
    "groq_fast":  "Groq - Fast (Limited Daily Use)",
    "groq_large": "Groq - Large (Higher Quality, Limited Daily Use)",
    "gemini":     "Gemini (Limited)",
    "mistral":    "Mistral (Unlimited, Offline)",
    "qwen":       "Qwen (Unlimited, Offline)",
}

DISPLAY_TO_BACKEND_MAP = {v: k for k, v in BACKEND_DISPLAY_MAP.items()}


def get_app_dir() -> str:
    """Returns the application directory path."""
    return os.path.dirname(os.path.abspath(__file__))


def get_user_config_path() -> str:
    """Returns absolute path to user configuration file in %AppData%\\ECD\\config.json."""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    ecd_dir = os.path.join(appdata, "ECD")
    os.makedirs(ecd_dir, exist_ok=True)
    return os.path.join(ecd_dir, "config.json")


class ConfigManager:
    """Manages application configuration, credentials, and user preferences."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config_data = {}
        self.load_config()

    def load_config(self):
        """Loads configuration in 3 layers: Hardcoded Defaults -> .env -> config.json."""
        # 1. Layer 1: Hardcoded Defaults
        self.config_data = {
            "ai": {
                "backend": "groq_fast",
                "groq_api_key": "",
                "gemini_api_key": "",
                "ollama_url": "http://localhost:11434"
            }
        }

        if HAS_BUNDLED_DEFAULTS:
            self._load_bundled_defaults()

        # 2. Layer 2: Read .env from app_dir (dev/deployment environment)
        app_dir = get_app_dir()
        env_paths = [
            os.path.join(app_dir, ".env"),
            os.path.join(os.path.dirname(app_dir), ".env")
        ]
        env_values = {}
        for ep in env_paths:
            if os.path.isfile(ep):
                try:
                    env_values.update(dotenv_values(ep))
                except Exception:
                    pass

        if env_values:
            if env_values.get("GROQ_API_KEY"):
                self.config_data["ai"]["groq_api_key"] = env_values["GROQ_API_KEY"].strip()
            if env_values.get("GEMINI_API_KEY"):
                self.config_data["ai"]["gemini_api_key"] = env_values["GEMINI_API_KEY"].strip()
            if env_values.get("OLLAMA_URL"):
                self.config_data["ai"]["ollama_url"] = env_values["OLLAMA_URL"].strip()

            env_backend = env_values.get("ECD_LLM_BACKEND") or env_values.get("LLM_BACKEND")
            if env_backend:
                b_norm = self.normalize_backend_id(env_backend)
                if b_norm:
                    self.config_data["ai"]["backend"] = b_norm

        # 3. Layer 3: User Overrides from %AppData%\ECD\config.json
        user_config_file = get_user_config_path()
        if os.path.isfile(user_config_file):
            try:
                with open(user_config_file, "r", encoding="utf-8") as f:
                    user_json = json.load(f)

                if isinstance(user_json, dict) and "ai" in user_json:
                    ai_sec = user_json["ai"]
                    if isinstance(ai_sec, dict):
                        b_id = ai_sec.get("backend")
                        b_norm = self.normalize_backend_id(b_id)
                        if b_norm:
                            self.config_data["ai"]["backend"] = b_norm
                        if "groq_api_key" in ai_sec:
                            self.config_data["ai"]["groq_api_key"] = str(ai_sec["groq_api_key"]).strip()
                        if "gemini_api_key" in ai_sec:
                            self.config_data["ai"]["gemini_api_key"] = str(ai_sec["gemini_api_key"]).strip()
                        if "ollama_url" in ai_sec:
                            self.config_data["ai"]["ollama_url"] = str(ai_sec["ollama_url"]).strip()
            except Exception as e:
                print(f"[ConfigManager] Error reading {user_config_file}: {e}")
        # Sync loaded API keys into os.environ for client instantiation
        if self.config_data["ai"].get("groq_api_key"):
            os.environ["GROQ_API_KEY"] = self.config_data["ai"]["groq_api_key"]
        if self.config_data["ai"].get("gemini_api_key"):
            os.environ["GEMINI_API_KEY"] = self.config_data["ai"]["gemini_api_key"]
        if self.config_data["ai"].get("ollama_url"):
            os.environ["OLLAMA_URL"] = self.config_data["ai"]["ollama_url"]

    def _load_bundled_defaults(self):
        """Loads developer convenience bundled defaults if HAS_BUNDLED_DEFAULTS is True."""
        app_dir = get_app_dir()
        env_file = os.path.join(app_dir, ".env")
        if not os.path.isfile(env_file):
            env_file = os.path.join(os.path.dirname(app_dir), ".env")
        if os.path.isfile(env_file):
            vals = dotenv_values(env_file)
            if vals.get("GROQ_API_KEY"):
                self.config_data["ai"]["groq_api_key"] = vals["GROQ_API_KEY"].strip()
            if vals.get("GEMINI_API_KEY"):
                self.config_data["ai"]["gemini_api_key"] = vals["GEMINI_API_KEY"].strip()

    def normalize_backend_id(self, backend_val: str) -> str | None:
        """Normalizes any input backend representation (stable ID or display string) to a stable internal ID."""
        if not backend_val:
            return None
        if backend_val in DISPLAY_TO_BACKEND_MAP:
            return DISPLAY_TO_BACKEND_MAP[backend_val]
        if backend_val in BACKEND_DISPLAY_MAP:
            return backend_val
        b_lower = str(backend_val).lower()
        if "groq_large" in b_lower or "large" in b_lower:
            return "groq_large"
        if "groq" in b_lower:
            return "groq_fast"
        if "gemini" in b_lower:
            return "gemini"
        if "mistral" in b_lower:
            return "mistral"
        if "qwen" in b_lower or "ollama" in b_lower:
            return "qwen"
        return None

    # ── Provider-Agnostic Accessors (for llm_factory.py & application) ──

    def current_backend(self) -> str:
        """Returns the stable internal ID of the active backend (e.g. 'groq_fast')."""
        return self.config_data["ai"].get("backend", "groq_fast")

    def current_display_name(self) -> str:
        """Returns the UI display string for the active backend."""
        b_id = self.current_backend()
        return BACKEND_DISPLAY_MAP.get(b_id, "Groq - Fast (Limited Daily Use)")

    def current_credentials(self) -> dict:
        """Returns credentials required by the currently active backend."""
        b_id = self.current_backend()
        ai = self.config_data["ai"]
        if b_id in ("groq_fast", "groq_large"):
            return {"api_key": ai.get("groq_api_key", ""), "model": "openai/gpt-oss-20b" if b_id == "groq_fast" else "openai/gpt-oss-120b"}
        elif b_id == "gemini":
            return {"api_key": ai.get("gemini_api_key", ""), "model": "gemini-3.5-flash"}
        elif b_id in ("mistral", "qwen"):
            model_name = "mistral:7b-instruct" if b_id == "mistral" else "qwen2.5:7b-instruct"
            return {"url": ai.get("ollama_url", "http://localhost:11434"), "model": model_name}
        return {}

    # ── Per-Provider Getters (for Settings UI) ──

    def backend(self) -> str:
        return self.current_backend()

    def groq_key(self) -> str:
        return self.config_data["ai"].get("groq_api_key", "")

    def gemini_key(self) -> str:
        return self.config_data["ai"].get("gemini_api_key", "")

    def ollama_url(self) -> str:
        return self.config_data["ai"].get("ollama_url", "http://localhost:11434")

    # ── Validation & Persistence ──

    def save_config(self, form_data: dict) -> tuple[bool, str]:
        """Validates and persists partial form updates to %AppData%\\ECD\\config.json."""
        ai = self.config_data["ai"]

        if "backend" in form_data:
            b_norm = self.normalize_backend_id(form_data["backend"])
            if b_norm:
                ai["backend"] = b_norm

        if "groq_api_key" in form_data:
            ai["groq_api_key"] = str(form_data["groq_api_key"]).strip()
        if "gemini_api_key" in form_data:
            ai["gemini_api_key"] = str(form_data["gemini_api_key"]).strip()
        if "ollama_url" in form_data:
            ai["ollama_url"] = str(form_data["ollama_url"]).strip()

        return self.save_config_to_disk()

    def save_config_to_disk(self) -> tuple[bool, str]:
        """Writes current config_data to %AppData%\\ECD\\config.json."""
        try:
            config_file = get_user_config_path()
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
            return True, ""
        except Exception as e:
            return False, str(e)

    def restore_defaults(self):
        """Clears user config overrides and reloads defaults from .env."""
        user_config_file = get_user_config_path()
        if os.path.isfile(user_config_file):
            try:
                os.remove(user_config_file)
            except Exception:
                pass
        self.load_config()


def get_config() -> ConfigManager:
    """Returns singleton ConfigManager instance."""
    return ConfigManager()
