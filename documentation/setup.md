# ECD Developer Onboarding Guide

## Prerequisites

### Operating Systems

- **Windows 10/11** (Primary development platform)
- **Linux** (Should work, not officially tested)
- **macOS** (Should work, not officially tested)

### Language & Runtime

- **Python 3.9+** (3.10+ recommended)
- **pip** (Python package manager)

### Required Services

- **Ollama** - Local LLM inference server
  - Download: https://ollama.ai
  - Model: `mistral:7b-instruct` (downloaded automatically on first use)

### Tools

- **Git** - Version control
- **Code Editor** - VS Code recommended (Python extension helpful)

### Hardware Requirements

- **RAM**: 16 GB minimum (LLM inference requires ~8 GB)
- **Storage**: 10 GB free (model weights + dependencies)
- **CPU**: Multi-core recommended for LLM performance
- **GPU**: Optional but recommended for faster LLM inference

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd ecd
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

**Option A: Minimal Installation**
```bash
pip install -r requirement.txt
```

This installs only the core dependencies:
- `ezdxf==1.4.3` - DXF file generation
- `PySide6==6.10.1` - Qt GUI framework
- `matplotlib` - Required for rendering and exporting diagrams as PNG and PDF files (ezdxf drawing addon)

**Option B: Full Installation**
```bash
pip install -r requirements.txt
```

This installs additional packages including:
- Machine learning libraries (tensorflow, torch)
- Web frameworks (fastapi, streamlit)
- Various utilities
- `matplotlib` and other CAD dependencies

> **Note**: The full requirements.txt appears to include packages not required for basic operation. Use minimal installation (Option A) with matplotlib unless you need specific features.

### Step 4: Install Ollama

1. Download from https://ollama.ai
2. Run the installer
3. Verify installation:
   ```bash
   ollama --version
   ```

4. Pull the required model:
   ```bash
   ollama pull mistral:7b-instruct
   ```

5. Start the Ollama server (if not auto-started):
   ```bash
   ollama serve
   ```

   The server runs at `http://localhost:11434`

### Step 5: Verify Installation

```bash
# Test imports
python -c "from PySide6.QtWidgets import QApplication; print('PySide6 OK')"
python -c "import ezdxf; print('ezdxf OK')"
python -c "import requests; requests.get('http://localhost:11434'); print('Ollama OK')"
```

---

## Running the Project

All executable scripts and modules in the project should be run from the **project root directory** using Python's module (`-m`) notation to ensure correct package import resolution.

### Running the Main GUI Application
To launch the main desktop diagram app:
```bash
python -m ECD.main_app
```

### Running Scripts and Diagnostics
To execute other utility, verification, or regression scripts in the repository:
```bash
# Verify DXF symbol wiring
python -m ECD.scripts.verify_dxf_symbol_wiring

# Verify Pin model connectivity checks
python -m ECD.scripts.verify_pin_model

# Run custom scratch tests
python C:\Users\Administrator\.gemini\antigravity\brain\74378425-7dcb-45df-9acb-201ab2ece057\scratch\test_gemini_client_live.py
```

### Expected Behavior

1. Application window opens (1400x900 pixels)
2. Sidebar appears on left with input controls
3. Welcome screen shows in main canvas area
4. Status bar shows "Ready" message

### Testing the Application

1. Enter a prompt in the text area, e.g.:
   ```
   Main supply at 230V, main breaker, busbar, neutral bar, earth bar, and load circuits for lights and sockets.
   ```

2. Select complexity level:
   - **Simple**: Phase wire only
   - **Neutral**: Prompt-driven (recommended for testing)
   - **Standard**: Full L/N/E with RCD
   - **Detailed**: Complete with fault paths

3. Click **"⚡ Generate Diagram"**

4. Wait for:
   - Loading screen appears
   - LLM parses prompt (~5-15 seconds)
   - Diagram renders
   - Validation panel shows results

### Troubleshooting LLM Issues

If generation fails:

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check model is available
ollama list

# Test LLM directly
ollama run mistral:7b-instruct "Hello, respond with OK"
```

---

## Build Process

### Creating a Standalone Executable

The project includes a PyInstaller spec file for building an executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller DiagramGeneration.spec
```

### Build Output

- Output directory: `dist/`
- Executable: `DiagramGeneration.exe` (Windows)
- Build artifacts: `build/`

### Build Notes

1. The spec file targets `Sequence.py` (may need update to `ECD/main_app.py`)
2. WebEngine resources must be included
3. Build size is large due to Qt and WebEngine

### Common Build Issues

**Issue**: Missing modules
```
Solution: Add hidden imports to spec file:
hiddenimports=['PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel']
```

**Issue**: WebEngine not working
```
Solution: Ensure all PySide6 packages are included
```

---

## Environment Variables

The application can be configured using environment variables loaded from a `.env` file at the project root, or set dynamically in your terminal shell.

