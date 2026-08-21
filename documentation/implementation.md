# ECD — Electrical Circuit Diagram Generator
## Architecture & Implementation Reference

---

## Project Overview

ECD is a desktop application that converts natural language descriptions into professional electrical distribution panel diagrams. The user types something like:

> *"415V three-phase panel with 150A MCCB, earth fault breaker, busbar, neutral bar, earth bar, 5.5kW motor, 7.5kW pump, 3kW HVAC"*

...and the app produces a rendered Mermaid diagram, DXF CAD file, KiCad schematic, PNG, SVG, and PDF — all correctly wired, validated against electrical rules, and ready to hand to an electrician.

### Goals

- Enable engineers, electricians, and students to quickly create distribution board diagrams from natural language
- Support multiple export formats: PNG, SVG, PDF, KiCad schematic, DXF
- Validate generated diagrams against 10 deterministic electrical rules (ERC engine)
- Support English and Japanese prompts
- Work with multiple LLM backends (cloud and offline)

---

## High-Level Architecture

```
+--------------------------------------------------------------+
|                    Presentation Layer                         |
|  +-----------+  +-------------------+  +----------------+    |
|  |  Sidebar  |  |  DiagramCanvas    |  |  MainWindow    |    |
|  | (Input UI)|  |  (Qt Graphics)    |  |  (Shell)       |    |
|  +-----------+  +-------------------+  +----------------+    |
+------------------------------+-------------------------------+
                               | parsed_data dict
                               v
+--------------------------------------------------------------+
|                    Business Logic Layer                       |
|  +-----------+  +-------------------+  +----------------+    |
|  | MermaidGen|  |  LLM Clients      |  | ValidationWkr  |    |
|  | (Renderer)|  |  (llm_factory)    |  | (ERC Engine)   |    |
|  +-----------+  +-------------------+  +----------------+    |
+------------------------------+-------------------------------+
                               |
                               v
+--------------------------------------------------------------+
|                    Export & CAD Layer                         |
|  +-----------+  +-------------------+  +----------------+    |
|  |DXFGenerator  | KiCadExporter     |  | PNG/SVG/PDF    |    |
|  | (ezdxf)   |  | (S-expression)    |  | (matplotlib)   |    |
|  +-----------+  +-------------------+  +----------------+    |
+--------------------------------------------------------------+
```

---

## Repository Structure

After the refactor (commit `5e81364`), the project is organized into focused sub-packages. There are stub files in `ECD/` root that simply re-export from the real sub-packages — always edit the sub-packages, not the stubs.

