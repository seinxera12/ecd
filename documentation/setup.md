# ECD Developer Onboarding Guide

---

## Prerequisites

### Operating System

- **Windows 10/11** — primary and tested platform.
- Linux / macOS should work but are untested.

### Language & Runtime

- **Python 3.10+** (3.11 recommended — this is what it has been developed and tested on)
- **pip**

### Tools

- **Git**
- **Code editor** — VS Code with the Python extension works well

### Hardware

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB (needed for local Ollama models) |
| Storage | 5 GB | 15 GB (Ollama model weights are large) |
| CPU | Any modern multi-core | — |
| GPU | Not required | Speeds up Ollama inference significantly |

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd ecd
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

> The project uses `.venv` as the virtual environment folder. If you see `venv/` in the directory, that is an old artifact — use `.venv`.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages installed:

| Package | Purpose |
|---------|---------|
| `PySide6` | Qt 6 GUI framework |
| `ezdxf` | DXF CAD file generation |
| `requests` | HTTP calls to LLM APIs |
| `pillow` | Image export (PNG) |
| `matplotlib` | PDF/PNG rendering backend |
| `python-dotenv` | `.env` file loading |
| `groq` | Groq Cloud API client |
| `google-genai` | Google Gemini API client |
| `pyinstaller` | Standalone `.exe` packaging |

### Step 4: Configure API Keys

Create a `.env` file in the project root:

```
# .env — place at ecd/ (project root)

GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# QFind (only needed if you use the QFind custom model)
QFIND_API_KEY=your_qfind_api_key_here
QFIND_URL=https://ubuntu.tailcd8da4.ts.net

# Optional: sets the default backend before the app loads
ECD_LLM_BACKEND=groq
```

**Get API keys from:**
- Groq: https://console.groq.com/keys (free tier available)
- Gemini: https://aistudio.google.com/app/apikey (free tier available)
- QFind: Contact the internal team — this is a self-hosted model endpoint

> **You can also change API keys from inside the app** — see the Settings page section below. This is the easier approach for day-to-day use.

### Step 5: (Optional) Install Ollama for Offline Models

Ollama is only needed if you want to run the **Mistral** or **Qwen** offline models. The cloud models (Groq, Gemini, QFind) work without it.

1. Download from https://ollama.ai and install
2. Pull the models you want:
   ```bash
   ollama pull mistral:7b-instruct
   ollama pull qwen2.5:7b-instruct
   ```
3. Ollama starts automatically as a service. If it doesn't:
   ```bash
   ollama serve
   # Runs at http://localhost:11434
   ```

### Step 6: Verify Installation

```bash
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
python -c "import ezdxf; print('ezdxf OK')"
python -c "from ECD.electrical.erc import run_erc; print('ERC Engine OK')"
python -c "from ECD.llm.llm_factory import get_llm_client; print('LLM Factory OK')"
```

---

## Running the Application

**Always run from the project root directory** using Python's `-m` module notation. This ensures package imports resolve correctly.

```bash
# Launch the main GUI
python -m ECD.main_app
```

### What you should see on startup

1. A window opens (~1400×900 px)
2. Sidebar on the left with:
   - Text input area for prompts
   - **Model** dropdown (Groq, Gemini, Mistral, Qwen, QFind)
   - **Detail Level** dropdown (Simple, Neutral, Standard, Detailed)
   - Template buttons
   - Generate / Reset buttons
3. Canvas area in the center showing a welcome screen
4. Status bar at the bottom showing "Ready"

---

## Model Selection

Models are selected from the **sidebar dropdown** in the UI. No environment variable changes or restarts are needed.

