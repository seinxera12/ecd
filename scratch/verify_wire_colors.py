import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from ECD.diagram_canvas import DiagramCanvas
from ECD.mermaid_generator import MermaidGenerator
from ECD.dxf_generator import export_dxf

app = QApplication.instance() or QApplication([])

canvas = DiagramCanvas()
gen = MermaidGenerator()

# 1. Single phase panel with neutral and earth
parsed_1ph = gen.parse_prompt("Distribution panel with main breaker, RCD, and 3 branch circuit breakers with lamps.", "Standard")
canvas.current_parsed_data = parsed_1ph
canvas.original_parsed_data = parsed_1ph.copy()
doc_1ph = export_dxf(parsed_1ph, None)
canvas.svg_widget.load_document(doc_1ph, {})

rect = canvas.svg_widget.scene.sceneRect()
image = QImage(QSize(int(rect.width() * 3.0), int(rect.height() * 3.0)), QImage.Format.Format_ARGB32)
image.fill(0xFF212830)
painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
canvas.svg_widget.scene.render(painter, target=image.rect(), source=rect)
painter.end()

out_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\74378425-7dcb-45df-9acb-201ab2ece057"
image.save(os.path.join(out_dir, "colors_1phase_preview.png"))

# 2. Three phase panel with L1, L2, L3 (Red, Yellow, Orange)
parsed_3ph = gen.parse_prompt("415V three-phase panel with main breaker, RCD, and 3-phase motor", "Standard")
canvas.current_parsed_data = parsed_3ph
canvas.original_parsed_data = parsed_3ph.copy()
doc_3ph = export_dxf(parsed_3ph, None)
canvas.svg_widget.load_document(doc_3ph, {})

rect_3ph = canvas.svg_widget.scene.sceneRect()
image_3ph = QImage(QSize(int(rect_3ph.width() * 3.0), int(rect_3ph.height() * 3.0)), QImage.Format.Format_ARGB32)
image_3ph.fill(0xFF212830)
painter_3ph = QPainter(image_3ph)
painter_3ph.setRenderHint(QPainter.RenderHint.Antialiasing)
canvas.svg_widget.scene.render(painter_3ph, target=image_3ph.rect(), source=rect_3ph)
painter_3ph.end()

image_3ph.save(os.path.join(out_dir, "colors_3phase_preview.png"))
print("Saved color previews successfully.")