```
ecd/
├── ECD/                            # Main application package
│   ├── main_app.py                 # Application entry point + MainWindow
│   ├── sidebar.py                  # Left panel: prompt input, model selector, templates
│   ├── settings_page.py            # Settings UI: API key management (added post-refactor)
│   ├── config_manager.py           # Reads/writes API keys to .env (added post-refactor)
│   ├── mermaid_generator.py        # Mermaid code generator + regex fallback parser
│   ├── ValidationWorker.py         # Async validation, auto-fix workers, ValidationPanel
│   ├── constants.py                # Complexity level definitions
│   │
│   │   # Stub re-exports (do not edit these — edit sub-packages)
│   ├── diagram_canvas.py           # Stub -> ECD/canvas/diagram_canvas.py
│   ├── erc.py                      # Stub -> ECD/electrical/erc.py
│   ├── pin_model.py                # Stub -> ECD/electrical/pin_model.py
│   ├── dxf_generator.py            # Stub -> ECD/cad/dxf_generator.py
│   ├── symbols.py                  # Stub -> ECD/cad/symbols.py
│   ├── Kicad_exporter.py           # Stub -> ECD/cad/Kicad_exporter.py
│   ├── undo_manager.py             # Stub -> ECD/canvas/undo_manager.py
│   │
│   ├── canvas/                     # Diagram canvas sub-package
│   │   ├── diagram_canvas.py       # Core rendering widget
│   │   ├── symbol_item.py          # Draggable electrical symbol items
│   │   ├── text_item.py            # Editable text label items
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
│   │   ├── erc.py                  # 10-rule deterministic ERC engine
│   │   ├── pin_model.py            # Pin maps, netlist builder, DFS wire tracer
│   │   └── wire_router.py          # Wire routing geometry
│   │
│   ├── llm/                        # LLM client sub-package
│   │   ├── base_client.py          # Abstract LLMClientBase
│   │   ├── llm_factory.py          # Factory: model name -> client instance
│   │   ├── ollama_client.py        # Local Ollama client (3-stage CoT pipeline)
│   │   ├── groq_client.py          # Groq Cloud client
│   │   ├── gemini_client.py        # Google Gemini client
│   │   └── qfind_client.py         # QFind custom model client (3-stage CoT pipeline)
│   │
│   └── assets/
│       └── symbols/                # IEC SVG symbol assets (used by mermaid_generator)
│
├── tests/                          # Automated unit test suite (47 tests)
├── documentation/                  # Project documentation (this file)
├── ECD.spec                        # PyInstaller build specification
├── requirements.txt                # Python dependencies
└── .env                            # API keys (not committed to git)
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| GUI Framework | PySide6 (Qt 6 Python bindings) |
| Diagram Rendering | QGraphicsScene + QWebEngineView (Mermaid.js) |
| LLM Backends | Groq Cloud, Google Gemini, Local Ollama, QFind (self-hosted) |
| Structured Output | JSON schema-constrained API calls |
| ERC Validation | 10-rule deterministic Python engine (no LLM) |
| CAD Export | ezdxf 1.4.3 (DXF with CJK font support) |
| Image Export | Matplotlib backend (PNG/PDF), SVG |
| KiCad Export | Custom S-expression generator |
| Packaging | PyInstaller 6.x |
| Language | Python 3.11+ |
| Threading | QThread for all async workers |

---

## Component Documentation

### main_app.py

**Purpose:** Application entry point and main window shell.

**Key responsibilities:**
- Creates and manages `MainWindow(QMainWindow)`
- Builds menu bar (File, Edit, View, Help)
- Coordinates between `Sidebar` and `DiagramCanvas`
- Handles all export operations (PNG, SVG, PDF, DXF, KiCad)

**Entry point:**
```python
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
```

---

### ECD/sidebar.py

**Purpose:** User input panel.

**Key responsibilities:**
- Text input for diagram description
- Model selection dropdown (all 6 models)
- Complexity level selection (Simple, Neutral, Standard, Detailed)
- Quick-start template buttons
- Generate and Reset buttons

**Model combo items (in order):**
```
Groq - Fast (Limited Daily Use)
Groq - Large (Higher Quality, Limited Daily Use)
Gemini (Limited)
Mistral (Unlimited, Offline)
Qwen (Unlimited, Offline)
QFind (Custom Model)
```

When the user selects a model and clicks Generate, the label string is passed to `llm_factory.get_llm_client()` which resolves it via `MODEL_CONFIGS` to the correct backend and model name.

---

### ECD/settings_page.py

**Purpose:** GUI for managing API keys. Added after the refactor.

Accessed from the menu. Reads and writes to `.env` via `config_manager.py`. Fields: `GROQ_API_KEY`, `GEMINI_API_KEY`, `QFIND_API_KEY`, `QFIND_URL`.

---

### ECD/config_manager.py

**Purpose:** Programmatic read/write of `.env` API key configuration.

Used by `settings_page.py` to persist changes. Handles both the project root path (development) and the executable directory (frozen PyInstaller build).

---

### ECD/canvas/diagram_canvas.py

**Purpose:** Core diagram rendering and interaction hub. This is the largest and most complex file in the project.

**Key responsibilities:**
- Render the diagram in a QGraphicsScene (symbols as draggable items)
- Coordinate LLM generation via background `GenerationWorker`
- Post-process LLM output in `_on_llm_finished()`: sanitize IDs, expand circuits, deduplicate
- Trigger ERC validation via `ValidationWorker`
- Handle element editing (double-click opens editor dialog)
- Export to PNG, SVG, PDF

**Critical post-processing in `_on_llm_finished()`:**

The raw LLM output goes through several sanitization steps before being used:
1. **ID sanitization** — Non-canonical IDs like `outcb_N_1` -> `outcb_1`, `loads-1` -> `loads_1`
2. **Circuit expansion** — If a model returns only `loads` instead of `outcb_1..N` + `loads_1..N`, the `_extract_circuits()` fallback expands them from the original prompt
3. **Deduplication** — Final pass removes any duplicate component IDs

**State:**
- `current_parsed_data` — active diagram data
- `original_parsed_data` — pre-edit state for reset
- `_current_mermaid_code` — live Mermaid code
- `_is_regex_fallback` — True if fallback parser was used

---

### ECD/mermaid_generator.py

**Purpose:** Generate Mermaid sequenceDiagram code from `parsed_data` and create the display HTML. Also contains the regex fallback parser (`parse_prompt()`).

**Complexity handling:**

| Level | Components | Wires |
|-------|-----------|-------|
| Simple | supply, maincb, loads | L only |
| Neutral | Exactly what user described | Prompt-driven |
| Standard | Full set + RCD | L, N, E |
| Detailed | Standard + outgoing MCBs | L, N, E + fault paths |

---

### ECD/llm/ (LLM Clients & Factory)

**`base_client.py`** — Abstract base class. All clients must implement:
- `prompt_to_structured_data(prompt, complexity) -> dict`
- `chat(system_prompt, user_prompt) -> str`

**`llm_factory.py`** — Central factory. `get_llm_client(model_choice)` maps the UI dropdown label to a client instance via `MODEL_CONFIGS`.

**`ollama_client.py`** — Local offline client. Uses a **3-stage chain-of-thought pipeline**:
1. Stage 1: Component identification (JSON output)
2. Stage 2: Step-by-step reasoning (plain text output)
3. Stage 3: Structured JSON assembly (JSON output following Stage 2 reasoning)

Also defines `STRUCTURED_SCHEMA` (shared by all backends) and `COMPONENT_MEANINGS` / `COMPLEXITY_RULES` (shared prompt text used by all clients).

**`groq_client.py`** — Groq Cloud client. Single-shot structured output using `json_schema` response format. Supports `openai/gpt-oss-20b` and `openai/gpt-oss-120b`.

**`gemini_client.py`** — Google Gemini client. Targets `gemini-3.5-flash`. Uses `max_tokens=4096` to avoid truncation of longer outputs.

**`qfind_client.py`** — Self-hosted custom model client. Targets `qfind-chat` at `https://ubuntu.tailcd8da4.ts.net/v1/chat/completions`. Uses the same **3-stage CoT pipeline** as `ollama_client.py`. Stage 2 dynamically injects a `NAMED LOAD EXPANSION` block when 2+ distinct named devices are detected in Stage 1, forcing correct `outcb_1..N` expansion. Reads `QFIND_URL` and `QFIND_API_KEY` from environment.

