"""
ECD/canvas/symbol_item.py — Selectable, movable symbol item component for live diagram canvas.
"""
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsItem, QApplication
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QColor, QBrush
from ECD.canvas.text_item import EditableTextItem

class SymbolItem(QGraphicsItemGroup):
    def __init__(self, cid: str, parent_view):
        super().__init__()
        self.cid = str(cid)
        self.parent_view = parent_view
        self.is_locked = False
        self.base_x = 0.0
        self.base_y = 0.0
        self._drag_start_pos = None
        self._drag_threshold_exceeded = False
        self._initial_positions = {}

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setHandlesChildEvents(True)
        self.setZValue(1.0)

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.is_locked)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setZValue(100.0)
            else:
                self.setZValue(1.0)
            self.update()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.boundingRect()

        if self.isSelected():
            # 1. Blue dashed selection bounding box
            pen = QPen(QColor(0, 150, 255), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # 2. Draw Padlock icon ABOVE the blue outline only when locked AND selected
            if self.is_locked:
                painter.save()
                current_scale = self.scale()
                sf = 1.0 / current_scale if current_scale > 0.0 else 1.0

                tr_x = rect.right()
                tr_y = rect.top()

                # Position icon above top-right corner of blue selection box
                icon_w = 12.0 * sf
                icon_h = 12.0 * sf
                offset_x = tr_x - (icon_w / 2.0)
                offset_y = tr_y - (icon_h + 2.0 * sf)

                # Lock Body (rounded rectangle)
                body_w = 8.0 * sf
                body_h = 6.0 * sf
                body_x = offset_x + 2.0 * sf
                body_y = offset_y + 5.0 * sf

                lock_pen = QPen(QColor(229, 62, 62), 1.2 * sf)
                lock_pen.setCosmetic(True)
                painter.setPen(lock_pen)
                painter.setBrush(QBrush(QColor(229, 62, 62)))
                painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 1.0 * sf, 1.0 * sf)

                # Lock Shackle (arc loop on top)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                shackle_w = 5.0 * sf
                shackle_h = 5.0 * sf
                shackle_x = offset_x + 3.5 * sf
                shackle_y = offset_y + 1.0 * sf
                painter.drawArc(QRectF(shackle_x, shackle_y, shackle_w, shackle_h), 0, 180 * 16)

                painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.scenePos()
            self._drag_threshold_exceeded = False
            scene = self.scene()
            if scene:
                selected_items = [
                    item for item in scene.selectedItems()
                    if not getattr(item, "is_locked", False)
                ]
                if self not in selected_items and not self.is_locked:
                    selected_items.append(self)
                self._initial_positions = {item: item.pos() for item in selected_items}
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            delta_vec = event.scenePos() - self._drag_start_pos
            if not self._drag_threshold_exceeded:
                if delta_vec.manhattanLength() >= QApplication.startDragDistance():
                    self._drag_threshold_exceeded = True
                else:
                    return

            if self._drag_threshold_exceeded:
                moved_cids = set()
                for item, start_pos in self._initial_positions.items():
                    item.setPos(start_pos + delta_vec)
                    cid = getattr(item, "cid", None)
                    if cid:
                        moved_cids.add(cid)
                if moved_cids and hasattr(self.parent_view, "update_connected_wires"):
                    self.parent_view.update_connected_wires(moved_cids)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._drag_threshold_exceeded and getattr(self, "_initial_positions", None):
            moved_symbol_overrides = {}
            moved_symbol_initial = {}
            for item, start_pos in self._initial_positions.items():
                cid = getattr(item, "cid", None)
                if cid is not None:
                    bx = getattr(item, "base_x", 0.0)
                    by = getattr(item, "base_y", 0.0)
                    moved_symbol_overrides[cid] = [bx + item.pos().x(), by - item.pos().y()]
                    moved_symbol_initial[item] = start_pos
                elif hasattr(item, "name"):
                    old_p = start_pos
                    old_s = item.scale()
                    if hasattr(self.parent_view, "store_layout_override"):
                        self.parent_view.store_layout_override(item.name, item.pos(), item.scale(), old_p, old_s)
            if moved_symbol_overrides and hasattr(self.parent_view, "store_component_position_overrides"):
                self.parent_view.store_component_position_overrides(moved_symbol_overrides, moved_symbol_initial)
        self._drag_start_pos = None
        self._drag_threshold_exceeded = False

    def mouseDoubleClickEvent(self, event):
        click_pos = event.pos()
        for child in self.childItems():
            if isinstance(child, EditableTextItem) and child.contains(child.mapFromParent(click_pos)):
                child.start_editing()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)
