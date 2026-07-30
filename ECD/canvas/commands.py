from PySide6.QtGui import QUndoCommand
from ECD.canvas.undo_manager import DictStateCommand

class MoveSymbolCommand(QUndoCommand):
    def __init__(self, canvas, old_positions: dict, new_positions: dict):
        super().__init__()
        self.canvas = canvas
        self.old_positions = old_positions
        self.new_positions = new_positions

    def undo(self):
        for cid, pos in self.old_positions.items():
            item = self.canvas.symbol_items.get(cid)
            if item:
                item.setPos(pos[0], pos[1])
        if hasattr(self.canvas, "update_connected_wires"):
            self.canvas.update_connected_wires(set(self.old_positions.keys()))

    def redo(self):
        for cid, pos in self.new_positions.items():
            item = self.canvas.symbol_items.get(cid)
            if item:
                item.setPos(pos[0], pos[1])
        if hasattr(self.canvas, "update_connected_wires"):
            self.canvas.update_connected_wires(set(self.new_positions.keys()))

class EditLabelCommand(QUndoCommand):
    def __init__(self, text_item, old_text: str, new_text: str):
        super().__init__()
        self.text_item = text_item
        self.old_text = old_text
        self.new_text = new_text

    def undo(self):
        self.text_item.setPlainText(self.old_text)

    def redo(self):
        self.text_item.setPlainText(self.new_text)
