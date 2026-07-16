import os
import requests
from dotenv import load_dotenv

load_dotenv()

STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["id", "label"],
                "additionalProperties": False,
            },
        },
        "flags": {
            "type": "object",
            "properties": {
                "show_neutral": {"type": "boolean"},
                "show_earth": {"type": "boolean"},
                "show_rcd": {"type": "boolean"},
                "show_protection_notes": {"type": "boolean"},
                "show_fault_paths": {"type": "boolean"},
            },
            "required": ["show_neutral", "show_earth", "show_rcd",
                         "show_protection_notes", "show_fault_paths"],
            "additionalProperties": False,
        },
        "voltage": {"type": "string"},
        "language": {"type": "string", "enum": ["en", "ja"]},
        "phase_hint": {
            "type": ["string", "null"],
            "enum": ["single-phase", "three-phase", None],
        },
    },
    "required": ["components", "flags", "voltage", "language", "phase_hint"],
    "additionalProperties": False,
}

api_key = os.environ.get("GROQ_API_KEY")

resp = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": "Generate a simple 230V panel with a main breaker and one load."}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "diagram_schema", "schema": STRUCTURED_SCHEMA, "strict": True},
        },
    },
)

print("Status:", resp.status_code)
print("Body:", resp.text)