### LLM Backend Selection (`ECD_LLM_BACKEND`)
Defines which LLM backend the application uses for diagram generation and parsing.
- **Value options**:
  - `ollama` (Default, offline, shipping path): Local Ollama server.
  - `groq` (Cloud): Fast cloud hosted models.
  - `gemini` (Cloud): Google Gemini models.

### Changing the Backend LLM via Terminal
You can temporarily or permanently override the active backend directly from your terminal before running the application:

#### Option A: Windows PowerShell (Session-only)
```powershell
# Set backend to Groq
$env:ECD_LLM_BACKEND="groq"

# Verify the backend value
echo $env:ECD_LLM_BACKEND
```

#### Option B: Windows Command Prompt (Session-only)
```cmd
# Set backend to Groq
set ECD_LLM_BACKEND=groq

# Verify the backend value
echo %ECD_LLM_BACKEND%
```

#### Option C: Persistent Environment Variable (Across all sessions)
To set the variable permanently in Windows registry:
```cmd
# Set backend persistently
setx ECD_LLM_BACKEND "groq"
```
*(Note: Restart your terminal/IDE for persistent changes to take effect.)*

### API Keys
Required when running cloud-based LLM backends:
- **`GROQ_API_KEY`**: Set your API key from Groq console (required when `ECD_LLM_BACKEND=groq`).
- **`GEMINI_API_KEY`**: Set your Google AI Studio API key (required when `ECD_LLM_BACKEND=gemini`).

### Default Models per Backend
- **Ollama**: Defaults to `mistral:7b-instruct`.
- **Groq**: Defaults to `openai/gpt-oss-20b`.
- **Gemini**: Defaults to `gemini-3.5-flash` (with a token limit of 4096 to prevent thinking/structured output truncation).

---

### Optional Customization

To change the LLM endpoints or model names programmatically, you can modify the respective client classes inside `ECD/llm/` (`ollama_client.py`, `groq_client.py`, `gemini_client.py`).

---

## Database Setup

This application does not use a database. All diagram data is stored in memory and optionally exported to files.

---

## Troubleshooting

### Common Errors and Solutions

#### Error: "ModuleNotFoundError: No module named 'PySide6'"

**Cause**: Dependencies not installed

**Solution**:
```bash
pip install PySide6
```

---

#### Error: "Connection refused" when calling Ollama

**Cause**: Ollama server not running

**Solution**:
```bash
# Start Ollama server
ollama serve

# Or check if it's running
curl http://localhost:11434
```

---

#### Error: "model 'mistral:7b-instruct' not found"

**Cause**: Model not downloaded

**Solution**:
```bash
ollama pull mistral:7b-instruct
```

---

#### Error: WebEngine not rendering diagrams

**Cause**: Missing WebEngine components

**Solution**:
```bash
pip install PySide6-WebEngine
```

---

#### Error: "TypeError: 'NoneType' object is not subscriptable" during generation

**Cause**: LLM returned invalid JSON

**Solution**: 
- Check LLM is running properly
- Try a simpler prompt
- Check Ollama logs for errors

---

#### Error: "Export failed" for KiCad or DXF

**Cause**: Invalid component data

**Solution**:
- Generate diagram with "Standard" complexity
- Check that diagram has valid components
- Look for error details in console output

---

#### Error: Application window is blank

**Cause**: WebEngine initialization issue

**Solution**:
- Update graphics drivers
- Try disabling hardware acceleration:
  ```bash
  set QT_QUICK_BACKEND=software
  python main_app.py
  ```

---

### Dependency Issues

#### Port Conflicts

Ollama uses port 11434 by default. If this port is in use:

1. Stop the conflicting service, or
2. Change Ollama's port (requires Ollama configuration)

#### Memory Issues

LLM inference requires significant memory. If the application crashes:

1. Close other applications
2. Use a smaller model:
   ```bash
   ollama pull mistral:7b-instruct-q4_0
   ```
3. Modify `ollama_client.py` to use the smaller model

---

## Useful Commands

### Development

```bash
# Run application
python ECD/main_app.py

# Check Python version
python --version

# Check installed packages
pip list

# Update a package
pip install --upgrade PySide6

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
```

### Git

```bash
# Check status
git status

# View changes
git diff

# Commit changes
git add .
git commit -m "Description of changes"
```

### Ollama

```bash
# List available models
ollama list

# Pull a model
ollama pull mistral:7b-instruct

# Run model interactively
ollama run mistral:7b-instruct

# Delete a model
ollama rm mistral:7b-instruct

# Show model info
ollama show mistral:7b-instruct
```

---

## Testing

### Manual Testing Checklist

1. **Startup**
   - [ ] Application opens without errors
   - [ ] Window displays correctly
   - [ ] Sidebar shows all controls

2. **Diagram Generation**
   - [ ] Simple complexity works
   - [ ] Neutral complexity works
   - [ ] Standard complexity works
   - [ ] Detailed complexity works

