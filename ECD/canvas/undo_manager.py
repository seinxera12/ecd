"""
Undo/Redo Manager for Per-Symbol & Group Editing Canvas.
Provides a single global undo stack for managing diagram edit history.
"""

from PySide6.QtGui import QUndoStack, QUndoCommand
from PySide6.QtCore import QObject, Signal


class UndoManager(QObject):
    """Single global Undo/Redo stack manager for the diagram editor."""
    
    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack = QUndoStack(self)
        self._stack.canUndoChanged.connect(self.can_undo_changed.emit)
        self._stack.canRedoChanged.connect(self.can_redo_changed.emit)

    def push(self, command: QUndoCommand):
        """Push a completed editing command onto the undo stack."""
        if command:
            self._stack.push(command)

    def undo(self):
        """Undo the last editing command."""
        if self._stack.canUndo():
            self._stack.undo()

    def redo(self):
        """Redo the last undone command."""
        if self._stack.canRedo():
            self._stack.redo()

    def clear(self):
        """Clear all undo/redo history and start a new editing session."""
        self._stack.clear()

    def can_undo(self) -> bool:
        return self._stack.canUndo()

    def can_redo(self) -> bool:
        return self._stack.canRedo()

    @property
    def count(self) -> int:
        return self._stack.count()


class DictStateCommand(QUndoCommand):
    """
    Generic undo command that restores a dictionary key/value pair 
    or position/text override state on undo/redo.
    """
    
    def __init__(self, description: str, apply_fn, undo_fn):
        super().__init__(description)
        self._apply_fn = apply_fn
        self._undo_fn = undo_fn
        self._first_exec = True

    def redo(self):
        if self._first_exec:
            self._first_exec = False
            return
        if self._apply_fn:
            self._apply_fn()

    def undo(self):
        if self._undo_fn:
            self._undo_fn()