| UI Label | Backend | Model | Notes |
|----------|---------|-------|-------|
| Groq - Fast (Limited Daily Use) | Groq Cloud | `openai/gpt-oss-20b` | Fast, good quality. Has daily quota. |
| Groq - Large (Higher Quality, Limited Daily Use) | Groq Cloud | `openai/gpt-oss-120b` | Better for complex diagrams. Lower daily quota. |
| Gemini (Limited) | Google AI Studio | `gemini-3.5-flash` | Free tier. Has daily quota. |
| Mistral (Unlimited, Offline) | Local Ollama | `mistral:7b-instruct` | Requires Ollama running locally. No quota. |
| Qwen (Unlimited, Offline) | Local Ollama | `qwen2.5:7b-instruct` | Requires Ollama running locally. Best local quality. |
| QFind (Custom Model) | Self-hosted endpoint | `qfind-chat` | Internal custom model. Requires `QFIND_URL` and optionally `QFIND_API_KEY`. |

### Automatic Regex Fallback

If a cloud API call fails (rate limit, network timeout, quota exhausted), the app automatically falls back to the **local deterministic regex parser**. This produces a basic diagram without an LLM. A yellow warning banner appears in the validation panel when this happens:

> ⚠️ `[FALLBACK WARNING] The diagram was generated using the local regex fallback parser because the LLM was unavailable.`

---

## Changing API Keys (Settings Page)

The easiest way to update API keys is through the **Settings page** in the UI. Open it from the menu (`File → Settings` or the gear icon).

From the Settings page you can:
- Set/update `GROQ_API_KEY`, `GEMINI_API_KEY`, `QFIND_API_KEY`, `QFIND_URL`
- Changes are saved directly to the `.env` file at the project root via `ECD/config_manager.py`

**For advanced / scripted configuration**, edit the `.env` file directly or set environment variables in your terminal session:

```powershell
# Windows PowerShell (session only)
$env:GROQ_API_KEY = "gsk_..."
$env:ECD_LLM_BACKEND = "groq"
```

```cmd
# Windows Command Prompt (session only)
set GROQ_API_KEY=gsk_...
```

```cmd
# Persistent (all future sessions)
setx GROQ_API_KEY "gsk_..."
```

> The app reads `.env` on startup via `python-dotenv`. Terminal environment variables take precedence over `.env`.

---

## Interactive Canvas Controls & Shortcuts

The diagram canvas supports interactive drag-and-drop editing, inline text modification, multi-selection, and full undo/redo history.

| Action | Shortcut / Gesture | Description |
|--------|-------------------|-------------|
| **Reposition Symbol** | `Left-click + Drag` | Moves the selected component symbol; connecting wires recalculate live. |
| **Edit Label Text** | `Double-click` | Opens inline text editor on component descriptions, ratings, or voltage text. |
| **Multi-Select** | `Shift + Click` or `Rubberband Drag` | Selects multiple components to move an entire circuit branch together. |
| **Undo** | `Ctrl + Z` | Reverts the last move, label edit, or layout adjustment. |
| **Redo** | `Ctrl + Y` or `Ctrl + Shift + Z` | Reapplies the previously undone action. |
| **Zoom In / Out** | `Mouse Wheel` or Zoom Slider | Scales the canvas view from 20% to 500%. |
| **Pan Canvas** | `Middle-click + Drag` or Spacebar | Panning across large multi-circuit diagrams. |
| **Reset Layout** | "Reset Layout" Button | Restores all component positions back to default pin-model layout. |
| **Save Diagram Project** | `File → Save Diagram (.json)` | Saves the complete diagram state with all position overrides. |
| **Open Diagram Project** | `File → Open Diagram (.json)` | Reopens a previously saved `.json` diagram project. |
| **Export Formats** | `File → Export → ...` | Export to DXF (CAD), KiCad (.kicad_sch), PNG, SVG, PDF, or Mermaid. |

---

## Running the Test Suite

The project has an automated unit test suite covering ERC rules, netlist validation, DXF generation, LLM client factory, and QFind pipeline stages.

```bash
# Run all tests
python -m unittest discover tests
```

Expected output on a clean run:

```
...............................................
----------------------------------------------------------------------
Ran 47 tests in ~4s

OK
```

