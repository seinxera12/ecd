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
            ("&Copy Mermaid Code","Ctrl+M", self.copy_mermaid),
            ("C&lear All",        "Ctrl+L", self.clear_all),
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

        help_m = mb.addMenu("&Help")
        ab = QAction("&About", self); ab.triggered.connect(self.show_about); help_m.addAction(ab)

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
                self.canvas.refresh_diagram()
                
                layout_overrides = data.get("layout_overrides", {})
                text_overrides = data.get("text_overrides", {})
                if layout_overrides or text_overrides:
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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"PNG export failed: {e}"
            self.status.showMessage(msg, 4000)
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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"SVG export failed: {e}"
            self.status.showMessage(msg, 4000)
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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"PDF export failed: {e}"
            self.status.showMessage(msg, 4000)
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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Downloaded", msg)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Edit / View actions ───────────────────────────────────────────────────

    def reset_diagram(self):  self.sidebar._reset()
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

    def show_about(self):
        QMessageBox.about(self, "About",
            "<h2>Electrical Distribution Diagram Generator</h2>"
            "<p>Version 3.0</p>"
            "<p>Generate electrical distribution diagrams from natural language.</p>"
            "<p><b>Export formats:</b></p>"
            "<ul>"
            "<li>PNG — full page or diagram-only</li>"
            "<li>SVG — scalable vector graphic (diagram only)</li>"
            "<li>PDF — A4 landscape via Qt print engine</li>"
            "<li>Mermaid code — .mmd text file</li>"
            "</ul>"
            "<p><b>Drag</b> participant boxes to reposition.<br>"
            "<p>Built with PySide6 · Mermaid.js</p>")

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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"KiCad export failed: {e}"
            self.status.showMessage(msg, 4000)
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
            self.status.showMessage(msg, 4000)
            QMessageBox.information(self, "Exported", msg)
        except Exception as e:
            msg = f"DXF export failed: {e}"
            self.status.showMessage(msg, 4000)
            QMessageBox.critical(self, "Export Error", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()