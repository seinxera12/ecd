"""
ECD/canvas/selection_manager.py — Selection rectangle and selection utilities for diagram canvas.
"""
from PySide6.QtWidgets import QGraphicsRectItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor

class SelectionRectItem(QGraphicsRectItem):
    """Blue selection rectangle for highlighted items."""
    def __init__(self, rect, parent=None):
        super().__init__(rect, parent)
        pen = QPen(QColor(0, 150, 255), 1.5, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(Qt.BrushStyle.NoBrush)