3. **Bilingual Support**
   - [ ] English prompts work
   - [ ] Japanese prompts work
   - [ ] Language detection is correct

4. **Editing**
   - [ ] Drag boxes to reposition
   - [ ] Double-click to edit text
   - [ ] Code editing updates diagram

5. **Export**
   - [ ] PNG export works
   - [ ] SVG export works
   - [ ] PDF export works
   - [ ] Mermaid code download works
   - [ ] KiCad export works

6. **Validation**
   - [ ] Validation panel shows
   - [ ] Issues are detected
   - [ ] Auto-fix works

### Test Prompts

**English:**
```
Main supply at 230V, main breaker, RCD, busbar, neutral bar, earth bar, and load circuits.
```

**Japanese:**
```
主電源230V/415V、メインブレーカー、バスバー、中性線バー、接地バー、照明とコンセントの負荷回路を含む基本的な電力配電図。
```

**Industrial:**
```
Three-phase 415V incoming supply, main MCCB breaker, copper busbar system, multiple outgoing MCBs for motors, neutral bar and earth bar.
```

---

## Debugging

### Enable Debug Output

Add to the beginning of `main_app.py`:

```python
import sys
sys.dont_write_bytecode = True  # Prevent .pyc files

# Enable Qt debugging
import os
os.environ['QT_DEBUG_PLUGINS'] = '1'
```

### Useful Debug Points

Add print statements at these locations:

1. **After LLM response** (`ollama_client.py`):
   ```python
   print(f"LLM Response: {raw[:500]}")
   ```

2. **After parsing** (`diagram_canvas.py`):
   ```python
   print(f"Parsed components: {parsed_data['components']}")
   ```

3. **After Mermaid generation** (`mermaid_generator.py`):
   ```python
   print(f"Mermaid code length: {len(mermaid_code)}")
   ```

### Logging LLM Requests

Add to `ollama_client.py`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Before request
logging.debug(f"Sending to LLM: {prompt[:200]}")

# After response
logging.debug(f"LLM response time: {response.elapsed.total_seconds()}s")
```

---

## Development Workflow

### Recommended Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and test**
   ```bash
   # Edit files
   python ECD/main_app.py  # Test
   ```

3. **Commit frequently**
   ```bash
   git add .
   git commit -m "Descriptive message"
   ```

4. **Test all export formats**
   - Generate a diagram
   - Export to PNG, SVG, PDF, KiCad
   - Verify all work correctly

5. **Merge to main**
   ```bash
   git checkout main
   git merge feature/my-feature
   ```

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings to new functions
- Keep functions under 50 lines when possible

### Adding New Features

1. **New export format**:
   - Create new exporter module
   - Add menu item in `main_app.py`
   - Connect to export function

2. **New complexity level**:
   - Add to `constants.py`
   - Update `MermaidGenerator` if needed
   - Add validation rules to `ValidationWorker.py`

3. **New template**:
   - Add to `sidebar.py` `_templates` dict
   - Test with both English and Japanese

---

## Project Structure Reference

```
ecd/
├── ECD/                    # Main application
│   ├── main_app.py         # Entry point
│   ├── diagram_canvas.py   # Core logic
│   ├── sidebar.py          # Input UI
│   ├── mermaid_generator.py
│   ├── ollama_client.py
│   ├── web_bridge.py
│   ├── ValidationWorker.py
│   ├── Kicad_exporter.py
│   ├── element_editor.py
│   └── constants.py
│
├── documentation/          # This documentation
├── dxf_generator.py        # DXF export
├── diagram.py             # Alternative editor (legacy)
├── Sequence.py            # Prototype
├── requirements.txt       # Dependencies
└── DiagramGeneration.spec # Build config
```

---

## Getting Help

### Resources

- **PySide6 Documentation**: https://doc.qt.io/qtforpython/
- **Mermaid.js Documentation**: https://mermaid.js.org/
- **Ollama Documentation**: https://github.com/ollama/ollama
- **ezdxf Documentation**: https://ezdxf.readthedocs.io/

### Common Questions

**Q: Can I use a different LLM model?**

A: Yes, modify `ollama_client.py` to use any Ollama-compatible model:
```python
def __init__(self, model="llama2:7b", ...):
```

**Q: Can I run this without a GPU?**

A: Yes, but LLM inference will be slower. Consider using a smaller model like `mistral:7b-instruct-q4_0`.

**Q: How do I add support for another language?**

A: Add translations to:
- `mermaid_generator.py`: `components_map`, `keywords_map`, `diagram_labels`
- `sidebar.py`: Templates
- `ValidationWorker.py`: Validation prompts

**Q: Why is my diagram different from what I described?**

A: The LLM interprets your prompt. Try:
- Being more specific
- Using "Neutral" complexity mode
- Checking the Mermaid code directly