> The `RuntimeError: Signal source has been deleted` lines that appear after `OK` are PySide6 cleanup warnings from the Qt event loop during testing. They are benign and do not indicate test failures.

**Always run the test suite** before committing, especially after changes to:
- `ECD/electrical/erc.py`
- `ECD/electrical/pin_model.py`
- `ECD/cad/dxf_generator.py`
- `ECD/canvas/diagram_canvas.py`
- `ECD/llm/` (any client file)

---

## Project Structure

```
ecd/
├── ECD/                            # Main application package
│   ├── main_app.py                 # Application entry point + MainWindow
│   ├── sidebar.py                  # Left panel: prompt input, model selector, templates
│   ├── settings_page.py            # Settings UI: API key management
│   ├── config_manager.py           # Reads/writes API keys to .env
│   ├── mermaid_generator.py        # Mermaid diagram code generator + regex fallback parser
│   ├── ValidationWorker.py         # Async ERC validation + auto-fix workers + ValidationPanel UI
│   ├── constants.py                # Complexity level definitions and shared constants
│   │
│   │   # The following are stub files that re-export from sub-packages.
│   │   # Edit the sub-package files, not these.
│   ├── diagram_canvas.py           # Stub → ECD/canvas/diagram_canvas.py
│   ├── erc.py                      # Stub → ECD/electrical/erc.py
│   ├── pin_model.py                # Stub → ECD/electrical/pin_model.py
│   ├── dxf_generator.py            # Stub → ECD/cad/dxf_generator.py
│   ├── symbols.py                  # Stub → ECD/cad/symbols.py
│   ├── Kicad_exporter.py           # Stub → ECD/cad/Kicad_exporter.py
│   ├── undo_manager.py             # Stub → ECD/canvas/undo_manager.py
│   │
│   ├── canvas/                     # Diagram canvas sub-package
│   │   ├── diagram_canvas.py       # Core rendering widget (QGraphicsScene + QWebEngineView)
│   │   ├── symbol_item.py          # Draggable electrical symbol graphics items
│   │   ├── text_item.py            # Editable text label graphics items
│   │   ├── commands.py             # Qt undo/redo command objects
│   │   ├── undo_manager.py         # Undo stack manager
│   │   └── selection_manager.py    # Multi-select and group operations
│   │
│   ├── cad/                        # CAD export sub-package
│   │   ├── dxf_generator.py        # DXF export engine (ezdxf, IEC symbols, wire routing)
│   │   ├── symbols.py              # ezdxf IEC symbol block library
│   │   ├── Kicad_exporter.py       # KiCad 6+ schematic export
│   │   ├── layout_sections.py      # Layout section helpers for DXF
│   │   └── renderers.py            # PNG/SVG rendering helpers
│   │
│   ├── electrical/                 # Electrical rule engine sub-package
│   │   ├── erc.py                  # 10-rule deterministic ERC engine (ERC-001..ERC-010)
│   │   ├── pin_model.py            # Pin terminal maps, netlist builder, DFS wire tracer
│   │   └── wire_router.py          # Wire routing geometry
│   │
│   ├── llm/                        # LLM client sub-package
│   │   ├── base_client.py          # Abstract LLMClientBase interface
│   │   ├── llm_factory.py          # Factory: maps model name → client instance
│   │   ├── ollama_client.py        # Local Ollama client (3-stage CoT pipeline)
│   │   ├── groq_client.py          # Groq Cloud client
│   │   ├── gemini_client.py        # Google Gemini client
│   │   └── qfind_client.py         # QFind custom model client (3-stage CoT pipeline)
│   │
│   └── assets/
│       └── symbols/                # IEC SVG symbol assets
│
├── tests/                          # Automated unit test suite (47 tests)
├── documentation/                  # This documentation
├── ECD.spec                        # PyInstaller build specification
├── requirements.txt                # Python dependencies
└── .env                            # API keys (not committed to git)
```