---

### ECD/electrical/erc.py

**Purpose:** Deterministic 10-rule electrical rule check engine. Runs after every diagram generation. No LLM involved.

**Rules:**

| Code | Tier | Check |
|------|------|-------|
| ERC-001 | Presence | Single supply (multiple allowed only with ATS present) |
| ERC-002 | Presence | Main breaker (`maincb` or top-of-column `rcbo`) |
| ERC-003 | Presence | Earth bar (`ebar`) in Standard/Detailed |
| ERC-003b | Presence | Neutral bar (`nbar`) in Standard/Detailed |
| ERC-004 | Presence | Earth fault protection (`rcd`/`rcbo`) in Standard/Detailed |
| ERC-005 | Consistency | Voltage/phase mode transparency |
| ERC-006 | Consistency | Phase mode component compatibility |
| ERC-007 | Consistency | Unprotected load detection |
| ERC-008 | Topology | Wiring graph cycle detection |
| ERC-009 | Topology | Orphaned component detection |
| ERC-010 | Topology | Duplicate/colliding component IDs |

**Key design decisions:**
- `"loads"` is NOT in `SINGLETON_BASE_TYPES` so `loads_1`, `loads_2`, `loads_3` are valid separate components
- ERC-001 and ERC-010 allow `supply` + `supply_2` (dual supplies) when `ats` is present
- All rules run in a single pass — no short-circuiting — so all findings surface at once

---

### ECD/electrical/pin_model.py

**Purpose:** Pin-level terminal geometry, netlist generation, and DFS wire continuity tracing.

**Key functions:**

