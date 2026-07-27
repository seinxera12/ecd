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
parsed = gen.parse_prompt("Distribution panel with main breaker, RCD, and 5 branch circuit breakers with lamps.", "Standard")

canvas.current_parsed_data = parsed
canvas.original_parsed_data = parsed.copy()

doc = export_dxf(parsed, None)
canvas.svg_widget.load_document(doc, {})

# Render scene to QImage
scene = canvas.svg_widget.scene
rect = scene.sceneRect()

img_width = int(rect.width() * 3.0)
img_height = int(rect.height() * 3.0)

image = QImage(QSize(img_width, img_height), QImage.Format.Format_ARGB32)
image.fill(0xFF212830)  # Navy slate background

painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
scene.render(painter, target=image.rect(), source=rect)
painter.end()

out_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\74378425-7dcb-45df-9acb-201ab2ece057"
out_path = os.path.join(out_dir, "wire_rendering_fixed.png")
image.save(out_path)
print(f"Saved rendered scene preview to: {out_path}")
