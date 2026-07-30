"""
ECD/canvas/text_item.py — Editable text item component for live diagram canvas.
"""
from PySide6.QtWidgets import QGraphicsTextItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

class EditableTextItem(QGraphicsTextItem):
    def __init__(self, label_id: str, parent_group, parent_view):
        super().__init__()
        self.label_id = label_id
        self.parent_group = parent_group
        self.parent_view = parent_view
        self._is_editing = False

    def start_editing(self):
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, EditableTextItem) and item is not self and item._is_editing:
                    item.stop_editing()

        self._initial_text_before_edit = self.toPlainText()
        self._is_editing = True
        if self.parent_group:
            self.parent_group.setHandlesChildEvents(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)

    def stop_editing(self):
        if not self._is_editing:
            return
        self._is_editing = False
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if self.parent_group:
            self.parent_group.setHandlesChildEvents(True)
        new_text = self.toPlainText().strip()
        old_text = getattr(self, "_initial_text_before_edit", new_text)
        if new_text != old_text:
            self.parent_view.store_text_override(self.label_id, new_text, old_text)

    def focusOutEvent(self, event):
        self.stop_editing()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clearFocus()
            event.accept()
        else:
            super().keyPressEvent(event)