| Function | Purpose |
|----------|---------|
| `get_base_type(cid)` | Maps a component ID to its base type. Recognizes `supply`, `maincb`, `rcd`, `rcbo`, `bus`, `nbar`, `ebar`, `loads`, `outcb`, `ats`, `generator`, `gen`, `solar`, `pv` |
| `compute_component_positions()` | Assigns 2D coordinates for CAD layout. Dual supplies are placed side-by-side at x=-35 and x=+35 above the ATS at x=0 |
| `generate_netlist()` | Builds L/N/E wire connection graph |
| `validate_netlist()` | DFS tracing from supply to all loads. `ats` and custom devices act as L_in -> L_out pass-through |

---

### ECD/cad/dxf_generator.py

**Purpose:** Generate DXF CAD files using ezdxf with IEC-standard electrical symbols.

**Key responsibilities:**
- Place component symbols at pin-aware positions from `pin_model.py`
- Draw phase (red), neutral (blue), earth (green) wires
- Handle dual-supply ATS topology (both supplies connect in parallel to ATS inputs)
- Generate title block, legend table, and load schedule

**Custom device detection:**
Any component whose `get_base_type(cid)` is not in `{"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads", "outcb"}` sets `has_custom = True` and triggers the "Custom Device" row in the legend table.

---

### ECD/cad/symbols.py

**Purpose:** ezdxf IEC symbol block library.

Registers reusable DXF blocks including:
- Single-phase: `SYM_BREAKER`, `SYM_MCB`, `SYM_RCD`, `SYM_LAMP`, `SYM_GROUND`, `SYM_JUNCTION`, `SYM_GENERIC`
- Three-phase: `SYM_SUPPLY_3PH`, `SYM_BREAKER_3PH`, `SYM_RCD_3PH`, `SYM_BUSBAR_3PH`, `SYM_MOTOR_3PH`

Each symbol defines terminal pin offsets for wire attachment.

---

### ECD/cad/Kicad_exporter.py

**Purpose:** Export as KiCad 6+ schematic (`.kicad_sch`).

| ECD Component ID | KiCad handling |
|-----------------|----------------|
| `supply` | `supply_L`, `supply_N`, `supply_PE` |
| `maincb` | `maincb` |
| `outcb_N` | `outcb` + load pair |
| `rcd`, `bus`, `nbar`, `ebar` | Absorbed (topology only) |

---

### ECD/ValidationWorker.py

**Purpose:** Async validation and auto-fix workers + the `ValidationPanel` UI widget.

**Classes:**
- `ValidationWorker(QThread)` — runs ERC checks and netlist validation in background. Emits `validationComplete(results)` signal.
- `MermaidFixWorker(QThread)` — takes current diagram + ERC findings and asks the LLM to fix them. Emits `fixComplete(new_mermaid_code)`.
- `ValidationPanel(QWidget)` — displays ERC findings. "Fix Issues" button triggers `MermaidFixWorker`.

---

## Data Model

### `parsed_data` Structure

```python
parsed_data = {
    # Components: list of dicts with id and label
    "components": [
        {"id": "supply",  "label": "Main Supply (230V AC)"},
        {"id": "maincb",  "label": "100A Main Breaker"},
        {"id": "outcb_1", "label": "5.5kW Induction Motor"},
        # ... etc
    ],
    # Flags: control what wires and annotations are shown
    "flags": {
        "show_neutral":          True,
        "show_earth":            True,
        "show_rcd":              True,
        "show_protection_notes": False,
        "show_fault_paths":      False,
    },
    "voltage":    "415V AC",
    "language":   "en",         # "en" | "ja"
    "phase_hint": "three-phase" # "single-phase" | "three-phase" | null
}
```

> **Note on old format:** In older code, `parsed_data["components"]` was a list of tuples `(id, label)`. After the refactor it is a list of dicts `{"id": ..., "label": ...}`. The `_on_llm_finished()` method in `diagram_canvas.py` normalizes both formats automatically.

---

## Component ID System

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
| Any other ID | Custom device | Rendered as generic symbol (`SYM_GENERIC`) |

---

## Request Processing Flow