> **Note on stubs:** After the refactor, several files in `ECD/` root (e.g., `ECD/erc.py`) are single-line stubs. The real implementations live in the sub-packages. Always edit the sub-package files, not the stubs.

---

## Build Process (Standalone Executable)

```bash
# Install PyInstaller (if not already in requirements.txt)
pip install pyinstaller

# Build standalone executable
pyinstaller ECD.spec --noconfirm
```

**Output:**
- `dist/ECD/ECD.exe` — standalone Windows executable
- `dist/ECD/` — full distribution folder (copy everything in this folder)

**Before distributing to an end user:**
1. Copy a `.env` file with their API keys alongside `ECD.exe`:
   ```
   dist/ECD/
   ├── ECD.exe
   └── .env        ← place API keys here
   ```
2. The app resolves `.env` relative to the executable when frozen.

**Spec highlights (`ECD.spec`):**
- Entry point: `ECD/main_app.py`
- Bundles: `ECD/assets/symbols/*.svg`
- Hidden imports: `ezdxf`, `matplotlib` backends, `PySide6.QtSvg`, `groq`, `google.genai`, `PIL`, `dotenv`

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'PySide6'`

```bash
pip install PySide6
```

### `ModuleNotFoundError: No module named 'ECD'`

You are not running from the project root, or the virtual environment is not activated.

```bash
cd ecd
.venv\Scripts\activate
python -m ECD.main_app
```

### `Connection refused` / Ollama errors

Ollama is not running. Start it:

```bash
ollama serve
```

Or verify it is running:

```bash
curl http://localhost:11434
```

### `model 'mistral:7b-instruct' not found`

```bash
ollama pull mistral:7b-instruct
```

### Groq / Gemini `401 Unauthorized`

API key is missing or wrong. Set it in the **Settings page** in the app, or update your `.env` file:

```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AI...
```

### Groq / Gemini `429 Too Many Requests`

You have hit the free-tier daily rate limit. The app will automatically fall back to the local regex parser. Either:
- Wait until the daily quota resets, or
- Switch to an offline model (Mistral or Qwen) in the sidebar dropdown

### WebEngine / Blank Canvas

Missing WebEngine components:

```bash
pip install PySide6-WebEngine
```

Or try disabling hardware acceleration:

```powershell
$env:QT_QUICK_BACKEND = "software"
python -m ECD.main_app
```

### Tests Failing

```bash
python -m unittest discover tests -v
```

Run with `-v` for verbose output to see exactly which test is failing and why.

---

## Development Workflow

### Day-to-Day

```bash
# 1. Activate environment
.venv\Scripts\activate

# 2. Run the app
python -m ECD.main_app

# 3. Make your changes

# 4. Run tests before committing
python -m unittest discover tests

