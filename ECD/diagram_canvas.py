# diagram_canvas.py
import json
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
import os

from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter

class SvgPreviewWidget(QWidget):
    """Renders an SVG scaled to fit the widget, preserving aspect ratio.
    scale_factor is a zoom multiplier on top of the fit-to-view base.
    At scale_factor=1.0 the entire SVG is visible.  When zoomed in
    beyond 1.0, DiagramCanvas resizes the widget explicitly so that
    scrollbars appear in the parent QScrollArea.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer()
        self.scale_factor = 1.0

    def load(self, byte_array: QByteArray) -> bool:
        res = self.renderer.load(byte_array)
        self.scale_factor = 1.0
        self.updateGeometry()
        self.update()
        return res

    def set_scale(self, scale: float):
        self.scale_factor = max(0.2, min(scale, 5.0))
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.renderer.isValid():
            return
        sz = self.renderer.defaultSize()
        if sz.isEmpty() or self.width() == 0 or self.height() == 0:
            return

        # Scale SVG to fit widget bounds, preserving aspect ratio
        scale = min(self.width() / sz.width(), self.height() / sz.height())
        w = int(sz.width() * scale)
        h = int(sz.height() * scale)

        # Center in widget
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2

        self.renderer.render(painter, QRect(x, y, w, h))

class WelcomeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            WelcomeWidget {
                background-color: #f0f4f8;
            }
            #card {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
            #title {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 24px;
                font-weight: 800;
                color: #2c5282;
            }
            #subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #718096;
            }
            #icon {
                font-size: 40px;
            }
            .step-num {
                background-color: #ebf4ff;
                color: #2c5282;
                border-radius: 12px;
                font-weight: bold;
                font-size: 13px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            .step-txt {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #4a5568;
            }
            .divider {
                font-size: 18px;
                color: #a0aec0;
                font-weight: bold;
            }
        """)
        
        main_lay = QVBoxLayout(self)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(30, 30, 30, 30)
        card_lay.setSpacing(15)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel("⚡")
        icon.setObjectName("icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(icon)
        
        title = QLabel("Electrical Diagram Generator")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title)
        
        subtitle = QLabel("Describe your electrical system in plain language\nand get a professional distribution diagram instantly.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(subtitle)
        
        steps_widget = QWidget()
        steps_lay = QHBoxLayout(steps_widget)
        steps_lay.setContentsMargins(0, 10, 0, 0)
        steps_lay.setSpacing(10)
        steps_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Step 1
        s1_num = QLabel("1")
        s1_num.setProperty("class", "step-num")
        s1_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s1_txt = QLabel("Type description\nin the panel")
        s1_txt.setProperty("class", "step-txt")
        s1_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w1 = QWidget()
        w1_lay = QVBoxLayout(w1)
        w1_lay.setContentsMargins(0, 0, 0, 0)
        w1_lay.addWidget(s1_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w1_lay.addWidget(s1_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w1)
        
        div1 = QLabel("→")
        div1.setProperty("class", "divider")
        steps_lay.addWidget(div1)
        
        # Step 2
        s2_num = QLabel("2")
        s2_num.setProperty("class", "step-num")
        s2_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s2_txt = QLabel("Choose a\ndetail level")
        s2_txt.setProperty("class", "step-txt")
        s2_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w2 = QWidget()
        w2_lay = QVBoxLayout(w2)
        w2_lay.setContentsMargins(0, 0, 0, 0)
        w2_lay.addWidget(s2_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w2_lay.addWidget(s2_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w2)
        
        div2 = QLabel("→")
        div2.setProperty("class", "divider")
        steps_lay.addWidget(div2)
        
        # Step 3
        s3_num = QLabel("3")
        s3_num.setProperty("class", "step-num")
        s3_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s3_txt = QLabel("Press ⚡\nGenerate Diagram")
        s3_txt.setProperty("class", "step-txt")
        s3_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w3 = QWidget()
        w3_lay = QVBoxLayout(w3)
        w3_lay.setContentsMargins(0, 0, 0, 0)
        w3_lay.addWidget(s3_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w3_lay.addWidget(s3_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w3)
        
        card_lay.addWidget(steps_widget)
        main_lay.addWidget(card)

class LoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            LoadingWidget {
                background-color: #f0f4f8;
            }
            #card {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
            #title {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                font-weight: 700;
                color: #2c5282;
            }
            #subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #718096;
            }
            #spinner {
                font-size: 36px;
            }
        """)
        
        main_lay = QVBoxLayout(self)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(40, 40, 40, 40)
        card_lay.setSpacing(15)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = QLabel("⏳")
        spinner.setObjectName("spinner")
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(spinner)
        
        title = QLabel("Generating Diagram…")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title)
        
        subtitle = QLabel("Parsing your description and building the diagram.\nThis may take a few seconds.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(subtitle)
        
        main_lay.addWidget(card)

class CodePanel(QWidget):
    applied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = True
        self.setStyleSheet("""
            CodePanel {
                background-color: #2d3748;
                border-top: 2px solid #1a202c;
            }
            QPlainTextEdit {
                background-color: #1a202c;
                color: #edf2f7;
                font-family: 'Courier New', Courier, monospace;
                font-size: 13px;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background-color: #3182ce;
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
            QPushButton:pressed {
                background-color: #2c5282;
            }
            #toggle_btn {
                background-color: transparent;
                color: #a0aec0;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border: 1px solid #4a5568;
                border-radius: 4px;
            }
            #toggle_btn:hover {
                background-color: #4a5568;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(4)

        # Header bar — always visible
        hdr = QHBoxLayout()
        self.toggle_btn = QPushButton("▶ Mermaid Code")
        self.toggle_btn.setObjectName("toggle_btn")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        hdr.addWidget(self.toggle_btn)
        hdr.addStretch()

        self.apply_btn = QPushButton("⚡ Apply Changes")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        hdr.addWidget(self.apply_btn)
        lay.addLayout(hdr)

        # Editor area — hidden by default
        self.text_edit = QPlainTextEdit()
        self.text_edit.setFixedHeight(220)
        self.text_edit.setVisible(False)
        self.apply_btn.setVisible(False)
        lay.addWidget(self.text_edit)

    def toggle(self):
        self._collapsed = not self._collapsed
        self.text_edit.setVisible(not self._collapsed)
        self.apply_btn.setVisible(not self._collapsed)
        self.toggle_btn.setText("▼ Mermaid Code" if not self._collapsed else "▶ Mermaid Code")

    def set_code(self, code: str):
        self.text_edit.setPlainText(code)

    def get_code(self) -> str:
        return self.text_edit.toPlainText()

    def _on_apply_clicked(self):
        self.applied.emit(self.get_code())

try:
    from ECD.dxf_generator import export_dxf, render_doc_to_svg, render_doc_to_png, render_doc_to_pdf
    from ECD.mermaid_generator import MermaidGenerator
    from ECD.llm.ollama_client import OllamaClient, GenerationWorker
    from ECD.constants import COMPLEXITY_LEVELS
    from ECD.ValidationWorker import ValidationWorker, ValidationPanel, MermaidFixWorker
except ImportError:
    from dxf_generator import export_dxf, render_doc_to_svg, render_doc_to_png, render_doc_to_pdf
    from mermaid_generator import MermaidGenerator
    from llm.ollama_client import OllamaClient, GenerationWorker
    from constants import COMPLEXITY_LEVELS
    from ValidationWorker import ValidationWorker, ValidationPanel, MermaidFixWorker

class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.generator = MermaidGenerator()
        self.current_parsed_data = None
        self.original_parsed_data = None
        self._current_mermaid_code = ""
        self.current_doc = None
        self.current_svg = ""
        self._build_ui()
        self._show_welcome()
        self._last_prompt = ""
        self._validation_worker = None
        self._gen_worker = None
        self._fix_worker = None
        self._is_regex_fallback = False

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.stacked_widget = QStackedWidget()
        lay.addWidget(self.stacked_widget, 1)  # stretch=1: diagram gets all available space

        self.welcome_widget = WelcomeWidget()
        self.stacked_widget.addWidget(self.welcome_widget)

        self.loading_widget = LoadingWidget()
        self.stacked_widget.addWidget(self.loading_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #ffffff; border: none;")

        self.svg_widget = SvgPreviewWidget()
        self.scroll_area.setWidget(self.svg_widget)
        self.stacked_widget.addWidget(self.scroll_area)

        # Lightweight stub — stores mermaid code for .mmd export / get_current_mermaid_code
        # without rendering any UI.  A full interactive editor will be added in v2.
        self.code_panel = type('_CodeStub', (), {
            '_code': '',
            'set_code': lambda self, c: setattr(self, '_code', c),
            'get_code': lambda self: self._code,
            'setVisible': lambda self, v: None,
        })()

        self.validation_panel = ValidationPanel()
        lay.addWidget(self.validation_panel)
        # "Fix Issues" button in the panel triggers auto-correction using stored findings
        self.validation_panel.fixRequested.connect(
            lambda: self._on_validation_issues_found(self.validation_panel._current_findings)
        )

    def closeEvent(self, event):
        if self._validation_worker is not None and self._validation_worker.isRunning():
            self._validation_worker.quit()
            self._validation_worker.wait(5000)

        super().closeEvent(event)


    def _show_welcome(self):
        """Display a branded welcome screen before any diagram is generated."""
        # code_panel is a no-op stub; nothing to hide
        self.stacked_widget.setCurrentWidget(self.welcome_widget)


    def _show_loading(self):
        """Replace the canvas with an animated loading screen while generating."""
        self.stacked_widget.setCurrentWidget(self.loading_widget)


    # ── Async generation (non-blocking) ───────────────────────────────────────

    def generate_from_prompt(self, prompt_text, complexity_level="Neutral"):
        """Kick off diagram generation asynchronously so the UI stays responsive."""
        prompt_text = prompt_text.strip()
        if not prompt_text:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            return False

        # Cancel any in-flight generation worker
        if getattr(self, "_gen_worker", None) is not None:
            if self._gen_worker.isRunning():
                self._gen_worker.requestInterruption()
                self._gen_worker.quit()
                self._gen_worker.wait(2000)
            self._gen_worker.deleteLater()
            self._gen_worker = None

        self._is_regex_fallback = False
        self._show_loading()
        self._pending_prompt     = prompt_text
        self._pending_complexity = complexity_level

        self._gen_worker = GenerationWorker(prompt_text, complexity_level, self.generator)
        self._gen_worker.finished.connect(self._on_llm_finished)
        self._gen_worker.failed.connect(self._on_llm_failed)
        self._gen_worker.start()
        return True   # returns immediately; diagram arrives via signal

    def _on_llm_failed(self, error_msg: str):
        """LLM unavailable — fall back to fast regex parser on the main thread."""
        print(f"LLM parsing failed, using regex fallback: {error_msg}")
        self._is_regex_fallback = True
        try:
            parsed_data = self.generator.parse_prompt(
                self._pending_prompt, self._pending_complexity)
            self._finalise_generation(parsed_data, self._pending_prompt, self._pending_complexity)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")

    def _on_llm_finished(self, parsed_data: dict):
        """Called on the main thread once the background LLM call succeeds."""
        self._is_regex_fallback = False
        prompt_text      = self._pending_prompt
        complexity_level = self._pending_complexity
        try:
            comp_ids = [c for c, _ in parsed_data["components"]]
            lang     = parsed_data.get("language", self.generator.detect_language(prompt_text))
            voltage  = parsed_data.get("voltage", "230V / 415V")

            # Safety minimum
            if "supply" not in comp_ids:
                parsed_data["components"].insert(0, (
                    "supply",
                    self.generator.components_map["main incoming supply"][lang].replace("230V / 415V", voltage)
                ))
            explicit_no_breaker = any(
                p in prompt_text.lower()
                for p in ["no breaker", "direct connection", "no maincb"])
            if "maincb" not in comp_ids and not explicit_no_breaker:
                parsed_data["components"].insert(1, (
                    "maincb", self.generator.components_map["main breaker"][lang]))

            # Complexity filtering
            prompt_lower = prompt_text.lower()
            COMPONENT_KEYWORDS = {
                "rcd":  ["rcd", "residual current", "rcbo", "earth fault"],
                "nbar": ["neutral bar", "neutral link"],
                "ebar": ["earth bar", "earth terminal"],
                "bus":  ["busbar", "bus bar", "copper bar"],
            }
            def prompt_mentions(cid):
                return any(kw in prompt_lower for kw in COMPONENT_KEYWORDS.get(cid, []))

            if complexity_level != "Neutral":
                allowed_ids = set(COMPLEXITY_LEVELS[complexity_level]["components"])
                allow_outcb = COMPLEXITY_LEVELS[complexity_level].get("allow_outcb", False)
            else:
                allowed_ids = set(c for c, _ in parsed_data["components"])
                allow_outcb = True

            try:
                from ECD.pin_model import get_base_type
            except ImportError:
                from pin_model import get_base_type

            parsed_data["components"] = [
                (c, l) for c, l in parsed_data["components"]
                if c in allowed_ids
                or (allow_outcb and get_base_type(c) == "outcb")
                or prompt_mentions(c)
            ]

            # Backfill defaults for non-Neutral modes
            if complexity_level != "Neutral":
                explicit_exclusions = {
                    "rcd":    ["no rcd", "no residual", "no earth fault"],
                    "nbar":   ["no neutral"],
                    "ebar":   ["no earth", "no ground"],
                    "bus":    ["no busbar", "no bus"],
                    "maincb": ["no breaker", "direct connection", "no maincb"],
                }
                current_ids = {c for c, _ in parsed_data["components"]}
                defaults    = self.generator.get_default_components(lang, voltage, complexity_level)
                for cid, lbl in defaults:
                    if cid not in current_ids and get_base_type(cid) != "outcb":
                        if not any(ex in prompt_lower for ex in explicit_exclusions.get(cid, [])):
                            parsed_data["components"].append((cid, lbl))

            if complexity_level == "Detailed":
                if not any(get_base_type(c) == "outcb" for c, _ in parsed_data["components"]):
                    generic_label = self.generator.components_map["outgoing mcbs"][lang]
                    parsed_data["components"].insert(-1, ("outcb_1", generic_label))

            # Force inclusion of nbar/ebar/bus based on flags and outgoing breakers (critical for correctness and validation)
            current_ids = {c for c, _ in parsed_data["components"]}
            has_outcb = any(get_base_type(c) == "outcb" for c, _ in parsed_data["components"])
            if parsed_data.get("flags", {}).get("show_neutral") and "nbar" not in current_ids:
                parsed_data["components"].append(("nbar", self.generator.components_map["neutral bar"][lang]))
                current_ids.add("nbar")
            if parsed_data.get("flags", {}).get("show_earth") and "ebar" not in current_ids:
                parsed_data["components"].append(("ebar", self.generator.components_map["earth bar"][lang]))
                current_ids.add("ebar")
            if has_outcb and "bus" not in current_ids:
                parsed_data["components"].append(("bus", self.generator.components_map["busbar"][lang]))
                current_ids.add("bus")

            parsed_data["complexity"] = complexity_level
            parsed_data["prompt"]     = prompt_text
            parsed_data["language"]   = self.generator.detect_language(prompt_text)
            print("Parsed via LLM")
            self._finalise_generation(parsed_data, prompt_text, complexity_level)

        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")

    def _finalise_generation(self, parsed_data: dict, prompt_text: str, complexity_level: str):
        """Shared final step: build Mermaid, render HTML, kick off async validation."""
        self.current_parsed_data  = parsed_data
        self.original_parsed_data = parsed_data.copy()

        mermaid_code = self.generator.generate_mermaid_code(parsed_data)
        self._current_mermaid_code = mermaid_code
        self.code_panel.set_code(mermaid_code)
        # code_panel is a no-op stub; nothing to show

        try:
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self.svg_widget.load(QByteArray(self.current_svg.encode('utf-8')))
            self._reset_fit_mode()
            self.stacked_widget.setCurrentWidget(self.scroll_area)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Render Error", f"Failed to render DXF preview:\n\n{e}")

        if self.parent_window and hasattr(self.parent_window, "status"):
            lang_name = "English" if parsed_data.get("language") == "en" else "Japanese"
            gen_source = "Regex Fallback" if getattr(self, "_is_regex_fallback", False) else "LLM"
            self.parent_window.status.showMessage(
                f"Diagram generated via {gen_source} ({lang_name}, {complexity_level}), "
                f"{len(parsed_data.get('components', []))} components. "
                "Drag boxes · Double-click text · Edit code below.", 6000)

        # Re-enable the sidebar Reset button
        if self.parent_window and hasattr(self.parent_window, "sidebar"):
            self.parent_window.sidebar.reset_btn.setEnabled(True)

        self._last_prompt = prompt_text
        self._run_validation(prompt_text, parsed_data)

    # ─────────────────────────────────────────────────────────────────────────
    def _on_native_code_applied(self, new_code: str):
        self._current_mermaid_code = new_code
        try:
            from ECD.dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        except ImportError:
            from dxf_generator import parse_mermaid_sequence, normalize_for_dxf

        try:
            nodes, edges = parse_mermaid_sequence(new_code)
            parsed_data = normalize_for_dxf(nodes, edges)
            # Preserve metadata
            if self.current_parsed_data:
                parsed_data["flags"] = self.current_parsed_data.get("flags", {})
                parsed_data["voltage"] = self.current_parsed_data.get("voltage", "")
                parsed_data["language"] = self.current_parsed_data.get("language", "en")
                parsed_data["complexity"] = self.current_parsed_data.get("complexity", "Standard")
                parsed_data["prompt"] = self.current_parsed_data.get("prompt", self._last_prompt)
            self.current_parsed_data = parsed_data
            
            # Re-generate DXF & SVG natively and show in SVG preview
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self.svg_widget.load(QByteArray(self.current_svg.encode('utf-8')))
            self._reset_fit_mode()
            self.stacked_widget.setCurrentWidget(self.scroll_area)
            
            # Re-run validation on the new code
            prompt = self.current_parsed_data.get("prompt", self._last_prompt) \
                    if self.current_parsed_data else self._last_prompt
            self._run_validation(prompt, self.current_parsed_data)
            
            if self.parent_window and hasattr(self.parent_window, 'status'):
                self.parent_window.status.showMessage("✓ Diagram updated from edited code", 3000)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Invalid Mermaid Code", f"Could not parse edited Mermaid code:\n\n{e}")

    def refresh_diagram(self):
        if not self.current_parsed_data:
            return
        try:
            mc = self.generator.generate_mermaid_code(self.current_parsed_data)
            self._current_mermaid_code = mc
            self.code_panel.set_code(mc)
            self.current_doc = export_dxf(self.current_parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self.svg_widget.load(QByteArray(self.current_svg.encode('utf-8')))
            self.stacked_widget.setCurrentWidget(self.scroll_area)
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", str(e))

    def _run_validation(self, prompt: str, parsed_data: dict):
        self.validation_panel.show_loading()

        if self._validation_worker is not None:
            if self._validation_worker.isRunning():
                self._validation_worker.requestInterruption()
                self._validation_worker.quit()
                self._validation_worker.wait(3000)
            self._validation_worker.deleteLater()
            self._validation_worker = None

        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"

        self._validation_worker = ValidationWorker(prompt, parsed_data, complexity)
        self._validation_worker.validationComplete.connect(self._on_validation_complete)
        self._validation_worker.findingsReady.connect(self.validation_panel.set_findings)
        # ← findingsReady no longer connected to _on_validation_issues_found here
        self._validation_worker.start()

    def _on_validation_complete(self, text: str, has_issues: bool):
        # If fallback was used for generation, prepend a warning to the findings
        if getattr(self, "_is_regex_fallback", False):
            warning_text = "⚠️ [FALLBACK WARNING] The diagram was generated using the local regex fallback parser because the Groq LLM model was unavailable (e.g. rate limit exceeded, API offline, or network error). Output may be incomplete or lack fine-grained electrical connections."
            if "FINDINGS:" in text:
                parts = text.split("FINDINGS:")
                # Prepend the fallback warning to findings bullet list
                text = f"{parts[0]}FINDINGS:\n- {warning_text}\n{parts[1]}"
            else:
                text = f"{text}\nFINDINGS:\n- {warning_text}"
            has_issues = True
            
        self.validation_panel.show_result(text, has_issues)


    def _on_validation_issues_found(self, findings: list):
        """
        Called when the user clicks Fix Issues.
    
        Spawns MermaidFixWorker (LLM #3) which receives the current raw Mermaid
        code and the validation findings, then returns a corrected Mermaid string.
    
        Rules enforced inside the worker:
        - NEVER removes existing participants or arrows (preserves complexity-level
        components the old keyword fixer could not handle).
        - ONLY adds what is needed to resolve each finding.
        - Returns the full corrected sequenceDiagram code directly.
        """
        if not findings:
            return
    
        # Guard: cancel any previous fix worker still running
        if self._fix_worker is not None:
            if self._fix_worker.isRunning():
                self._fix_worker.quit()
                self._fix_worker.wait(3000)
            self._fix_worker.deleteLater()
            self._fix_worker = None
    
        # Read the live Mermaid code (reflects any user edits in the code editor)
        current_code = self._current_mermaid_code
        if not current_code:
            return
    
        prompt     = self.current_parsed_data.get("prompt", self._last_prompt) \
                    if self.current_parsed_data else self._last_prompt
        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"
    
        # Show "Applying fixes…" state in the panel immediately
        self.validation_panel.show_fixing()
    
        # Create and wire the fix worker
        self._fix_worker = MermaidFixWorker(current_code, findings, prompt, complexity)
        self._fix_worker.fixComplete.connect(self._on_fix_complete)
        self._fix_worker.fixFailed.connect(self._on_fix_failed)
        self._fix_worker.start()
    
    
    def _on_fix_complete(self, fixed_code: str):
        """Render the LLM-corrected Mermaid code and re-run validation."""
        self._current_mermaid_code = fixed_code
        self.code_panel.set_code(fixed_code)
    
        # Parse the corrected Mermaid code back to parsed_data
        try:
            from ECD.dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        except ImportError:
            from dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        try:
            nodes, edges = parse_mermaid_sequence(fixed_code)
            parsed_data = normalize_for_dxf(nodes, edges)
            # Preserve flags and voltage
            if self.current_parsed_data:
                parsed_data["flags"] = self.current_parsed_data.get("flags", {})
                parsed_data["voltage"] = self.current_parsed_data.get("voltage", "")
                parsed_data["language"] = self.current_parsed_data.get("language", "en")
                parsed_data["complexity"] = self.current_parsed_data.get("complexity", "Standard")
                parsed_data["prompt"] = self.current_parsed_data.get("prompt", self._last_prompt)
            self.current_parsed_data = parsed_data
            
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self.svg_widget.load(QByteArray(self.current_svg.encode('utf-8')))
            self.stacked_widget.setCurrentWidget(self.scroll_area)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Fix Render Error", f"Failed to render corrected diagram:\n\n{e}")
    
        # Clear stored findings — they've been consumed
        self.validation_panel._current_findings = []
        self.validation_panel.fix_btn.setEnabled(False)
    
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(
                "✓ Diagram patched by LLM — re-validating…", 4000
            )
    
        # Re-run validation for display only.
        # findingsReady is NOT reconnected to _on_validation_issues_found here,
        # so there is no fix loop — only show_result and set_findings are connected.
        prompt = self.current_parsed_data.get("prompt", self._last_prompt) \
                if self.current_parsed_data else self._last_prompt
        self._run_validation(prompt, self.current_parsed_data)
    
    
    def _on_fix_failed(self, error_msg: str):
        """Surface the error in the validation panel without touching the diagram."""
        self.validation_panel.show_fix_error(error_msg)
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(f"Fix failed: {error_msg[:80]}", 5000)
 
    
    def zoom_in(self):
        self.svg_widget.scale_factor = min(self.svg_widget.scale_factor * 1.25, 5.0)
        self._apply_zoom()

    def zoom_out(self):
        new_scale = self.svg_widget.scale_factor / 1.25
        if new_scale < 1.05:
            new_scale = 1.0
        self.svg_widget.scale_factor = max(new_scale, 0.2)
        self._apply_zoom()

    def reset_zoom(self):
        self.svg_widget.scale_factor = 1.0
        self._apply_zoom()

    def _reset_fit_mode(self):
        """Restore fit-to-view mode (called on new generation / code apply)."""
        self.svg_widget.scale_factor = 1.0
        self.svg_widget.setMinimumSize(0, 0)
        self.svg_widget.setMaximumSize(16777215, 16777215)
        self.scroll_area.setWidgetResizable(True)
        self.svg_widget.update()

    def _apply_zoom(self):
        """Switch between fit-to-view and scrollable-zoom modes."""
        zf = self.svg_widget.scale_factor
        if zf <= 1.0:
            # Fit-to-view: widget fills viewport, SVG scales to fit
            self.svg_widget.setMinimumSize(0, 0)
            self.svg_widget.setMaximumSize(16777215, 16777215)
            self.scroll_area.setWidgetResizable(True)
        else:
            # Zoomed: widget sized larger than viewport so scrollbars appear
            self.scroll_area.setWidgetResizable(False)
            vp = self.scroll_area.viewport().size()
            sz = self.svg_widget.renderer.defaultSize()
            if not sz.isEmpty() and vp.height() > 0:
                fit_scale = min(vp.width() / sz.width(), vp.height() / sz.height())
                w = int(sz.width() * fit_scale * zf)
                h = int(sz.height() * fit_scale * zf)
                self.svg_widget.setFixedSize(w, h)
        self.svg_widget.update()

    def get_current_mermaid_code(self) -> str:
        return self.code_panel.get_code() or self._current_mermaid_code

    # ── SVG Export ────────────────────────────────────────────────────────────
    def export_svg(self, file_path: str, on_done=None):
        try:
            if not self.current_svg:
                raise ValueError("No generated SVG found in memory.")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.current_svg)
            if on_done:
                on_done(True, f"✓ SVG saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"SVG save error: {e}")

    # ── PDF Export ────────────────────────────────────────────────────────────
    def export_pdf(self, file_path: str, on_done=None):
        try:
            if not self.current_doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_pdf(self.current_doc, file_path)
            if on_done:
                on_done(True, f"✓ PDF saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"PDF save error: {e}")

    # ── SVG-only PNG Export (diagram only, no UI chrome) ─────────────────────
    def export_svg_as_png(self, file_path: str, on_done=None):
        try:
            if not self.current_doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_png(self.current_doc, file_path)
            if on_done:
                on_done(True, f"✓ PNG saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"PNG save error: {e}")