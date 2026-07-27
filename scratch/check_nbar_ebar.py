from PySide6.QtWidgets import QApplication
from ECD.diagram_canvas import DiagramCanvas
from ECD.mermaid_generator import MermaidGenerator
from ECD.dxf_generator import export_dxf

app = QApplication.instance() or QApplication([])

canvas = DiagramCanvas()
gen = MermaidGenerator()
parsed = gen.parse_prompt("Distribution panel with main breaker, RCD, and 3 branch circuit breakers with lamps.", "Standard")
doc = export_dxf(parsed, None)
canvas.svg_widget.load_document(doc, {})

print("Symbol items created:", list(canvas.svg_widget.symbol_items.keys()))

for cid in ("nbar", "ebar"):
    item = canvas.svg_widget.symbol_items.get(cid)
    if item:
        children = [type(c).__name__ for c in item.childItems()]
        print(f"Item '{cid}': base=({item.base_x}, {item.base_y}), children={children}")
        for c in item.childItems():
            if hasattr(c, "toPlainText"):
                print(f"   Text: '{c.toPlainText()}' at pos=({c.pos().x()}, {c.pos().y()})")
    else:
        print(f"Item '{cid}' NOT FOUND in symbol_items")
