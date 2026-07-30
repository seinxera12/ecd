"""
Shim module forwarding all diagram_canvas classes to ECD.canvas.diagram_canvas.
"""
from ECD.canvas.diagram_canvas import *
from ECD.canvas.symbol_item import SymbolItem
from ECD.canvas.text_item import EditableTextItem
from ECD.canvas.selection_manager import SelectionRectItem
from ECD.canvas.commands import MoveSymbolCommand, EditLabelCommand