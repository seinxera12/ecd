import sys
import os
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    # Running as a PyInstaller-built exe
    app_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(app_dir, ".env"))
else:
    # Running from source
    app_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(app_dir, ".env"))
    load_dotenv(os.path.join(os.path.dirname(app_dir), ".env"))


import sys
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import json
import os
import math
import requests

from ECD.diagram_canvas import DiagramCanvas
from ECD.sidebar import Sidebar
from ECD.Kicad_exporter import export_kicad_schematic
from ECD.dxf_generator import export_dxf, render_doc_to_png, render_doc_to_pdf


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrical Distribution Diagram Generator")
        self.resize(1400, 900)
        self._build_menu()
        self._build_ui()
        self.installEventFilter(self)
        # In MainWindow.__init__ or wherever you set up the app:
        # app.aboutToQuit.connect(self.canvas.closeEvent)

    def _build_menu(self):
        mb = self.menuBar()

        file_m = mb.addMenu("&File")
        for label, shortcut, slot in [
            ("&New",          "Ctrl+N", self.new_diagram),
            ("&Open Diagram", "Ctrl+O", self.open_diagram),
            ("&Save Diagram", "Ctrl+S", self.save_diagram),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); file_m.addAction(a)
        file_m.addSeparator()

        # Export submenu with PNG, SVG, PDF, and Mermaid download
        exp = file_m.addMenu("&Export")
        for label, slot in [
            ("Export as PNG", self.export_as_png),
            ("Export as SVG",                self.export_as_svg),
            ("Export as PDF",                self.export_as_pdf),
            ("Download Mermaid Code (.mmd)", self.download_mermaid_code),
            ("Export as KiCad Schematic",    self.export_as_kicad),
            ("Export as DXF",               self.export_as_dxf),
            ("Export as JSON",               self.export_as_json),
        ]:
            a = QAction(label, self); a.triggered.connect(slot); exp.addAction(a)

        file_m.addSeparator()
        ex = QAction("E&xit", self); ex.setShortcut("Ctrl+Q"); ex.triggered.connect(self.close); file_m.addAction(ex)

        edit_m = mb.addMenu("&Edit")
        for label, shortcut, slot in [
            ("&Reset Diagram",    "Ctrl+R", self.reset_diagram),
            ("Toggle Symbol &Lock","Ctrl+L", self.toggle_symbol_lock),
            ("&Copy Mermaid Code","Ctrl+M", self.copy_mermaid),
            ("C&lear All",        "Ctrl+Shift+C", self.clear_all),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); edit_m.addAction(a)

        view_m = mb.addMenu("&View")
        for label, shortcut, slot in [
            ("Zoom &In",    "Ctrl++", self.zoom_in),
            ("Zoom &Out",   "Ctrl+-", self.zoom_out),
            ("&Reset Zoom", "Ctrl+0", self.reset_zoom),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut); a.triggered.connect(slot); view_m.addAction(a)
        view_m.addSeparator()
        # fs = QAction("&Fullscreen", self); fs.setShortcut("F11"); fs.triggered.connect(self.toggle_fullscreen); view_m.addAction(fs)
        fs = QAction("&Fullscreen", self)
        fs.setShortcut("F11")
        fs.triggered.connect(self.toggle_fullscreen)
        view_m.addAction(fs)

        settings_m = mb.addMenu("&Settings")
        app_settings_action = QAction("Application &Settings...", self)
        app_settings_action.setShortcut("Ctrl+,")
        app_settings_action.triggered.connect(self.open_settings_page)
        settings_m.addAction(app_settings_action)

        help_m = mb.addMenu("&Help")
        instr_act = QAction("&Instructions / User Guide", self)
        instr_act.setShortcut("F1")
        instr_act.triggered.connect(self.show_instructions)
        help_m.addAction(instr_act)
        help_m.addSeparator()
        ab = QAction("&About", self)
        ab.triggered.connect(self.show_about)
        help_m.addAction(ab)

    def _build_ui(self):
        central = QWidget()
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(12, 12, 12, 12)
        root_lay.setSpacing(16)

        self.sidebar = Sidebar(self)
        root_lay.addWidget(self.sidebar)

        canvas_wrap = QWidget()
        canvas_wrap.setObjectName("CanvasRoot")
        canvas_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        canvas_wrap.setStyleSheet(
            "#CanvasRoot{background:#f7fafc;border:1px solid #e2e8f0;border-radius:14px;}"
        )
        canvas_lay = QVBoxLayout(canvas_wrap)
        canvas_lay.setContentsMargins(14, 14, 14, 14)
        canvas_lay.setSpacing(0)

        self.canvas = DiagramCanvas(self)
        canvas_lay.addWidget(self.canvas)
        root_lay.addWidget(canvas_wrap, 1)

        self.setCentralWidget(central)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(
            "Ready — enter a prompt, choose detail level, and click Generate. "
        )

    def _require_diagram(self, action_name="export"):
        if not self.canvas.current_parsed_data:
            QMessageBox.warning(self, "No Diagram", f"Generate a diagram before you {action_name}.")
            return False
        return True

    def new_diagram(self):
        self.sidebar.prompt_text.clear()
        self.canvas.code_panel.set_code("")
        self.canvas._show_welcome()
        self.sidebar.reset_btn.setEnabled(False)
        self.status.showMessage("New diagram started", 2000)

    def _get_renders_default_path(self, filename: str) -> str:
        renders_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "renders", "demo")
        os.makedirs(renders_dir, exist_ok=True)
        return os.path.join(renders_dir, filename)

    def open_diagram(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Diagram", self._get_renders_default_path(""), "JSON Files (*.json)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Restore current_parsed_data
                data.pop("_mermaid_code", None)
                self.canvas.current_parsed_data = data
                self.canvas.original_parsed_data = data.copy()
                
                # Clear and render
                self.canvas.undo_manager.clear()
                self.canvas.refresh_diagram()
                
                layout_overrides = data.get("layout_overrides", {})
                text_overrides = data.get("text_overrides", {})
                comp_overrides = data.get("component_position_overrides", {})
                if layout_overrides or text_overrides or comp_overrides:
                    self.sidebar.reset_btn.setEnabled(True)
                else:
                    self.sidebar.reset_btn.setEnabled(False)
                    
                self.status.showMessage(f"Loaded diagram from {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load diagram:\n{e}")

    def save_diagram(self):
        if not self._require_diagram("save"): return
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", self._get_renders_default_path("diagram.json"), "JSON Files (*.json)")
        if path:
            data = dict(self.canvas.current_parsed_data)
            data["_mermaid_code"] = self.canvas.get_current_mermaid_code()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status.showMessage(f"Saved to {path}", 3000)

    def export_as_json(self):
        self.save_diagram()


    def export_as_png(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG (diagram only)", self._get_renders_default_path("diagram.png"), "PNG Files (*.png)")
        if not path: return
        self.status.showMessage("⏳ Preparing diagram-only PNG…", 0)
        try:
            doc = self.canvas.get_updated_document()
            if not doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_png(doc, path)
            msg = f"✓ PNG saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            msg = f"PNG export failed: {e}"
            self.status.showMessage(msg, 5000)
            QMessageBox.critical(self, "Export Error", msg)

    def export_as_svg(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", self._get_renders_default_path("diagram.svg"), "SVG Files (*.svg)")
        if not path: return
        self.status.showMessage("⏳ Exporting SVG…", 0)
        try:
            svg_str = self.canvas.get_updated_svg()
            if not svg_str:
                raise ValueError("No generated SVG found in memory.")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(svg_str)
            msg = f"✓ SVG saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            msg = f"SVG export failed: {e}"
            self.status.showMessage(msg, 5000)
            QMessageBox.critical(self, "Export Error", msg)

    def export_as_pdf(self):
        if not self._require_diagram(): return
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", self._get_renders_default_path("diagram.pdf"), "PDF Files (*.pdf)")
        if not path: return
        self.status.showMessage("⏳ Generating PDF…", 0)
        try:
            doc = self.canvas.get_updated_document()
            if not doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_pdf(doc, path)
            msg = f"✓ PDF saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            msg = f"PDF export failed: {e}"
            self.status.showMessage(msg, 5000)
            QMessageBox.critical(self, "Export Error", msg)
        

    def download_mermaid_code(self):
        """Save the current Mermaid code as a .mmd text file."""
        code = self.canvas.get_current_mermaid_code()
        if not code:
            QMessageBox.warning(self, "No Diagram", "Generate a diagram first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Download Mermaid Code", self._get_renders_default_path("diagram.mmd"),
            "Mermaid Files (*.mmd);;Text Files (*.txt);;All Files (*)"
        )
        if not path: return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            msg = f"✓ Mermaid code saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Edit / View actions ───────────────────────────────────────────────────

    def reset_diagram(self):  self.sidebar._reset()
    def toggle_symbol_lock(self):
        if hasattr(self.canvas, "toggle_symbol_lock"):
            self.canvas.toggle_symbol_lock()

    def zoom_in(self):
        self.canvas.zoom_in()

    def zoom_out(self):
        self.canvas.zoom_out()

    def reset_zoom(self):
        self.canvas.reset_zoom()

    def toggle_fullscreen(self):

        self.showNormal() if self.isFullScreen() else self.showFullScreen()


    # Exit fullscreen on ESC key
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key_Escape and self.isFullScreen():
                self.showNormal()
                return True
        return super().eventFilter(obj, event)

       




    def copy_mermaid(self):
        code = self.canvas.get_current_mermaid_code()
        if not code:
            QMessageBox.warning(self, "No Diagram", "No diagram to copy."); return
        QApplication.clipboard().setText(code)
        self.status.showMessage("Mermaid code copied to clipboard", 2000)

    def clear_all(self):
        if QMessageBox.question(self, "Clear All", "Clear prompt and diagram?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.new_diagram()

    def open_settings_page(self):
        """Open the Application Settings dialog."""
        try:
            from ECD.settings_page import SettingsPage
            from ECD.config_manager import get_config
        except ImportError:
            from settings_page import SettingsPage
            from config_manager import get_config

        dialog = SettingsPage(config_manager=get_config(), parent=self)
        dialog.exec()

    def show_instructions(self):
        """Display User Guide and Feature Manual in the unified Dark Slate card container theme."""
        dialog = QDialog(self)
        dialog.setWindowTitle("User Guide & Feature Manual")
        dialog.setFixedWidth(720)
        dialog.setFixedHeight(620)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a202c;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
                background-color: #3182ce;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        header_lbl = QLabel("User Guide & Feature Manual")
        header_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_lbl.setStyleSheet("color: #ffffff; margin-bottom: 0px;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel("Complete keyboard shortcuts, canvas controls, and export capabilities.")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #a0aec0; margin-bottom: 2px;")
        layout.addWidget(sub_lbl)

        card_box = QFrame()
        card_box.setStyleSheet("""
            QFrame {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 10px;
            }
        """)
        card_lay = QVBoxLayout(card_box)
        card_lay.setContentsMargins(16, 14, 16, 14)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                color: #ffffff;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a202c;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #4a5568;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #718096;
            }
        """)
        text_browser.setHtml("""
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; color: #e2e8f0; line-height: 1.6; font-size: 13px; }
            h2 { color: #63b3ed; border-bottom: 1px solid #4a5568; padding-bottom: 6px; margin-top: 6px; font-size: 15px; font-weight: 700; }
            h3 { color: #63b3ed; margin-top: 14px; margin-bottom: 6px; font-size: 13px; font-weight: 600; }
            table { width: 100%; border-collapse: collapse; margin-top: 6px; margin-bottom: 12px; }
            th { color: #ffffff; text-align: left; padding: 6px 8px; border-bottom: 2px solid #4a5568; background-color: #1a202c; font-weight: 700; }
            td { color: #e2e8f0; padding: 6px 8px; border-bottom: 1px solid #4a5568; }
            ul { color: #e2e8f0; margin-top: 4px; padding-left: 20px; }
            li { color: #e2e8f0; margin-bottom: 4px; }
            p { color: #e2e8f0; margin-top: 4px; margin-bottom: 8px; }
            .kbd { font-family: 'Consolas', monospace; font-weight: bold; color: #ffffff; background-color: #1a202c; padding: 2px 6px; border-radius: 4px; border: 1px solid #4a5568; }
            .desc { color: #a0aec0; margin-bottom: 12px; }
        </style>

        <h2>Keyboard & Mouse Controls</h2>
        <table>
            <tr><th>Action</th><th>Shortcut / Gesture</th><th>Description</th></tr>
            <tr><td><b>Move Symbol(s)</b></td><td><span class="kbd">Left Click + Drag</span></td><td>Click and drag any symbol or selected group of symbols to move them.</td></tr>
            <tr><td><b>Marquee Select</b></td><td><span class="kbd">Left Click + Drag (Empty Space)</span></td><td>Draw a selection box around multiple symbols to move or lock them together.</td></tr>
            <tr><td><b>Nudge Selection (1px)</b></td><td><span class="kbd">Left / Right / Up / Down</span></td><td>Nudge selected unlocked symbols or documentation sections by 1 pixel.</td></tr>
            <tr><td><b>Coarse Nudge (10px)</b></td><td><span class="kbd">Shift + Arrow Keys</span></td><td>Nudge selected unlocked symbols or sections by 10 pixels.</td></tr>
            <tr><td><b>Undo Action</b></td><td><span class="kbd">Ctrl + Z</span></td><td>Undo symbol moves, text edits, or layout position changes.</td></tr>
            <tr><td><b>Redo Action</b></td><td><span class="kbd">Ctrl + Shift + Z</span></td><td>Redo previously undone actions.</td></tr>
            <tr><td><b>Toggle Lock</b></td><td><span class="kbd">Ctrl + L</span></td><td>Lock selected symbols in place (locked symbols show an indicator dot and cannot be moved).</td></tr>
            <tr><td><b>Clear All</b></td><td><span class="kbd">Ctrl + Shift + C</span></td><td>Clear prompt input and active diagram canvas.</td></tr>
            <tr><td><b>Edit Text Label</b></td><td><span class="kbd">Double-Click Text</span></td><td>Edit any symbol or section text label in place. Press Enter to commit.</td></tr>
            <tr><td><b>Zoom View</b></td><td><span class="kbd">Mouse Wheel / Ctrl + / -</span></td><td>Zoom in and out centered under the cursor.</td></tr>
            <tr><td><b>Pan Canvas</b></td><td><span class="kbd">Right-Click / Middle-Click + Drag</span></td><td>Pan smoothly across the diagram canvas.</td></tr>
            <tr><td><b>Reset Zoom</b></td><td><span class="kbd">Ctrl + 0</span></td><td>Reset zoom scale back to 100% baseline.</td></tr>
            <tr><td><b>Toggle Fullscreen</b></td><td><span class="kbd">F11</span></td><td>Expand application to full screen.</td></tr>
        </table>

        <h2>Key Features & Capabilities</h2>
        <ul>
            <li><b>Reset Layout:</b> Restores all symbols to their default auto-aligned grid positions.</li>
            <li><b>Electrical Rule Check (ERC):</b> Three-tier deterministic rule engine (Presence, Consistency, Topology) validates diagram safety.</li>
            <li><b>Multi-Format Exporting:</b>
                <ul>
                    <li><b>DXF:</b> CAD drawing format compatible with AutoCAD and LibreCAD.</li>
                    <li><b>SVG:</b> Scalable Vector Graphics for web and vector embedding.</li>
                    <li><b>PNG:</b> High-resolution raster images (full sheet or cropped diagram).</li>
                    <li><b>PDF:</b> Standard A4 landscape printable document.</li>
                    <li><b>KiCad Schematic:</b> Export as native KiCad 10 schematic (.kicad_sch).</li>
                    <li><b>Mermaid.js:</b> Save text representation (.mmd).</li>
                </ul>
            </li>
            <li><b>Save / Load Project:</b> Save complete project state (.json) preserving custom layout overrides and text edits.</li>
        </ul>
        """)
        card_lay.addWidget(text_browser)
        layout.addWidget(card_box)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

        dialog.exec()

    def show_about(self):
        """Display About information in the unified Dark Slate card container theme."""
        dialog = QDialog(self)
        dialog.setWindowTitle("About Electrical Diagram Generator")
        dialog.setFixedWidth(540)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a202c;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
                background-color: #3182ce;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        header_lbl = QLabel("About Electrical Diagram Generator")
        header_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_lbl.setStyleSheet("color: #ffffff; margin-bottom: 0px;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel("AI-Powered Electrical CAD & Live Schematic Editor")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #a0aec0; margin-bottom: 2px;")
        layout.addWidget(sub_lbl)

        card_box = QFrame()
        card_box.setStyleSheet("""
            QFrame {
                background-color: #2d3748;
                border: 1px solid #4a5568;
                border-radius: 10px;
            }
        """)
        card_lay = QVBoxLayout(card_box)
        card_lay.setSpacing(12)
        card_lay.setContentsMargins(18, 16, 18, 16)

        card_title = QLabel("⚡ Electrical Diagram Generator v3.0")
        card_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        card_title.setStyleSheet("color: #63b3ed; border: none;")
        card_lay.addWidget(card_title)

        desc_lbl = QLabel("Generate, edit, validate, and export professional single-line and three-phase electrical distribution diagrams from natural language prompts.")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("border: none; color: #e2e8f0; font-size: 12px; line-height: 1.5;")
        card_lay.addWidget(desc_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #4a5568; border: none; max-height: 1px;")
        card_lay.addWidget(line)

        caps_title = QLabel("Key Capabilities:")
        caps_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        caps_title.setStyleSheet("color: #ffffff; border: none;")
        card_lay.addWidget(caps_title)

        caps_list = QLabel(
            "• <b>Interactive Canvas:</b> Move, lock, nudge, and edit symbol labels in real time.<br>"
            "• <b>Canonical Wire Router:</b> Automatic Manhattan right-angle routing & busbars.<br>"
            "• <b>Deterministic ERC Engine:</b> 3-tier validation (Presence, Consistency, Topology).<br>"
            "• <b>Universal CAD Exporter:</b> DXF, SVG, PNG, PDF, KiCad 10 (.kicad_sch), and Mermaid (.mmd)."
        )
        caps_list.setWordWrap(True)
        caps_list.setStyleSheet("border: none; color: #cbd5e0; font-size: 12px; line-height: 1.6;")
        card_lay.addWidget(caps_list)

        tech_lbl = QLabel("Built with Python, PySide6, and ezdxf.")
        tech_lbl.setFont(QFont("Segoe UI", 8))
        tech_lbl.setStyleSheet("border: none; color: #a0aec0; margin-top: 4px;")
        card_lay.addWidget(tech_lbl)

        layout.addWidget(card_box)

        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

        dialog.exec()

    def export_as_kicad(self):
        """Export current diagram as a KiCad 6+ schematic (.kicad_sch)."""
        if not self._require_diagram("export"): return
 
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export KiCad Schematic",
            self._get_renders_default_path("diagram.kicad_sch"),
            "KiCad Schematic Files (*.kicad_sch);;All Files (*)"
        )
        if not path:
            return
 
        try:
            export_kicad_schematic(self.canvas.current_parsed_data, path)
            msg = f"✓ KiCad schematic saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            msg = f"KiCad export failed: {e}"
            self.status.showMessage(msg, 5000)
            QMessageBox.critical(self, "Export Error", msg)

    def export_as_dxf(self):
        """Export current diagram as a DXF file."""
        if not self._require_diagram("export"): return
 
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DXF",
            self._get_renders_default_path("diagram.dxf"),
            "DXF Files (*.dxf);;All Files (*)"
        )
        if not path:
            return

        try:
            doc = self.canvas.get_updated_document()
            if not doc:
                raise ValueError("No generated DXF document found in memory.")
            doc.saveas(path)
            msg = f"✓ DXF file saved to {path}"
            self.status.showMessage(msg, 5000)
        except Exception as e:
            msg = f"DXF export failed: {e}"
            self.status.showMessage(msg, 5000)
            QMessageBox.critical(self, "Export Error", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()