```
User enters prompt -> clicks Generate
    |
    v
Sidebar.generate_from_prompt(prompt, complexity)
    |
    v
DiagramCanvas._show_loading()
    |
    v
GenerationWorker(prompt, complexity, llm_client).start()
    |
    v  [background thread]
llm_client.prompt_to_structured_data(prompt, complexity)
    |
    |  Ollama/QFind: 3-stage CoT pipeline
    |    Stage 1: identify components (JSON)
    |    Stage 2: reason step-by-step (plain text)
    |    Stage 3: assemble JSON (follows Stage 2 reasoning)
    |
    |  Groq/Gemini: single-shot JSON schema output
    |
    v  [back to main thread via signal]
DiagramCanvas._on_llm_finished(parsed_data)
    |  1. Sanitize IDs (outcb_N_1 -> outcb_1)
    |  2. Expand circuits if model omitted outcb_N
    |  3. Deduplicate component IDs
    |
    v
MermaidGenerator.generate_mermaid_code(parsed_data)
    |
    v
Render diagram in QGraphicsScene
    |
    v  [parallel background thread]
ValidationWorker -> erc.run_erc() + pin_model.validate_netlist()
    |
    v
ValidationPanel displays findings
```

---

## Feature: Custom & Special Symbols

### What counts as a custom component?

Any component ID that `get_base_type(cid)` in `pin_model.py` cannot map to a known standard type is treated as a **custom device**. The known standard types are:

| Base type | Matched IDs |
|-----------|------------|
| `supply` | `supply`, `grid`, `mains`, `generator`, `gen`, `solar`, `pv`, and `supply_2` |
| `maincb` | `maincb`, `mccb`, `mcb` |
| `rcd` | `rcd` |
| `rcbo` | `rcbo` |
| `bus` | `bus`, `busbar` |
| `nbar` | `nbar`, `neutral` |
| `ebar` | `ebar`, `earth` |
| `loads` | `loads`, `load` |
| `outcb` | `outcb_1` .. `outcb_15` |
| `ats` | `ats` |

Any other ID — `spd`, `meter`, `contactor`, `softstart`, `transformer`, `capacitor`, `inverter`, etc. — is classified as a custom device.

### How custom components flow through the stack

```
LLM returns component with id "spd" (surge protection device)
    |
    v
_on_llm_finished() in diagram_canvas.py
  - ID sanitization passes (no renaming needed, "spd" is valid)
  - Kept as-is in parsed_data["components"]
    |
    v
mermaid_generator.py
  - "spd" has no special case -> rendered as a generic box
  - Label from parsed_data used as-is
    |
    v
pin_model.py -> get_base_type("spd") returns None
  - validate_netlist(): treated as L_in -> L_out pass-through
  - compute_component_positions(): placed in the main vertical column
    |
    v
dxf_generator.py
  - Symbol: SYM_GENERIC (rectangular box with X)
  - has_custom = True is set
  - Legend table gains a "Custom Device" row with the generic symbol
    |
    v
erc.py
  - ERC-009 (orphan check): custom device is checked for connectivity
  - ERC-010 (duplicate IDs): custom device ID checked for uniqueness
  - No special singleton constraint applied
```

### Standard IEC Symbols vs Generic Symbol

| Component type | DXF Symbol used |
|----------------|----------------|
| Single-phase supply | `SYM_SUPPLY_3PH` (adapted) |
| Main breaker | `SYM_BREAKER` |
| MCB | `SYM_MCB` |
| RCD / RCBO | `SYM_RCD` |
| Motor (3-phase) | `SYM_MOTOR_3PH` |
| Busbar | `SYM_BUSBAR_3PH` |
| Neutral/Earth bar | Terminal block symbol |
| **Any custom device** | **`SYM_GENERIC`** (box with X) |

### CAD Legend Table

When `has_custom = True`, the DXF legend table automatically includes a **Custom Device** row showing `SYM_GENERIC`. This happens in `dxf_generator.py` location 2 of the legend rendering function.

If a diagram has **no** custom devices, this row is omitted from the legend.

---

## Feature: Multiple Sources & ATS Panels

### Overview

A panel can have two incoming supplies — typically a utility grid and a generator or solar backup — connected through an **Automatic Transfer Switch (ATS)**. The ATS ensures only one source powers the panel at a time.

ECD supports this topology end-to-end: from LLM parsing through netlist routing, ERC validation, and DXF CAD output.

### Component IDs involved

| ID | Role |
|----|------|
| `supply` | Primary supply (grid / mains) |
| `supply_2` | Secondary supply (generator / solar / UPS) |
| `ats` | Automatic Transfer Switch |
| `maincb` | Main breaker (downstream of ATS) |

### How the LLM detects dual-supply panels