# 5. Commit
git add .
git commit -m "feat: description of what changed"
```

### Adding a New LLM Backend

1. Create `ECD/llm/your_client.py` extending `LLMClientBase`
2. Implement `prompt_to_structured_data(prompt, complexity) -> dict`
3. Implement `chat(system_prompt, user_prompt) -> str`
4. Add an entry to `MODEL_CONFIGS` in `ECD/llm/llm_factory.py`
5. Add instantiation block (`if backend == "your_backend"`) in `get_llm_client()`
6. Add display label to `self.model_combo.addItems([...])` in `ECD/sidebar.py`
7. Add a unit test in `tests/test_your_client.py`

### Adding a New ERC Rule

1. Open `ECD/electrical/erc.py`
2. Add a `_check_erc_NNN()` method following the existing pattern
3. Register it in `run_erc()` at the bottom of the file
4. Add test cases to `tests/test_erc_rules.py`

### Adding a New Export Format

1. Create `ECD/cad/your_exporter.py`
2. Implement `export_your_format(parsed_data, output_path)`
3. Add a menu item in `ECD/main_app.py` → `_build_menu()`
4. Connect the menu action to your export function

### Code Style

- Follow PEP 8
- Add docstrings to public functions and classes
- Match the existing print-based debug logging style: `print(f"[module] message")`

---

## Key Concepts for New Developers

### The `parsed_data` Dict

This is the central data structure flowing through the entire app. Produced by the LLM client and consumed by the Mermaid generator, DXF generator, ERC engine, and KiCad exporter.

```python
parsed_data = {
    "components": [
        {"id": "supply",   "label": "Main Supply (230V AC)"},
        {"id": "maincb",   "label": "100A Main Breaker"},
        {"id": "rcd",      "label": "RCD (Earth Fault Protection)"},
        {"id": "bus",      "label": "Copper Busbar"},
        {"id": "nbar",     "label": "Neutral Bar"},
        {"id": "ebar",     "label": "Earth Bar"},
        {"id": "outcb_1",  "label": "5.5kW Induction Motor"},
        {"id": "outcb_2",  "label": "7.5kW Pump Motor"},
        {"id": "outcb_3",  "label": "3kW HVAC Load"},
    ],
    "flags": {
        "show_neutral": True,
        "show_earth": True,
        "show_rcd": True,
        "show_protection_notes": False,
        "show_fault_paths": False,
    },
    "voltage": "415V AC",
    "language": "en",            # "en" or "ja"
    "phase_hint": "three-phase"  # "single-phase", "three-phase", or null
}
```

### Component ID System

| ID | Component | Notes |
|----|-----------|-------|
| `supply` | Incoming mains / grid | Exactly one, unless ATS is present |
| `supply_2` | Secondary supply (generator) | Used with ATS only |
| `maincb` | Main circuit breaker | One per panel |
| `rcd` / `rcbo` | Earth fault protection device | Optional |
| `bus` | Copper busbar | Optional |
| `nbar` | Neutral bar | Optional |
| `ebar` | Earth bar | Optional |
| `outcb_1..N` | Outgoing branch breakers | One per named circuit, max 15 |
| `ats` | Automatic Transfer Switch | Treated as custom device |
| Any other ID | Custom device | Rendered as generic symbol |

### 3-Stage LLM Pipeline

Both `OllamaClient` and `QFindClient` use a 3-stage chain-of-thought pipeline. This is more reliable than single-shot prompting for smaller models:

1. **Stage 1 — Identify**: Extract raw facts from the prompt. No rules applied.
2. **Stage 2 — Reason**: Think step-by-step in plain text. Apply complexity rules, resolve flags, pick labels.
3. **Stage 3 — Assemble**: Convert Stage 2 reasoning into final JSON. Just follows the reasoning.

`GroqClient` and `GeminiClient` use direct single-shot structured output with JSON schema enforcement — they are capable enough to handle it in one call.

### ERC Engine

`ECD/electrical/erc.py` contains 10 deterministic electrical rule checks (`ERC-001` through `ERC-010`). These run after every diagram generation:

| Code | Check |
|------|-------|
| ERC-001 | Single supply constraint (multiple supplies only allowed with ATS) |
| ERC-002 | Main breaker presence |
| ERC-003 | Earth bar presence in Standard/Detailed |
| ERC-003b | Neutral bar presence in Standard/Detailed |
| ERC-004 | RCD/RCBO presence in Standard/Detailed |
| ERC-005 | Voltage/phase mode transparency |
| ERC-006 | Phase mode component compatibility |
| ERC-007 | Unprotected load detection |
| ERC-008 | Wiring graph cycle detection |
| ERC-009 | Orphaned component detection |
| ERC-010 | Duplicate / colliding component IDs |

These are entirely deterministic — no LLM involved.

---

## Resources

| Resource | URL |
|----------|-----|
| PySide6 Docs | https://doc.qt.io/qtforpython/ |
| Mermaid.js Docs | https://mermaid.js.org/ |
| Ollama | https://github.com/ollama/ollama |
| ezdxf Docs | https://ezdxf.readthedocs.io/ |
| Groq Console | https://console.groq.com/keys |
| Google AI Studio | https://aistudio.google.com/app/apikey |