The LLM is guided by `COMPONENT_MEANINGS` which tells it:
- `supply` = incoming mains / grid source
- Any generator, backup source, or secondary feed maps to `supply_2`
- `ats` = custom device with ID `ats`

When the user writes something like `Grid Supply, Generator Backup, ATS`, the LLM produces:

```json
{
  "components": [
    {"id": "supply",   "label": "Grid Supply (230V AC)"},
    {"id": "supply_2", "label": "Generator Backup"},
    {"id": "ats",      "label": "Automatic Transfer Switch"},
    {"id": "maincb",   "label": "63A Main Breaker"},
    ...
  ]
}
```

### Post-processing in diagram_canvas.py

`_on_llm_finished()` includes a `supply_2` re-mapper. If the LLM returns a secondary supply with a non-canonical ID (e.g. `generator`, `gen_supply`), it is normalised to `supply_2` before being passed downstream.

### Netlist routing (pin_model.py)

`validate_netlist()` performs DFS wire-continuity tracing from supply to all loads:

- `supply` and `supply_2` are both treated as `supply` base type — both are valid source nodes
- `ats` is treated as a **pass-through** (`L_in` → `L_out`) so the DFS continues through it
- This means all loads downstream of `maincb` (which sits after the ATS) still show as reachable from both sources

Without the pass-through rule, the DFS would stop at `ats` and report all loads as unreachable (connectivity errors).

### Physical layout (pin_model.py)

`compute_component_positions()` handles dual-supply layout:

| Component | X position | Y position |
|-----------|-----------|-----------|
| `supply` (grid) | -35.0 | top |
| `supply_2` (generator) | +35.0 | top |
| `ats` | 0.0 | below both supplies |
| `maincb` | 0.0 | below ATS |
| rest of panel | 0.0 | continues downward |

This places both supply sources side-by-side above the ATS, preventing the overlap that occurred before this was implemented.

### DXF wiring (dxf_generator.py)

The DXF generator has specific logic for the dual-supply case:

```
supply  ─┐
          ├─→ ats → maincb → bus → outcb_1..N → loads
supply_2 ─┘
```

Both `supply` and `supply_2` wire into the ATS inputs in parallel. The ATS output connects to `maincb`. From `maincb` onward the diagram is identical to a standard single-supply panel.

### ERC rules affected

| Rule | Normal behaviour | With ATS present |
|------|-----------------|-----------------|
| ERC-001 | Raises ERROR if more than one supply detected | Suppressed — dual supply is valid |
| ERC-010 | Raises ERROR if `supply_2` collides with `supply` under singleton normalisation | Suppressed — `supply_2` is the designated secondary supply ID |

Both suppressions are conditional on `ats` being present in the component list. Without an `ats`, two supplies still raise ERC-001.

---

## Feature: Interactive Canvas & Per-Symbol Editing

The application features an interactive 2D graphics canvas implemented via Qt Graphics View Framework (`QGraphicsScene` + `QGraphicsView` in `ECD/canvas/`).

```
┌─────────────────────────────────────────────────────────────┐
│                    DiagramCanvas (QGraphicsView)             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    QGraphicsScene                      │  │
│  │  ┌────────────────────┐     ┌──────────────────────┐  │  │
│  │  │ SymbolItem         │     │ EditableTextItem     │  │  │
│  │  │ (Draggable SVG/box)│     │ (Double-click edit)  │  │  │
│  │  └────────────────────┘     └──────────────────────┘  │  │
│  │  ┌────────────────────┐     ┌──────────────────────┐  │  │
│  │  │ SelectionManager   │     │ UndoManager          │  │  │
│  │  │ (Rubberband/group) │     │ (QUndoStack history) │  │  │
│  │  └────────────────────┘     └──────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Modules in `ECD/canvas/`

| Module | Class | Responsibility |
|--------|-------|---------------|
| `diagram_canvas.py` | `DiagramCanvas` | Host widget, viewport transform, wire routing recalculation on move, scene geometry management. |
| `symbol_item.py` | `SymbolItem` / `DiagramGroupItem` | Draggable symbol graphical items, bounding box handles, terminal snap points. |
| `text_item.py` | `EditableTextItem` | Click-to-edit text labels. Emits text modification signals on commit. |
| `commands.py` | `MoveCommand`, `TextEditCommand` | Qt `QUndoCommand` implementations encapsulating before/after states. |
| `undo_manager.py` | `UndoManager` | Manages `QUndoStack`, connects to `Ctrl+Z` (Undo), `Ctrl+Y` / `Ctrl+Shift+Z` (Redo). |
| `selection_manager.py` | `SelectionManager` | Handles multi-selection, rubberband selection, and grouped dragging. |

### Interactive Capabilities

1. **Direct Manipulation**: Click and drag any component symbol or text label to reposition it. Connecting wires dynamically recalculate their Manhattan bend routes in real time.
2. **Inline Text Editing**: Double-click any label to modify component ratings, descriptions, or voltage annotations directly on the canvas.
3. **Multi-Selection & Group Drag**: Shift-click or rubberband-select multiple components to move entire sub-circuits together.
4. **Undo / Redo Stack**: All drag operations, label edits, and layout adjustments push onto a full `QUndoStack` history (`Ctrl+Z` / `Ctrl+Y`).
5. **Zoom & Pan**: Mouse wheel zoom, middle-click pan, fit-to-view, and zoom slider controls.
6. **Layout Reset**: "Reset Layout" button restores the diagram to the deterministic pin-model computed positions.
7. **JSON Diagram Save / Load**: Diagrams can be saved to `.json` files preserving both semantic component data and manual layout position overrides (`component_position_overrides`), and reopened later.

---

## Feature: CAD Layer, Styling & Multi-Format Export Specification

### DXF Layer Table & Color Coding

The DXF export engine (`ECD/cad/dxf_generator.py`) generates AutoCAD R2010 compliant `.dxf` files using `ezdxf` with structured layering:

| Layer Name | AutoCAD Color Index (ACI) | Color | Line Type | Purpose |
|------------|--------------------------|-------|-----------|---------|
| `BACKGROUND` | 250 | Dark Gray | Continuous | Outer canvas page border |
| `PAGE_MARGIN` | 250 | Dark Gray | Continuous | Inner printable margin border |
| `COMPONENTS` | 7 (White/Black) | White | Continuous | Component boundary boxes & IEC symbol blocks |
| `WIRES_PHASE` | 1 (Red) | Red | Continuous | Single-phase Line (L) or 3-phase trunk wires |
| `WIRES_NEUTRAL` | 3 (Green) | Green | `DASHED` | Neutral (N) return conductors |
| `WIRES_EARTH` | 5 (Blue) | Blue | `DASHDOT` | Protective Earth (PE) conductors |
| `WIRES_FAULT` | 6 (Magenta) | Magenta | `DASHED` | Ground fault simulated paths |
| `WIRE_LABELS` | 2 (Yellow) | Yellow | Continuous | Wire annotation & terminal callouts |
| `TITLE` | 4 (Cyan) | Cyan | Continuous | Title block headers and document metadata |
| `NOTES` | 7 (White/Black) | White | Continuous | Safety notes & protection remarks |
| `LEGEND` | 7 (White/Black) | White | Continuous | Symbol legend table border and item text |
| `LOAD_SCHEDULE` | 7 (White/Black) | White | Continuous | Load schedule table border and branch ratings |

### Three-Phase Line Colors

In three-phase distribution mode (`phase_mode == "three"`), phase conductors use standard identification:
- **Phase L1**: Red (ACI 1)
- **Phase L2**: Yellow (ACI 2)
- **Phase L3**: Orange (ACI 30)

### Japanese & CJK Font Handling

When generating diagrams with Japanese text (`language == "ja"`), the DXF generator configures fallback styles targeting standard CJK TrueType fonts (`MS Gothic`, `Meiryo`, `Yu Gothic`, or `SimSun`) to prevent question marks (`???`) or box characters in AutoCAD, DraftSight, or DWG TrueView.

### Tiered Page Sizing

The DXF exporter automatically selects the optimal page envelope based on the number of outgoing circuits ($N$) and phase mode:

| Circuits ($N$) | DXF Page Size | Dimensions (mm) |
|---------------|---------------|-----------------|
| 1 – 4 | Custom Compact | $420 \times 297$ (A3 equivalent) |
| 5 – 8 | Custom Standard | $594 \times 420$ (A2 equivalent) |
| 9 – 12 | Custom Large | $841 \times 594$ (A1 equivalent) |
| 13 – 15 | Custom Extended | $1189 \times 841$ (A0 equivalent) |

### Supported Export Formats

| Format | Module | Backend | Output Description |
|--------|--------|---------|-------------------|
| **DXF (.dxf)** | `ECD/cad/dxf_generator.py` | `ezdxf` | Vector CAD with IEC symbol blocks, legend, load schedule, and layers. |
| **KiCad (.kicad_sch)** | `ECD/cad/Kicad_exporter.py` | S-expression | KiCad 6+ schematic format with embedded `lib_symbols`. |
| **SVG (.svg)** | `ECD/canvas/diagram_canvas.py` | Qt SVG / Matplotlib | Scalable vector graphic for web and print. |
| **PNG (.png)** | `ECD/canvas/diagram_canvas.py` | `QImage` / Matplotlib | High-resolution raster image render. |
| **PDF (.pdf)** | `ECD/canvas/diagram_canvas.py` | `QPainter` / `QPdfWriter` | Vector PDF document with title block. |
| **JSON (.json)** | `ECD/canvas/diagram_canvas.py` | Python `json` | Complete diagram project state with position overrides. |
| **Mermaid (.txt)** | `ECD/mermaid_generator.py` | Text generator | Plain text sequence diagram code. |

---

## Configuration


### Environment Variables

| Variable | Purpose | Required |
|----------|---------|---------|
| `GROQ_API_KEY` | Groq Cloud API key | Only for Groq models |
| `GEMINI_API_KEY` | Google AI Studio API key | Only for Gemini |
| `QFIND_API_KEY` | QFind endpoint API key | Optional |
| `QFIND_URL` | QFind endpoint URL | Only for QFind (defaults to `https://ubuntu.tailcd8da4.ts.net`) |
| `ECD_LLM_BACKEND` | Default backend if no UI selection | Optional (defaults to `groq`) |

Set via `.env` file at project root, or via the **Settings page** in the UI.

### Complexity Level System

| Level | Components | Wires | Use case |
|-------|-----------|-------|---------|
| Simple | supply, maincb, loads | L only | Basic concept |
| Neutral | Prompt-defined only | Prompt-defined | Maximum flexibility |
| Standard | supply, maincb, rcd, bus, nbar, ebar, loads | L, N, E | Professional |
| Detailed | Standard + outcb_N per circuit | L, N, E + fault paths | Full documentation |

---

## Known Issues & Tech Debt

### Resolved Since Original Documentation

- **Duplicate OllamaClient** — consolidated into `ECD/llm/ollama_client.py`
- **Test files in repo root** — moved to `tests/` with proper unittest framework (47 tests)
- **No unit test framework** — automated tests now run with `python -m unittest discover tests`
- **Hardcoded LLM config** — fully configurable via `MODEL_CONFIGS` in `llm_factory.py` and the Settings page

### Remaining

- **`mermaid_generator.py` is large** (~1400 lines). Mixes regex parsing, Mermaid code generation, and HTML template rendering. Works reliably but could be split.
- **Print-based logging** — still uses `print(f"[module] ...")` throughout. A proper `logging` module would be an improvement.
- **QFind model quality** — `qfind-chat` is not as fine-tuned as Groq/Gemini for electrical diagram JSON output. The 3-stage pipeline helps significantly but does not fully close the gap for all prompt types.

---

## Design Decisions

### Why Sub-packages?

The original flat structure (`ECD/*.py`) became hard to navigate as the codebase grew. The refactor split it into `canvas/`, `cad/`, `electrical/`, and `llm/` to make ownership clear. Root stubs preserve backward compatibility for any existing imports.

### Why Sequence Diagrams?

Mermaid sequence diagrams were chosen because they naturally represent electrical flow (supply -> breaker -> load), the participant boxes map directly to electrical components, and non-technical users can read and manually edit the diagram.

### Why 3-Stage Pipeline for Ollama/QFind?

Smaller models struggle to simultaneously understand domain rules, apply complexity logic, AND format valid JSON in one pass. Breaking the task into three focused stages (identify -> reason -> assemble) dramatically improves reliability — each stage is a much simpler, focused task.

### Why Deterministic ERC Instead of LLM Validation?

Electrical rules are rule-based by nature. LLMs can hallucinate; deterministic code does not. The ERC engine runs on every diagram, catches real issues reliably, and has a full test suite. The LLM-based `MermaidFixWorker` is used only as a second step to propose fixes after ERC identifies problems.
