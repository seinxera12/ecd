# diagram_canvas.py
import json
import re
import math
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
import os

def route_diagram_wire(src_cid: str, dst_cid: str, wtype: str, qt_src: tuple, qt_dst: tuple) -> list:
    """Generate orthogonal wire points with neutral and earth daisy chain bus bar logic matching DXF layout."""
    try:
        from ECD.dxf_generator import route_wire_bend
    except ImportError:
        from dxf_generator import route_wire_bend

    if wtype == "N" and dst_cid.startswith("load"):
        qt_y_bend = qt_dst[1] + 10.0
        return [qt_src, (qt_src[0], qt_y_bend), (qt_dst[0], qt_y_bend), qt_dst]
    elif wtype == "E" and (dst_cid.startswith("load") or src_cid == "ebar"):
        qt_y_bend = qt_dst[1] + 22.0
        return [qt_src, (qt_src[0], qt_y_bend), (qt_dst[0], qt_y_bend), qt_dst]
    return route_wire_bend(qt_src, qt_dst)


class EditableTextItem(QGraphicsTextItem):
    def __init__(self, label_id: str, parent_group, parent_view):
        super().__init__()
        self.label_id = label_id
        self.parent_group = parent_group
        self.parent_view = parent_view
        self._is_editing = False
        
    def start_editing(self):
        # First, stop any other items currently in edit mode across the whole scene
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, EditableTextItem) and item is not self and item._is_editing:
                    item.stop_editing()
        
        self._initial_text_before_edit = self.toPlainText()
        self._is_editing = True
        # Disable parent group event handling so this item can receive mouse focus/clicks
        self.parent_group.setHandlesChildEvents(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
        
    def stop_editing(self):
        """Exit edit mode: clear selection highlight, disable text interaction,
        re-enable parent group event handling, and commit text override."""
        if not self._is_editing:
            return
        self._is_editing = False
        # Clear text selection highlight
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Re-enable parent group event handling
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


class DiagramGroupItem(QGraphicsItemGroup):
    def __init__(self, name: str, parent_view: QGraphicsView):
        super().__init__()
        self.name = name
        self.parent_view = parent_view
        
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setHandlesChildEvents(True)
        
        self.is_resizing = False
        self.active_handle = None
        self.drag_start_scale = 1.0
        self.local_anchor = None
        self.scene_anchor = None
        self.scene_start_pos = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.update()
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene:
                scene_rect = scene.sceneRect()
                s = self.scale()
                rect = self.boundingRect()
                
                L_TL = rect.topLeft()
                L_BR = rect.bottomRight()
                
                min_pos_x = scene_rect.left() - L_TL.x() * s
                max_pos_x = scene_rect.right() - L_BR.x() * s
                min_pos_y = scene_rect.top() - L_TL.y() * s
                max_pos_y = scene_rect.bottom() - L_BR.y() * s
                
                if min_pos_x <= max_pos_x:
                    new_x = max(min_pos_x, min(value.x(), max_pos_x))
                else:
                    new_x = scene_rect.left() - L_TL.x() * s
                    
                if min_pos_y <= max_pos_y:
                    new_y = max(min_pos_y, min(value.y(), max_pos_y))
                else:
                    new_y = scene_rect.top() - L_TL.y() * s
                    
                return QPointF(new_x, new_y)
        return super().itemChange(change, value)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            rect = self.boundingRect()
            
            # Cosmetic pen for selection bounding box
            pen = QPen(QColor(0, 150, 255), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
            
            # Cosmetic handles at the corners
            current_scale = self.scale()
            sf = 1.0 / current_scale if current_scale > 0.0 else 1.0
            h_sz = 8.0 * sf
            
            painter.setPen(QPen(QColor(0, 150, 255), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            
            corners = [
                rect.topLeft(),
                rect.topRight(),
                rect.bottomLeft(),
                rect.bottomRight()
            ]
            for pt in corners:
                painter.drawRect(pt.x() - h_sz / 2.0, pt.y() - h_sz / 2.0, h_sz, h_sz)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.pos()
            self._drag_start_scale = self.scale()

        if self.isSelected():
            rect = self.boundingRect()
            current_scale = self.scale()
            sf = 1.0 / current_scale if current_scale > 0.0 else 1.0
            tolerance = 6.0 * sf
            
            click_pos = event.pos()
            corners = {
                "top_left": (rect.topLeft(), rect.bottomRight()),
                "top_right": (rect.topRight(), rect.bottomLeft()),
                "bottom_left": (rect.bottomLeft(), rect.topRight()),
                "bottom_right": (rect.bottomRight(), rect.topLeft())
            }
            
            for handle_name, (corner_pt, anchor_pt) in corners.items():
                diff = click_pos - corner_pt
                dist = math.hypot(diff.x(), diff.y())
                if dist <= tolerance:
                    self.is_resizing = True
                    self.active_handle = handle_name
                    self.drag_start_scale = self.scale()
                    self.local_anchor = anchor_pt
                    self.scene_anchor = self.mapToScene(anchor_pt)
                    self.scene_start_pos = self.mapToScene(click_pos)
                    event.accept()
                    return
                    
        super().mousePressEvent(event)

    def calculate_max_scale(self, scene_anchor, local_anchor):
        scene = self.scene()
        if not scene:
            return 5.0
        scene_rect = scene.sceneRect()
        rect = self.boundingRect()
        
        corners = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight()
        ]
        
        max_scale = 5.0
        for c in corners:
            dx = c.x() - local_anchor.x()
            dy = c.y() - local_anchor.y()
            
            if abs(dx) > 0.001:
                if dx > 0:
                    s_limit = (scene_rect.right() - scene_anchor.x()) / dx
                else:
                    s_limit = (scene_rect.left() - scene_anchor.x()) / dx
                max_scale = min(max_scale, s_limit)
                
            if abs(dy) > 0.001:
                if dy > 0:
                    s_limit = (scene_rect.bottom() - scene_anchor.y()) / dy
                else:
                    s_limit = (scene_rect.top() - scene_anchor.y()) / dy
                max_scale = min(max_scale, s_limit)
                
        return max(0.2, max_scale)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            scene_pos = event.scenePos()
            
            start_diff = self.scene_start_pos - self.scene_anchor
            d_start = math.hypot(start_diff.x(), start_diff.y())
            
            curr_diff = scene_pos - self.scene_anchor
            d_curr = math.hypot(curr_diff.x(), curr_diff.y())
            
            if d_start > 0.1:
                new_scale = self.drag_start_scale * (d_curr / d_start)
                max_allowed = self.calculate_max_scale(self.scene_anchor, self.local_anchor)
                new_scale = min(new_scale, max_allowed)
                new_scale = max(0.2, min(new_scale, 5.0))
                
                # Invalidate old bounding region BEFORE changing geometry
                self.prepareGeometryChange()
                self.setScale(new_scale)
                
                # Adjust position to keep scene_anchor stationary
                new_pos_x = self.scene_anchor.x() - new_scale * self.local_anchor.x()
                new_pos_y = self.scene_anchor.y() - new_scale * self.local_anchor.y()
                self.setPos(new_pos_x, new_pos_y)
                
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        old_p = getattr(self, "_drag_start_pos", self.pos())
        old_s = getattr(self, "_drag_start_scale", self.scale())
        if self.is_resizing:
            self.is_resizing = False
            self.active_handle = None
            self.parent_view.store_layout_override(self.name, self.pos(), self.scale(), old_p, old_s)
            # Force full scene repaint to clear any stale paint residue
            if self.scene():
                self.scene().update()
            if self.parent_view.is_at_100_percent():
                self.parent_view.fit_to_view()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            self.parent_view.store_layout_override(self.name, self.pos(), self.scale(), old_p, old_s)
            if self.parent_view.is_at_100_percent():
                self.parent_view.fit_to_view()

    def mouseDoubleClickEvent(self, event):
        click_pos = event.pos()
        for child in self.childItems():
            if isinstance(child, EditableTextItem) and child.contains(child.mapFromParent(click_pos)):
                child.start_editing()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


class SymbolItem(QGraphicsItemGroup):
    """
    Represents an individual, movable, selectable symbol within the Main Diagram.
    Contains the symbol graphic and its permanently attached label.
    """
    def __init__(self, cid: str, parent_view: QGraphicsView):
        super().__init__()
        self.cid = str(cid)
        self.parent_view = parent_view
        self.is_locked = False
        self._drag_start_pos = None
        self._initial_positions = {}
        self._drag_threshold_exceeded = False

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
        if self.isSelected():
            pen = QPen(QColor(0, 150, 255), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())
        if self.is_locked:
            pen = QPen(QColor(229, 62, 62), 1.5)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(229, 62, 62)))
            rect = self.boundingRect()
            painter.drawRect(rect.left() + 2, rect.top() + 2, 6, 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.scenePos()
            self._drag_threshold_exceeded = False
            scene = self.scene()
            if scene:
                # Capture initial positions of all unlocked selected symbols for multi-drag (Q23)
                selected_symbols = [
                    item for item in scene.selectedItems()
                    if isinstance(item, SymbolItem) and not item.is_locked
                ]
                if self not in selected_symbols and not self.is_locked:
                    selected_symbols.append(self)
                self._initial_positions = {item: item.pos() for item in selected_symbols}
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            delta_vec = event.scenePos() - self._drag_start_pos
            # Enforce drag threshold (Q13)
            if not self._drag_threshold_exceeded:
                if delta_vec.manhattanLength() >= QApplication.startDragDistance():
                    self._drag_threshold_exceeded = True
                else:
                    return

            if self._drag_threshold_exceeded:
                # Multi-symbol drag: translate all unlocked selected symbols together, preserving relative spacing (Q23)
                moved_cids = set()
                for item, start_pos in self._initial_positions.items():
                    item.setPos(start_pos + delta_vec)
                    moved_cids.add(item.cid)
                # Live wire routing update during drag for connected wires only (Q12, Q21)
                self.parent_view.update_connected_wires(moved_cids)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._drag_threshold_exceeded and self._initial_positions:
            # Commit updated positions to component_position_overrides and record 1 undo action (Q10, Q17)
            moved_overrides = {}
            for item in self._initial_positions:
                bx = getattr(item, "base_x", 0.0)
                by = getattr(item, "base_y", 0.0)
                moved_overrides[item.cid] = [bx + item.pos().x(), by - item.pos().y()]
            self.parent_view.store_component_position_overrides(moved_overrides, self._initial_positions)
        self._drag_start_pos = None
        self._drag_threshold_exceeded = False

    def mouseDoubleClickEvent(self, event):
        click_pos = event.pos()
        # Double-clicking ONLY the label enters text-edit mode (Q3, Q16)
        for child in self.childItems():
            if isinstance(child, EditableTextItem) and child.contains(child.mapFromParent(click_pos)):
                child.start_editing()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


class SvgPreviewWidget(QGraphicsView):
    """QGraphicsView-based interactive viewer for the electrical diagram.
    Displays the diagram with individually selectable, movable symbols and 3 grouped doc sections.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas_parent = parent
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.baseline_scale = 1.0
        
        # Configure viewport anchors for cursor-centered zooming
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Rubber-band marquee selection configuration (intersection-based, direction invariant - Q1)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemBoundingRect)

        # Style to set navy/slate background matching export theme (#212830) and hide borders
        self.setBackgroundBrush(QBrush(QColor("#212830")))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Use FullViewportUpdate to prevent stale paint residue
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        self.group_items = {}
        self.symbol_items = {}
        self.selected_group = None
        self.scene.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, DiagramGroupItem)]
        newly_selected = None
        for item in selected:
            if item != self.selected_group:
                newly_selected = item
                break
                
        if newly_selected:
            if self.selected_group and self.selected_group != newly_selected:
                self.scene.blockSignals(True)
                self.selected_group.setSelected(False)
                self.scene.blockSignals(False)
            self.selected_group = newly_selected
        else:
            if not selected:
                self.selected_group = None

    def keyPressEvent(self, event):
        # Check if text is currently being edited in the scene
        focus_item = self.scene.focusItem()
        if isinstance(focus_item, EditableTextItem) or any(
            isinstance(item, EditableTextItem) and getattr(item, "_is_editing", False)
            for item in self.scene.items()
        ):
            super().keyPressEvent(event)
            return

        # Ctrl + L: toggle lock on all selected SymbolItems (Q5, Q14)
        if event.key() == Qt.Key.Key_L and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            selected = [item for item in self.scene.selectedItems() if isinstance(item, SymbolItem)]
            for item in selected:
                item.toggle_lock()
            event.accept()
            return

        # Ctrl + Z: Undo / Redo (Q6)
        if event.key() == Qt.Key.Key_Z and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if self.canvas_parent and hasattr(self.canvas_parent, "undo_manager"):
                    self.canvas_parent.undo_manager.redo()
            else:
                if self.canvas_parent and hasattr(self.canvas_parent, "undo_manager"):
                    self.canvas_parent.undo_manager.undo()
            event.accept()
            return

        # Arrow keys: Nudge selected unlocked symbols or section groups (Phase 2.1)
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            selected_symbols = [
                item for item in self.scene.selectedItems()
                if isinstance(item, SymbolItem) and not item.is_locked
            ]
            selected_groups = [
                item for item in self.scene.selectedItems()
                if isinstance(item, DiagramGroupItem)
            ]

            step = 10.0 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1.0
            dx, dy = 0.0, 0.0
            if event.key() == Qt.Key.Key_Left:
                dx = -step
            elif event.key() == Qt.Key.Key_Right:
                dx = step
            elif event.key() == Qt.Key.Key_Up:
                dy = -step
            elif event.key() == Qt.Key.Key_Down:
                dy = step

            if selected_symbols:
                initial_positions = {item: item.pos() for item in selected_symbols}
                moved_overrides = {}
                moved_cids = set()

                for item in selected_symbols:
                    new_pos = item.pos() + QPointF(dx, dy)
                    item.setPos(new_pos)
                    moved_cids.add(item.cid)
                    bx = getattr(item, "base_x", 0.0)
                    by = getattr(item, "base_y", 0.0)
                    moved_overrides[item.cid] = [bx + new_pos.x(), by - new_pos.y()]

                self.update_connected_wires(moved_cids)
                self.store_component_position_overrides(moved_overrides, initial_positions)
                event.accept()
                return

            if selected_groups:
                for item in selected_groups:
                    init_pos = item.pos()
                    new_pos = init_pos + QPointF(dx, dy)
                    self.store_layout_override(item.name, new_pos, item.scale(), init_pos, item.scale())
                event.accept()
                return

        # Disable Delete key for symbol items (Rule 8, Rule 9)
        if event.key() == Qt.Key.Key_Delete:
            event.ignore()
            return

        super().keyPressEvent(event)

    def store_layout_override(self, group_name: str, pos: QPointF, scale: float, old_pos: QPointF = None, old_scale: float = None):
        if not self.canvas_parent or not self.canvas_parent.current_parsed_data:
            return

        data = self.canvas_parent.current_parsed_data
        overrides = data.setdefault("layout_overrides", {})

        old_override = overrides.get(group_name)
        if old_pos is not None and old_scale is not None:
            px = old_pos.x() if hasattr(old_pos, "x") else old_pos[0]
            py = old_pos.y() if hasattr(old_pos, "y") else old_pos[1]
            prev_pos = [px, py]
            prev_scale = old_scale
        elif old_override:
            prev_pos = [old_override["position"][0], old_override["position"][1]]
            prev_scale = old_override.get("scale", 1.0)
        else:
            prev_pos = None
            prev_scale = 1.0

        nx = pos.x() if hasattr(pos, "x") else pos[0]
        ny = pos.y() if hasattr(pos, "y") else pos[1]
        new_pos = [nx, ny]
        new_scale = scale

        def apply_new():
            overrides[group_name] = {
                "position": new_pos,
                "scale": new_scale
            }
            item = self.group_items.get(group_name)
            if item:
                item.setPos(new_pos[0], new_pos[1])
                item.setScale(new_scale)

        def apply_old():
            if prev_pos is None:
                overrides.pop(group_name, None)
                item = self.group_items.get(group_name)
                if item:
                    item.setPos(0.0, 0.0)
                    item.setScale(1.0)
            else:
                overrides[group_name] = {
                    "position": prev_pos,
                    "scale": prev_scale
                }
                item = self.group_items.get(group_name)
                if item:
                    item.setPos(prev_pos[0], prev_pos[1])
                    item.setScale(prev_scale)

        from ECD.undo_manager import DictStateCommand
        cmd = DictStateCommand(f"Move/Resize Group '{group_name}'", apply_new, apply_old)
        if hasattr(self.canvas_parent, "undo_manager"):
            self.canvas_parent.undo_manager.push(cmd)

        overrides[group_name] = {
            "position": new_pos,
            "scale": new_scale
        }

        item = self.group_items.get(group_name)
        if item:
            item.setPos(new_pos[0], new_pos[1])
            item.setScale(new_scale)

        # Enable the reset button if it exists
        if hasattr(self.canvas_parent, "parent_window") and self.canvas_parent.parent_window:
            win = self.canvas_parent.parent_window
            if hasattr(win, "sidebar") and win.sidebar:
                win.sidebar.reset_btn.setEnabled(True)

    def store_text_override(self, label_id: str, new_text: str, old_text: str = None):
        if not self.canvas_parent or self.canvas_parent.current_parsed_data is None:
            return

        data = self.canvas_parent.current_parsed_data
        overrides = data.setdefault("text_overrides", {})

        old_override_val = overrides.get(label_id)

        # Find the text item displayed on canvas
        text_item = None
        if self.scene:
            for item in self.scene.items():
                if isinstance(item, EditableTextItem) and getattr(item, "label_id", None) == label_id:
                    text_item = item
                    break

        prev_displayed_text = old_text if old_text is not None else (text_item.toPlainText() if text_item else "")

        def apply_new():
            overrides[label_id] = new_text
            if self.scene:
                for item in self.scene.items():
                    if isinstance(item, EditableTextItem) and getattr(item, "label_id", None) == label_id:
                        item.setPlainText(new_text)

        def apply_old():
            if old_override_val is not None:
                overrides[label_id] = old_override_val
            else:
                overrides.pop(label_id, None)

            if self.scene:
                for item in self.scene.items():
                    if isinstance(item, EditableTextItem) and getattr(item, "label_id", None) == label_id:
                        item.setPlainText(prev_displayed_text)

        from ECD.undo_manager import DictStateCommand
        cmd = DictStateCommand(f"Edit Label '{label_id}'", apply_new, apply_old)
        if hasattr(self.canvas_parent, "undo_manager"):
            self.canvas_parent.undo_manager.push(cmd)

        overrides[label_id] = new_text
        if text_item:
            text_item.setPlainText(new_text)

        # Enable the reset button if it exists
        if hasattr(self.canvas_parent, "parent_window") and self.canvas_parent.parent_window:
            win = self.canvas_parent.parent_window
            if hasattr(win, "sidebar") and win.sidebar:
                win.sidebar.reset_btn.setEnabled(True)

    def store_component_position_overrides(self, overrides: dict, initial_positions: dict):
        if not self.canvas_parent or not self.canvas_parent.current_parsed_data:
            return

        data = self.canvas_parent.current_parsed_data
        comp_overrides = data.setdefault("component_position_overrides", {})

        old_states = {}
        new_states = {}
        old_pos_coords = {}

        for cid, pos in overrides.items():
            cid_str = str(cid)
            old_pos = comp_overrides.get(cid_str, {}).get("position")
            sym_item = self.symbol_items.get(cid_str)
            bx = getattr(sym_item, "base_x", 0.0) if sym_item else 0.0
            by = getattr(sym_item, "base_y", 0.0) if sym_item else 0.0

            init_p = initial_positions.get(cid_str)
            if not init_p:
                for item, p_val in initial_positions.items():
                    if getattr(item, "cid", None) == cid_str:
                        init_p = p_val
                        break
            if init_p:
                old_pos_coords[cid_str] = [bx + init_p.x(), by - init_p.y()]

            old_states[cid_str] = old_pos
            new_states[cid_str] = pos
            comp_overrides[cid_str] = {"position": pos}
            if sym_item:
                sym_item.setPos(pos[0] - bx, -(pos[1] - by))

        def apply_new():
            for cid, p in new_states.items():
                comp_overrides[cid] = {"position": p}
                item = self.symbol_items.get(cid)
                if item:
                    bx = getattr(item, "base_x", 0.0)
                    by = getattr(item, "base_y", 0.0)
                    item.setPos(p[0] - bx, -(p[1] - by))
            self.update_connected_wires(set(new_states.keys()))

        def apply_old():
            for cid, p in old_states.items():
                item = self.symbol_items.get(cid)
                if p is None:
                    comp_overrides.pop(cid, None)
                    if item:
                        item.setPos(0.0, 0.0)
                else:
                    comp_overrides[cid] = {"position": p}
                    if item:
                        bx = getattr(item, "base_x", 0.0)
                        by = getattr(item, "base_y", 0.0)
                        item.setPos(p[0] - bx, -(p[1] - by))
            self.update_connected_wires(set(old_states.keys()))

        from ECD.undo_manager import DictStateCommand
        cmd = DictStateCommand("Move Symbol(s)", apply_new, apply_old)
        if hasattr(self.canvas_parent, "undo_manager"):
            self.canvas_parent.undo_manager.push(cmd)

        if hasattr(self.canvas_parent, "parent_window") and self.canvas_parent.parent_window:
            win = self.canvas_parent.parent_window
            if hasattr(win, "sidebar") and win.sidebar:
                win.sidebar.reset_btn.setEnabled(True)

    def update_connected_wires(self, moved_cids: set):
        """Live-update only the wires connected to moved symbols during drag (Q12, Q21)."""
        if not hasattr(self, "wire_items") or not self.wire_items:
            return

        try:
            from ECD.pin_model import get_pin_position
        except ImportError:
            from pin_model import get_pin_position

        for wire_info in self.wire_items:
            src_cid = wire_info["src_cid"]
            dst_cid = wire_info["dst_cid"]

            if src_cid in moved_cids or dst_cid in moved_cids:
                src_item = self.symbol_items.get(src_cid)
                dst_item = self.symbol_items.get(dst_cid)

                if src_item:
                    src_pos = (src_item.base_x + src_item.pos().x(), src_item.base_y - src_item.pos().y())
                else:
                    src_pos = wire_info.get("src_default_pos", (0.0, 0.0))

                if dst_item:
                    dst_pos = (dst_item.base_x + dst_item.pos().x(), dst_item.base_y - dst_item.pos().y())
                else:
                    dst_pos = wire_info.get("dst_default_pos", (0.0, 0.0))

                try:
                    src_pin_pos = get_pin_position(src_cid, wire_info["src_pin"], src_pos, wire_info["phase_mode"])
                except Exception:
                    src_pin_pos = src_pos

                try:
                    dst_pin_pos = get_pin_position(dst_cid, wire_info["dst_pin"], dst_pos, wire_info["phase_mode"])
                except Exception:
                    dst_pin_pos = dst_pos

                qt_src = (src_pin_pos[0], -src_pin_pos[1])
                qt_dst = (dst_pin_pos[0], -dst_pin_pos[1])

                pts = route_diagram_wire(src_cid, dst_cid, wire_info["wire_type"], qt_src, qt_dst)

                path = QPainterPath()
                if pts:
                    path.moveTo(pts[0][0], pts[0][1])
                    for p in pts[1:]:
                        path.lineTo(p[0], p[1])
                wire_info["item"].setPath(path)

    def load_document(self, doc, layout_overrides: dict) -> bool:
        """Load ezdxf document as per-symbol objects and 3 documentation groups."""
        self.scene.clear()
        self.group_items.clear()
        self.symbol_items.clear()
        self.wire_items = []
        self.renderers = []  # Keep references to prevent premature garbage collection
        
        if not doc:
            return False
            
        try:
            from ezdxf.bbox import extents
        except ImportError:
            return False
            
        def aci_to_qcolor(aci: int) -> QColor:
            mapping = {
                1: QColor(215, 38, 56),    # Red / L1 (rich)
                2: QColor(220, 170, 0),    # Yellow / L2 (warm golden)
                3: QColor(0, 230, 100),    # Green / Neutral
                4: QColor(0, 210, 255),    # Cyan
                5: QColor(25, 90, 210),    # Darker Blue / Earth
                6: QColor(255, 0, 255),    # Magenta
                7: QColor(255, 255, 255),  # White
                30: QColor(220, 100, 0),   # Orange / L3 (rich)
                250: QColor(128, 128, 128) # Grey
            }
            return mapping.get(aci, QColor(255, 255, 255))
            
        try:
            from dxf_generator import get_group_graphics_and_text, get_per_symbol_graphics_and_text, render_entities_to_svg
        except ImportError:
            from ECD.dxf_generator import get_group_graphics_and_text, get_per_symbol_graphics_and_text, render_entities_to_svg
            
        # 1. Render Documentation Groups (Title Block, Legend, Load Schedule)
        doc_groups = ["title_block", "legend", "load_schedule"]
        for gname in doc_groups:
            graphics, text_ents = get_group_graphics_and_text(doc, gname)
            
            group_item = DiagramGroupItem(gname, self)
            self.scene.addItem(group_item)
            self.group_items[gname] = group_item
            
            override = layout_overrides.get(gname, {})
            pos_override = override.get("position")
            scale_override = override.get("scale", 1.0)
            
            if graphics:
                try:
                    bb = extents(graphics)
                    x_min, y_min = bb.extmin.x, bb.extmin.y
                    x_max, y_max = bb.extmax.x, bb.extmax.y
                    
                    svg_str = render_entities_to_svg(doc, graphics)
                    if svg_str:
                        svg_item = QGraphicsSvgItem()
                        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
                        self.renderers.append(renderer)
                        svg_item.setSharedRenderer(renderer)
                        
                        target_w = x_max - x_min
                        target_h = y_max - y_min
                        default_size = svg_item.boundingRect().size()
                        if default_size.width() > 0 and default_size.height() > 0:
                            scale_x = target_w / default_size.width()
                            scale_y = target_h / default_size.height()
                            transform = QTransform()
                            transform.scale(scale_x, scale_y)
                            svg_item.setTransform(transform)
                        
                        svg_item.setPos(x_min, -y_max)
                        group_item.addToGroup(svg_item)
                except Exception as ge:
                    print(f"Error rendering graphics for doc group {gname}: {ge}")
                    
            for tent in text_ents:
                align, p1, p2 = tent.get_placement()
                pos = p1 if align == 0 or p2 is None else p2
                
                label_id = getattr(tent, "label_id", None)
                if label_id:
                    text_item = EditableTextItem(label_id, group_item, self)
                else:
                    text_item = QGraphicsTextItem()
                text_item.setPlainText(tent.dxf.text)
                text_item.document().setDocumentMargin(0)
                
                font = QFont("Arial")
                font.setPointSizeF(tent.dxf.height)
                text_item.setFont(font)
                
                aci = tent.dxf.color
                if aci == 256 or aci is None:
                    try:
                        layer = doc.layers.get(tent.dxf.layer)
                        aci = layer.dxf.color
                    except Exception:
                        aci = 7
                text_item.setDefaultTextColor(aci_to_qcolor(aci))
                
                self.scene.addItem(text_item)
                
                fm = QFontMetricsF(font)
                ascent = fm.ascent()
                descent = fm.descent()

                width = text_item.boundingRect().width()
                height = text_item.boundingRect().height()
                
                align_val = align.value if hasattr(align, "value") else int(align)
                is_center = align_val in (2, 5, 8, 11, 14)
                is_right  = align_val in (3, 9, 12, 15)
                is_top    = align_val in (13, 14, 15)
                is_middle = align_val in (5, 10, 11, 12)
                is_bottom = align_val in (7, 8, 9)
                
                adj_x = pos.x
                if is_center:
                    adj_x -= width / 2.0
                elif is_right:
                    adj_x -= width
                    
                adj_y = -pos.y
                if is_top:
                    adj_y -= 0.0
                elif is_middle:
                    adj_y -= (ascent - descent) / 2.0
                elif is_bottom:
                    adj_y -= (ascent + descent)
                else:
                    adj_y -= ascent
                    
                text_item.setPos(adj_x, adj_y)
                group_item.addToGroup(text_item)
                
            if pos_override:
                group_item.setPos(pos_override[0], pos_override[1])
            if scale_override != 1.0:
                group_item.prepareGeometryChange()
                group_item.setScale(scale_override)

        # 2. Render Per-Symbol Items in Main Diagram
        symbol_map, (static_graphics, static_texts) = get_per_symbol_graphics_and_text(doc)
        comp_overrides = {}
        box_positions = getattr(doc, "box_positions", {})
        if self.canvas_parent and self.canvas_parent.current_parsed_data:
            comp_overrides = self.canvas_parent.current_parsed_data.get("component_position_overrides", {})

        for cid, (graphics, text_ents) in symbol_map.items():
            sym_item = SymbolItem(cid, self)
            self.scene.addItem(sym_item)
            self.symbol_items[cid] = sym_item

            init_base = box_positions.get(cid, (0.0, 0.0))
            sym_item.base_x = float(init_base[0])
            sym_item.base_y = float(init_base[1])

            if graphics:
                try:
                    bb = extents(graphics)
                    x_min, y_min = bb.extmin.x, bb.extmin.y
                    x_max, y_max = bb.extmax.x, bb.extmax.y

                    svg_str = render_entities_to_svg(doc, graphics)
                    if svg_str:
                        svg_item = QGraphicsSvgItem()
                        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
                        self.renderers.append(renderer)
                        svg_item.setSharedRenderer(renderer)

                        target_w = x_max - x_min
                        target_h = y_max - y_min
                        default_size = svg_item.boundingRect().size()
                        if default_size.width() > 0 and default_size.height() > 0:
                            scale_x = target_w / default_size.width()
                            scale_y = target_h / default_size.height()
                            transform = QTransform()
                            transform.scale(scale_x, scale_y)
                            svg_item.setTransform(transform)

                        svg_item.setPos(x_min, -y_max)
                        sym_item.addToGroup(svg_item)
                except Exception as se:
                    print(f"Error rendering symbol graphics for {cid}: {se}")

            for tent in text_ents:
                align, p1, p2 = tent.get_placement()
                pos = p1 if align == 0 or p2 is None else p2
                label_id = getattr(tent, "label_id", None)
                if label_id:
                    text_item = EditableTextItem(label_id, sym_item, self)
                else:
                    text_item = QGraphicsTextItem()
                text_item.setPlainText(tent.dxf.text)
                text_item.document().setDocumentMargin(0)
                font = QFont("Arial")
                font.setPointSizeF(tent.dxf.height)
                text_item.setFont(font)
                aci = tent.dxf.color or 7
                text_item.setDefaultTextColor(aci_to_qcolor(aci))
                self.scene.addItem(text_item)

                fm = QFontMetricsF(font)
                width = text_item.boundingRect().width()
                align_val = align.value if hasattr(align, "value") else int(align)
                adj_x = pos.x - (width / 2.0 if align_val in (2, 5, 8, 11, 14) else (width if align_val in (3, 9, 12, 15) else 0.0))
                adj_y = -pos.y - fm.ascent()
                text_item.setPos(adj_x, adj_y)
                sym_item.addToGroup(text_item)

            pos_ov = comp_overrides.get(cid, {}).get("position")
            if pos_ov and len(pos_ov) >= 2:
                delta_x = float(pos_ov[0]) - sym_item.base_x
                delta_y = -(float(pos_ov[1]) - sym_item.base_y)
                sym_item.setPos(delta_x, delta_y)

        # 3. Render Dynamic Netlist Wires for Live Drag Routing
        netlist = getattr(doc, "netlist", None)
        phase_mode = getattr(doc, "phase_mode", "single")

        if netlist and netlist.get("connections"):
            try:
                from ECD.pin_model import get_pin_position
                from ECD.dxf_generator import route_wire_bend
            except ImportError:
                from pin_model import get_pin_position
                from dxf_generator import route_wire_bend

            for conn in netlist["connections"]:
                src_cid = conn["src_component"]
                dst_cid = conn["dst_component"]
                src_pin = conn["src_pin"]
                dst_pin = conn["dst_pin"]
                wtype = conn["wire_type"]

                src_item = self.symbol_items.get(src_cid)
                dst_item = self.symbol_items.get(dst_cid)

                if src_item:
                    src_pos = (src_item.base_x + src_item.pos().x(), src_item.base_y - src_item.pos().y())
                else:
                    src_pos = box_positions.get(src_cid, (0.0, 0.0))

                if dst_item:
                    dst_pos = (dst_item.base_x + dst_item.pos().x(), dst_item.base_y - dst_item.pos().y())
                else:
                    dst_pos = box_positions.get(dst_cid, (0.0, 0.0))

                try:
                    src_pin_pos = get_pin_position(src_cid, src_pin, src_pos, phase_mode)
                except Exception:
                    src_pin_pos = conn.get("src_pos", src_pos)

                try:
                    dst_pin_pos = get_pin_position(dst_cid, dst_pin, dst_pos, phase_mode)
                except Exception:
                    dst_pin_pos = conn.get("dst_pos", dst_pos)

                qt_src = (src_pin_pos[0], -src_pin_pos[1])
                qt_dst = (dst_pin_pos[0], -dst_pin_pos[1])

                pts = route_diagram_wire(src_cid, dst_cid, wtype, qt_src, qt_dst)

                path = QPainterPath()
                if pts:
                    path.moveTo(pts[0][0], pts[0][1])
                    for p in pts[1:]:
                        path.lineTo(p[0], p[1])

                path_item = QGraphicsPathItem(path)

                if wtype in ("L", "L1"):
                    pen = QPen(QColor(215, 38, 56), 2.0)      # Deep Rich Red (L1)
                elif wtype == "L2":
                    pen = QPen(QColor(220, 170, 0), 2.0)     # Warm Golden Yellow (L2)
                elif wtype == "L3":
                    pen = QPen(QColor(220, 100, 0), 2.0)     # Deep Rich Orange (L3)
                elif wtype == "N":
                    pen = QPen(QColor(0, 230, 100), 1.5, Qt.PenStyle.DashLine)  # Green (Neutral)
                elif wtype == "E":
                    pen = QPen(QColor(25, 90, 210), 1.5, Qt.PenStyle.DashDotLine) # Darker Blue (Earth)
                else:
                    pen = QPen(QColor(255, 255, 255), 1.5)

                pen.setCosmetic(True)
                path_item.setPen(pen)
                path_item.setZValue(5.0)
                path_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                self.scene.addItem(path_item)

                self.wire_items.append({
                    "src_cid": src_cid,
                    "dst_cid": dst_cid,
                    "src_pin": src_pin,
                    "dst_pin": dst_pin,
                    "wire_type": wtype,
                    "phase_mode": phase_mode,
                    "item": path_item,
                    "src_default_pos": box_positions.get(src_cid, (0.0, 0.0)),
                    "dst_default_pos": box_positions.get(dst_cid, (0.0, 0.0))
                })

        # Determine and set fixed sceneRect from PAGE_MARGIN layer bounds
        try:
            margin_entities = [e for e in doc.modelspace() if e.dxf.layer == "PAGE_MARGIN"]
            if margin_entities:
                margin_bb = extents(margin_entities)
                s_min_x = margin_bb.extmin.x
                s_max_x = margin_bb.extmax.x
                s_min_y = -margin_bb.extmax.y
                s_max_y = -margin_bb.extmin.y
                self.scene.setSceneRect(s_min_x, s_min_y, s_max_x - s_min_x, s_max_y - s_min_y)
            else:
                self.scene.setSceneRect(self.scene.itemsBoundingRect())
        except Exception as e:
            print("Failed to set bounded scene rect from PAGE_MARGIN:", e)
            self.scene.setSceneRect(self.scene.itemsBoundingRect())
            
        print(f"Fixed scene.sceneRect() set to: x={self.scene.sceneRect().x():.2f}, y={self.scene.sceneRect().y():.2f}, w={self.scene.sceneRect().width():.2f}, h={self.scene.sceneRect().height():.2f}")
        
        rect = self.scene.sceneRect()
        if rect.width() > 0 and rect.height() > 0 and self.width() > 0 and self.height() > 0:
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.update_baseline_scale()
        return True

    def update_baseline_scale(self):
        t_m11 = self.transform().m11()
        if t_m11 > 0:
            self.baseline_scale = t_m11

    def get_relative_zoom(self) -> float:
        if getattr(self, "baseline_scale", 0.0) <= 0.0:
            return 1.0
        return self.transform().m11() / self.baseline_scale

    def is_at_100_percent(self) -> bool:
        return abs(self.get_relative_zoom() - 1.0) < 1e-3

    def _notify_zoom_changed(self):
        is_zoomed = not self.is_at_100_percent()
        if getattr(self, "canvas_parent", None) and hasattr(self.canvas_parent, "parent_window"):
            pw = self.canvas_parent.parent_window
            if pw and hasattr(pw, "sidebar") and pw.sidebar:
                pw.sidebar.reset_view_btn.setEnabled(is_zoomed)

    def reset_view(self):
        """Reset view to 100% fit-to-page baseline and center the diagram."""
        rect = self.scene.sceneRect()
        if rect.width() > 0 and rect.height() > 0 and self.width() > 0 and self.height() > 0:
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.update_baseline_scale()
        self._notify_zoom_changed()

    def fit_to_view(self):
        if self.is_at_100_percent():
            self.reset_view()

    def wheelEvent_scale(self, factor: float):
        current_rel = self.get_relative_zoom()
        target_rel = current_rel * factor

        if target_rel > 5.0:
            factor = 5.0 / current_rel
            target_rel = 5.0
        elif target_rel < 1.0:
            factor = 1.0 / current_rel
            target_rel = 1.0

        if abs(target_rel - current_rel) < 1e-4:
            return

        if abs(target_rel - 1.0) < 1e-3:
            self.reset_view()
        else:
            self.scale(factor, factor)
            self._notify_zoom_changed()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else (1.0 / 1.1)
        self.wheelEvent_scale(factor)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # exact-match guard: auto-refit on window resize only occurs at 100% baseline
        if self.is_at_100_percent():
            rect = self.scene.sceneRect()
            if rect.width() > 0 and rect.height() > 0 and self.width() > 0 and self.height() > 0:
                self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
                self.update_baseline_scale()
        self._notify_zoom_changed()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._is_panning = True
            self._pan_start = event.pos()
            self._has_panned = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, "_is_panning", False):
            delta = event.pos() - self._pan_start
            if abs(delta.x()) > 0 or abs(delta.y()) > 0:
                self._has_panned = True
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "_is_panning", False):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if getattr(self, "_has_panned", False):
            self._has_panned = False
            event.accept()
            return
        super().contextMenuEvent(event)

class WelcomeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            WelcomeWidget {
                background-color: #f0f4f8;
            }
            #card {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
            #title {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 24px;
                font-weight: 800;
                color: #2c5282;
            }
            #subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #718096;
            }
            #icon {
                font-size: 40px;
            }
            .step-num {
                background-color: #ebf4ff;
                color: #2c5282;
                border-radius: 12px;
                font-weight: bold;
                font-size: 13px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            .step-txt {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #4a5568;
            }
            .divider {
                font-size: 18px;
                color: #a0aec0;
                font-weight: bold;
            }
        """)
        
        main_lay = QVBoxLayout(self)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(30, 30, 30, 30)
        card_lay.setSpacing(15)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel("⚡")
        icon.setObjectName("icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(icon)
        
        title = QLabel("Electrical Diagram Generator")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title)
        
        subtitle = QLabel("Describe your electrical system in plain language\nand get a professional distribution diagram instantly.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(subtitle)
        
        steps_widget = QWidget()
        steps_lay = QHBoxLayout(steps_widget)
        steps_lay.setContentsMargins(0, 10, 0, 0)
        steps_lay.setSpacing(10)
        steps_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Step 1
        s1_num = QLabel("1")
        s1_num.setProperty("class", "step-num")
        s1_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s1_txt = QLabel("Type description\nin the panel")
        s1_txt.setProperty("class", "step-txt")
        s1_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w1 = QWidget()
        w1_lay = QVBoxLayout(w1)
        w1_lay.setContentsMargins(0, 0, 0, 0)
        w1_lay.addWidget(s1_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w1_lay.addWidget(s1_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w1)
        
        div1 = QLabel("→")
        div1.setProperty("class", "divider")
        steps_lay.addWidget(div1)
        
        # Step 2
        s2_num = QLabel("2")
        s2_num.setProperty("class", "step-num")
        s2_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s2_txt = QLabel("Choose a\ndetail level")
        s2_txt.setProperty("class", "step-txt")
        s2_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w2 = QWidget()
        w2_lay = QVBoxLayout(w2)
        w2_lay.setContentsMargins(0, 0, 0, 0)
        w2_lay.addWidget(s2_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w2_lay.addWidget(s2_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w2)
        
        div2 = QLabel("→")
        div2.setProperty("class", "divider")
        steps_lay.addWidget(div2)
        
        # Step 3
        s3_num = QLabel("3")
        s3_num.setProperty("class", "step-num")
        s3_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s3_txt = QLabel("Press ⚡\nGenerate Diagram")
        s3_txt.setProperty("class", "step-txt")
        s3_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        w3 = QWidget()
        w3_lay = QVBoxLayout(w3)
        w3_lay.setContentsMargins(0, 0, 0, 0)
        w3_lay.addWidget(s3_num, alignment=Qt.AlignmentFlag.AlignCenter)
        w3_lay.addWidget(s3_txt, alignment=Qt.AlignmentFlag.AlignCenter)
        steps_lay.addWidget(w3)
        
        card_lay.addWidget(steps_widget)
        main_lay.addWidget(card)

class LoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            LoadingWidget {
                background-color: #f0f4f8;
            }
            #card {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
            #title {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                font-weight: 700;
                color: #2c5282;
            }
            #subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #718096;
            }
            #spinner {
                font-size: 36px;
            }
        """)
        
        main_lay = QVBoxLayout(self)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(40, 40, 40, 40)
        card_lay.setSpacing(15)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = QLabel("⏳")
        spinner.setObjectName("spinner")
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(spinner)
        
        title = QLabel("Generating Diagram…")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title)
        
        subtitle = QLabel("Parsing your description and building the diagram.\nThis may take a few seconds.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(subtitle)
        
        main_lay.addWidget(card)

class CodePanel(QWidget):
    applied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = True
        self.setStyleSheet("""
            CodePanel {
                background-color: #2d3748;
                border-top: 2px solid #1a202c;
            }
            QPlainTextEdit {
                background-color: #1a202c;
                color: #edf2f7;
                font-family: 'Courier New', Courier, monospace;
                font-size: 13px;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background-color: #3182ce;
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #2b6cb0;
            }
            QPushButton:pressed {
                background-color: #2c5282;
            }
            #toggle_btn {
                background-color: transparent;
                color: #a0aec0;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border: 1px solid #4a5568;
                border-radius: 4px;
            }
            #toggle_btn:hover {
                background-color: #4a5568;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(4)

        # Header bar — always visible
        hdr = QHBoxLayout()
        self.toggle_btn = QPushButton("▶ Mermaid Code")
        self.toggle_btn.setObjectName("toggle_btn")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        hdr.addWidget(self.toggle_btn)
        hdr.addStretch()

        self.apply_btn = QPushButton("⚡ Apply Changes")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        hdr.addWidget(self.apply_btn)
        lay.addLayout(hdr)

        # Editor area — hidden by default
        self.text_edit = QPlainTextEdit()
        self.text_edit.setFixedHeight(220)
        self.text_edit.setVisible(False)
        self.apply_btn.setVisible(False)
        lay.addWidget(self.text_edit)

    def toggle(self):
        self._collapsed = not self._collapsed
        self.text_edit.setVisible(not self._collapsed)
        self.apply_btn.setVisible(not self._collapsed)
        self.toggle_btn.setText("▼ Mermaid Code" if not self._collapsed else "▶ Mermaid Code")

    def set_code(self, code: str):
        self.text_edit.setPlainText(code)

    def get_code(self) -> str:
        return self.text_edit.toPlainText()

    def _on_apply_clicked(self):
        self.applied.emit(self.get_code())

try:
    from ECD.dxf_generator import export_dxf, render_doc_to_svg, render_doc_to_png, render_doc_to_pdf
    from ECD.mermaid_generator import MermaidGenerator
    from ECD.llm.ollama_client import OllamaClient, GenerationWorker
    from ECD.constants import COMPLEXITY_LEVELS
    from ECD.ValidationWorker import ValidationWorker, ValidationPanel, MermaidFixWorker
except ImportError:
    from dxf_generator import export_dxf, render_doc_to_svg, render_doc_to_png, render_doc_to_pdf
    from mermaid_generator import MermaidGenerator
    from llm.ollama_client import OllamaClient, GenerationWorker
    from constants import COMPLEXITY_LEVELS
    from ValidationWorker import ValidationWorker, ValidationPanel, MermaidFixWorker

class DiagramCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.generator = MermaidGenerator()
        from ECD.undo_manager import UndoManager
        self.undo_manager = UndoManager(self)
        self.current_parsed_data = None
        self.original_parsed_data = None
        self._current_mermaid_code = ""
        self.current_doc = None
        self.current_svg = ""
        self._build_ui()
        self._show_welcome()
        self._last_prompt = ""
        self._validation_worker = None
        self._gen_worker = None
        self._fix_worker = None
        self._is_regex_fallback = False

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background: transparent;
                height: 4px;
            }
        """)

        self.stacked_widget = QStackedWidget()
        self.splitter.addWidget(self.stacked_widget)

        self.welcome_widget = WelcomeWidget()
        self.stacked_widget.addWidget(self.welcome_widget)

        self.loading_widget = LoadingWidget()
        self.stacked_widget.addWidget(self.loading_widget)

        self.svg_widget = SvgPreviewWidget(self)
        self.stacked_widget.addWidget(self.svg_widget)

        # Lightweight stub — stores mermaid code for .mmd export / get_current_mermaid_code
        # without rendering any UI.  A full interactive editor will be added in v2.
        self.code_panel = type('_CodeStub', (), {
            '_code': '',
            'set_code': lambda self, c: setattr(self, '_code', c),
            'get_code': lambda self: self._code,
            'setVisible': lambda self, v: None,
        })()

        self.validation_panel = ValidationPanel()
        self.splitter.addWidget(self.validation_panel)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([600,150 ])

        lay.addWidget(self.splitter)
        # "Fix Issues" button in the panel triggers auto-correction using stored findings
        self.validation_panel.fixRequested.connect(
            lambda: self._on_validation_issues_found(self.validation_panel._current_findings)
        )

    def closeEvent(self, event):
        if self._validation_worker is not None and self._validation_worker.isRunning():
            self._validation_worker.quit()
            self._validation_worker.wait(5000)

        super().closeEvent(event)


    def _show_welcome(self):
        """Display a branded welcome screen before any diagram is generated."""
        self.stacked_widget.setCurrentWidget(self.welcome_widget)
        self.current_parsed_data = None
        self.original_parsed_data = None
        self.current_doc = None
        self.current_svg = ""
        self._current_mermaid_code = ""
        val_worker = getattr(self, "_validation_worker", None)
        if val_worker is not None and val_worker.isRunning():
            val_worker.requestInterruption()
            val_worker.quit()
            val_worker.wait(1000)
            self._validation_worker = None
        if hasattr(self, "validation_panel") and self.validation_panel:
            self.validation_panel._current_findings = []
            self.validation_panel.findings_lbl.setText("")
            self.validation_panel.fix_btn.setEnabled(False)
            self.validation_panel.hide()


    def _show_loading(self):
        """Replace the canvas with an animated loading screen while generating."""
        val_worker = getattr(self, "_validation_worker", None)
        if val_worker is not None and val_worker.isRunning():
            val_worker.requestInterruption()
            val_worker.quit()
            val_worker.wait(1000)
            self._validation_worker = None
        if hasattr(self, "validation_panel") and self.validation_panel:
            self.validation_panel._current_findings = []
            self.validation_panel.findings_lbl.setText("")
            self.validation_panel.fix_btn.setEnabled(False)
            self.validation_panel.hide()

        self.stacked_widget.setCurrentWidget(self.loading_widget)
        if self.parent_window and hasattr(self.parent_window, "sidebar") and self.parent_window.sidebar:
            self.parent_window.sidebar.set_generating(True)


    # ── Async generation (non-blocking) ───────────────────────────────────────

    def generate_from_prompt(self, prompt_text, complexity_level="Neutral", model_choice="Groq \u2014 Fast (Cloud)"):
        """Kick off diagram generation asynchronously so the UI stays responsive."""
        prompt_text = prompt_text.strip()
        if not prompt_text:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a diagram description.")
            if self.parent_window and hasattr(self.parent_window, "sidebar") and self.parent_window.sidebar:
                self.parent_window.sidebar.set_generating(False)
            return False

        # Cancel any in-flight generation worker
        if getattr(self, "_gen_worker", None) is not None:
            if self._gen_worker.isRunning():
                self._gen_worker.requestInterruption()
                self._gen_worker.quit()
                self._gen_worker.wait(2000)
            self._gen_worker.deleteLater()
            self._gen_worker = None

        self._is_regex_fallback = False
        self._show_loading()
        self._pending_prompt       = prompt_text
        self._pending_complexity   = complexity_level
        self._pending_model_choice = model_choice

        self._gen_worker = GenerationWorker(prompt_text, complexity_level, self.generator, model_choice)
        self._gen_worker.finished.connect(self._on_llm_finished)
        self._gen_worker.failed.connect(self._on_llm_failed)
        self._gen_worker.start()
        return True   # returns immediately; diagram arrives via signal

    def _on_llm_failed(self, error_msg: str):
        """LLM unavailable — fall back to fast regex parser on the main thread."""
        print(f"LLM parsing failed, using regex fallback: {error_msg}")
        self._is_regex_fallback = True
        try:
            parsed_data = self.generator.parse_prompt(
                self._pending_prompt, self._pending_complexity)
            self._finalise_generation(parsed_data, self._pending_prompt, self._pending_complexity)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")
            if self.parent_window and hasattr(self.parent_window, "sidebar") and self.parent_window.sidebar:
                self.parent_window.sidebar.set_generating(False)

    def _on_llm_finished(self, parsed_data: dict):
        """Called on the main thread once the background LLM call succeeds."""
        self._is_regex_fallback = False
        prompt_text      = self._pending_prompt
        complexity_level = self._pending_complexity
        try:
            from ECD.pin_model import get_base_type
        except ImportError:
            from pin_model import get_base_type

        try:
            def _to_tuple(c):
                if isinstance(c, dict):
                    return (c.get("id", ""), c.get("label", ""))
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    return (c[0], c[1])
                return (str(c), str(c))

            parsed_data["components"] = [_to_tuple(c) for c in parsed_data.get("components", [])]
            comp_ids = [c for c, _ in parsed_data["components"]]
            lang     = parsed_data.get("language", self.generator.detect_language(prompt_text))
            voltage  = parsed_data.get("voltage", "230V / 415V")

            prompt_lower = prompt_text.lower()
            def is_explicitly_excluded(cid: str) -> bool:
                cid_base = get_base_type(cid)
                if cid_base == "supply":
                    if any(kw in prompt_lower for kw in ["no supply", "without supply", "exclude supply", "omit supply", "no incoming"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:supply|mains|incoming)\b', prompt_lower))
                if cid_base == "maincb":
                    if any(kw in prompt_lower for kw in ["direct connection", "connected directly", "no maincb", "no main breaker", "without main breaker", "without a main breaker", "no breaker", "without breaker", "do not include a main breaker", "do not include main breaker", "ブレーカーなし", "主遮断器なし", "主遮断器は含めない", "主遮断器不要", "ブレーカー不要", "直接接続"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:main\s+)?(?:cb|breaker|mcb|mccb)\b', prompt_lower))
                if cid_base in ("rcd", "rcbo"):
                    if any(kw in prompt_lower for kw in ["direct connection", "connected directly", "no rcd", "no rcbo", "no residual", "no earth fault", "without rcd", "漏電遮断器なし", "漏電遮断器は含めない", "rcdなし"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:rcd|rcbo|residual|earth\s+fault)\b', prompt_lower))
                if cid_base == "nbar":
                    if any(kw in prompt_lower for kw in ["no neutral", "without neutral", "中性線なし", "中性バーなし"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:neutral|nbar|n-bar|n\s+bar)\b', prompt_lower))
                if cid_base == "ebar":
                    if any(kw in prompt_lower for kw in ["no earth", "no ground", "without earth", "without ground", "接地バーなし", "アースなし", "接地なし"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:earth|ground|ebar|e-bar|e\s+bar)\b', prompt_lower))
                if cid_base == "bus":
                    if any(kw in prompt_lower for kw in ["no busbar", "no bus"]):
                        return True
                    return bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:busbar|bus\s+bar|bus)\b', prompt_lower))
                return False

            # Safety minimum (only insert supply if not explicitly omitted)
            if "supply" not in comp_ids and not is_explicitly_excluded("supply"):
                parsed_data["components"].insert(0, (
                    "supply",
                    self.generator.components_map["main incoming supply"][lang].replace("230V / 415V", voltage)
                ))

            if re.search(r'\b(?:supply\s*(?:1\s*and\s*(?:supply\s*)?2|[a-b]\s*and\s*supply\s*[a-b])|mains\s*1\s*and\s*(?:mains\s*)?2|(?:two|2)\s+(?:main\s+)?supplies|dual\s+supplies?|(?:main\s+)?(?:grid|mains|utility)\s+(?:supply\s+)?and\s+(?:backup\s+)?(?:generator|secondary|auxiliary)\s+supply)\b|(?:主電源|電源).*?(?:副電源|発電機|2系統)', prompt_lower):
                if not any(c == "supply_2" for c, _ in parsed_data["components"]):
                    parsed_data["components"].insert(1, ("supply_2", f"Secondary Supply ({voltage})"))

            explicit_no_breaker = is_explicitly_excluded("maincb")
            if "maincb" not in comp_ids and not explicit_no_breaker:
                parsed_data["components"].insert(1, (
                    "maincb", self.generator.components_map["main breaker"][lang]))

            # Complexity filtering
            COMPONENT_KEYWORDS = {
                "supply":["supply", "mains", "grid", "source", "incoming"],
                "rcd":   ["rcd", "residual current", "rcbo", "earth fault"],
                "nbar":  ["neutral bar", "neutral link"],
                "ebar":  ["earth bar", "earth terminal"],
                "bus":   ["busbar", "bus bar", "copper bar"],
                "outcb": ["breaker", "mcb", "circuit", "load", "motor", "socket", "light", "outlet", "branch", "lamp"],
                "motor_3ph": ["motor_3ph", "3ph_motor", "3-phase motor", "three-phase motor", "3ph motor"],
            }

            def prompt_mentions(cid):
                base_id = get_base_type(cid)
                return any(kw in prompt_lower for kw in COMPONENT_KEYWORDS.get(base_id, []))

            if complexity_level != "Neutral":
                allowed_ids = set(COMPLEXITY_LEVELS[complexity_level]["components"])
                allow_outcb = COMPLEXITY_LEVELS[complexity_level].get("allow_outcb", False)
            else:
                allowed_ids = set(c for c, _ in parsed_data["components"])
                allow_outcb = True

            parsed_data["components"] = [
                (c, l) for c, l in parsed_data["components"]
                if (c in allowed_ids or get_base_type(c) == "supply" or (allow_outcb and get_base_type(c) == "outcb") or prompt_mentions(c))
                and not is_explicitly_excluded(c)
            ]

            # Backfill defaults for non-Neutral modes
            if complexity_level != "Neutral":
                current_ids = {c for c, _ in parsed_data["components"]}
                defaults    = self.generator.get_default_components(lang, voltage, complexity_level)
                for cid, lbl in defaults:
                    if cid not in current_ids and get_base_type(cid) != "outcb":
                        if not is_explicitly_excluded(cid):
                            parsed_data["components"].append((cid, lbl))

            if complexity_level == "Detailed":
                if not any(get_base_type(c) == "outcb" for c, _ in parsed_data["components"]):
                    generic_label = self.generator.components_map["outgoing mcbs"][lang]
                    parsed_data["components"].insert(-1, ("outcb_1", generic_label))

            # Force inclusion of nbar/ebar/bus based on flags and outgoing breakers (critical for correctness and validation)
            current_ids = {c for c, _ in parsed_data["components"]}
            has_outcb = any(get_base_type(c) == "outcb" for c, _ in parsed_data["components"])
            if parsed_data.get("flags", {}).get("show_neutral") and "nbar" not in current_ids:
                parsed_data["components"].append(("nbar", self.generator.components_map["neutral bar"][lang]))
                current_ids.add("nbar")
            if parsed_data.get("flags", {}).get("show_earth") and "ebar" not in current_ids:
                parsed_data["components"].append(("ebar", self.generator.components_map["earth bar"][lang]))
                current_ids.add("ebar")
            if has_outcb and "bus" not in current_ids:
                parsed_data["components"].append(("bus", self.generator.components_map["busbar"][lang]))
                current_ids.add("bus")

            parsed_data["complexity"] = complexity_level
            parsed_data["prompt"]     = prompt_text
            parsed_data["language"]   = self.generator.detect_language(prompt_text)

            phase_hint = parsed_data.get("phase_hint")
            if not phase_hint:
                if re.search(r'\b(?:three[-\s]*phase|3[-\s]*phase|三相)\b', prompt_lower):
                    phase_hint = "three-phase"
                elif re.search(r'\b(?:single[-\s]*phase|1[-\s]*phase|単相)\b', prompt_lower):
                    phase_hint = "single-phase"
            parsed_data["phase_hint"] = phase_hint

            if re.search(r'\b(?:spare_block|spare_terminal|spare_cb|unwired|spare)\b', prompt_lower):
                if not any(c == "spare_block" for c, _ in parsed_data["components"]):
                    parsed_data["components"].append(("spare_block", "Spare Component"))
            print("Parsed via LLM")
            self._finalise_generation(parsed_data, prompt_text, complexity_level)

        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "Generation Error", f"Failed to generate diagram:\n\n{str(e)}")

    def _display_current_diagram(self):
        """Helper to load the current document into the SvgPreviewWidget (Phase 1)."""
        if self.current_doc:
            layout_overrides = {}
            if self.current_parsed_data:
                layout_overrides = self.current_parsed_data.get("layout_overrides", {})
            self.svg_widget.load_document(self.current_doc, layout_overrides)
        else:
            self.svg_widget.load(QByteArray(self.current_svg.encode('utf-8')))

    def _finalise_generation(self, parsed_data: dict, prompt_text: str, complexity_level: str):
        """Shared final step: build Mermaid, render HTML, kick off async validation."""
        import copy
        self.current_parsed_data  = copy.deepcopy(parsed_data)
        self.original_parsed_data = copy.deepcopy(parsed_data)
        self.undo_manager.clear()

        mermaid_code = self.generator.generate_mermaid_code(parsed_data)
        self._current_mermaid_code = mermaid_code
        self.code_panel.set_code(mermaid_code)
        # code_panel is a no-op stub; nothing to show

        try:
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self._display_current_diagram()
            self._reset_fit_mode()
            self.stacked_widget.setCurrentWidget(self.svg_widget)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Render Error", f"Failed to render DXF preview:\n\n{e}")

        if self.parent_window and hasattr(self.parent_window, "status"):
            lang_name = "English" if parsed_data.get("language") == "en" else "Japanese"
            gen_source = "Regex Fallback" if getattr(self, "_is_regex_fallback", False) else "LLM"
            self.parent_window.status.showMessage(
                f"Diagram generated via {gen_source} ({lang_name}, {complexity_level}), "
                f"{len(parsed_data.get('components', []))} components. "
                "Drag boxes · Double-click text · Edit code below.", 6000)

        # Disable the sidebar Reset button on fresh generation baseline and re-enable Generate button
        if self.parent_window and hasattr(self.parent_window, "sidebar") and self.parent_window.sidebar:
            self.parent_window.sidebar.reset_btn.setEnabled(False)
            self.parent_window.sidebar.set_generating(False)

        self._last_prompt = prompt_text
        self._run_validation(prompt_text, parsed_data)

    # ─────────────────────────────────────────────────────────────────────────
    def _on_native_code_applied(self, new_code: str):
        self._current_mermaid_code = new_code
        try:
            from ECD.dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        except ImportError:
            from dxf_generator import parse_mermaid_sequence, normalize_for_dxf

        try:
            nodes, edges = parse_mermaid_sequence(new_code)
            parsed_data = normalize_for_dxf(nodes, edges)
            # Preserve metadata
            if self.current_parsed_data:
                parsed_data["flags"] = self.current_parsed_data.get("flags", {})
                parsed_data["voltage"] = self.current_parsed_data.get("voltage", "")
                parsed_data["language"] = self.current_parsed_data.get("language", "en")
                parsed_data["complexity"] = self.current_parsed_data.get("complexity", "Standard")
                parsed_data["prompt"] = self.current_parsed_data.get("prompt", self._last_prompt)
            self.current_parsed_data = parsed_data
            
            # Re-generate DXF & SVG natively and show in SVG preview
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self._display_current_diagram()
            self._reset_fit_mode()
            self.stacked_widget.setCurrentWidget(self.svg_widget)
            
            # Re-run validation on the new code
            prompt = self.current_parsed_data.get("prompt", self._last_prompt) \
                    if self.current_parsed_data else self._last_prompt
            self._run_validation(prompt, self.current_parsed_data)
            
            if self.parent_window and hasattr(self.parent_window, 'status'):
                self.parent_window.status.showMessage("✓ Diagram updated from edited code", 3000)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Invalid Mermaid Code", f"Could not parse edited Mermaid code:\n\n{e}")

    def refresh_diagram(self):
        if not self.current_parsed_data:
            return
        try:
            mc = self.generator.generate_mermaid_code(self.current_parsed_data)
            self._current_mermaid_code = mc
            self.code_panel.set_code(mc)
            self.current_doc = export_dxf(self.current_parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self._display_current_diagram()
            self.stacked_widget.setCurrentWidget(self.svg_widget)
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", str(e))

    def _run_validation(self, prompt: str, parsed_data: dict):
        self.validation_panel.show_loading()

        if self._validation_worker is not None:
            if self._validation_worker.isRunning():
                self._validation_worker.requestInterruption()
                self._validation_worker.quit()
                self._validation_worker.wait(3000)
            self._validation_worker.deleteLater()
            self._validation_worker = None

        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"

        self._validation_worker = ValidationWorker(prompt, parsed_data, complexity)
        self._validation_worker.validationComplete.connect(self._on_validation_complete)
        self._validation_worker.findingsReady.connect(self.validation_panel.set_findings)
        # ← findingsReady no longer connected to _on_validation_issues_found here
        self._validation_worker.start()

    def _on_validation_complete(self, text: str, has_issues: bool):
        # If fallback was used for generation, prepend a warning to the findings
        if getattr(self, "_is_regex_fallback", False):
            warning_text = "⚠️ [FALLBACK WARNING] The diagram was generated using the local regex fallback parser because the Groq LLM model was unavailable (e.g. rate limit exceeded, API offline, or network error). Output may be incomplete or lack fine-grained electrical connections."
            if "FINDINGS:" in text:
                parts = text.split("FINDINGS:")
                # Prepend the fallback warning to findings bullet list
                text = f"{parts[0]}FINDINGS:\n- {warning_text}\n{parts[1]}"
            else:
                text = f"{text}\nFINDINGS:\n- {warning_text}"
            has_issues = True
            
        self.validation_panel.show_result(text, has_issues)


    def _on_validation_issues_found(self, findings: list):
        """
        Called when the user clicks Fix Issues.
    
        Spawns MermaidFixWorker (LLM #3) which receives the current raw Mermaid
        code and the validation findings, then returns a corrected Mermaid string.
    
        Rules enforced inside the worker:
        - NEVER removes existing participants or arrows (preserves complexity-level
        components the old keyword fixer could not handle).
        - ONLY adds what is needed to resolve each finding.
        - Returns the full corrected sequenceDiagram code directly.
        """
        if not findings:
            return
    
        # Guard: cancel any previous fix worker still running
        if self._fix_worker is not None:
            if self._fix_worker.isRunning():
                self._fix_worker.quit()
                self._fix_worker.wait(3000)
            self._fix_worker.deleteLater()
            self._fix_worker = None
    
        # Read the live Mermaid code (reflects any user edits in the code editor)
        current_code = self._current_mermaid_code
        if not current_code:
            return
    
        prompt     = self.current_parsed_data.get("prompt", self._last_prompt) \
                    if self.current_parsed_data else self._last_prompt
        complexity = self.current_parsed_data.get("complexity", "Standard") \
                    if self.current_parsed_data else "Standard"
    
        # Show "Applying fixes…" state in the panel immediately
        self.validation_panel.show_fixing()
    
        # Create and wire the fix worker
        self._fix_worker = MermaidFixWorker(current_code, findings, prompt, complexity)
        self._fix_worker.fixComplete.connect(self._on_fix_complete)
        self._fix_worker.fixFailed.connect(self._on_fix_failed)
        self._fix_worker.start()
    
    
    def _on_fix_complete(self, fixed_code: str):
        """Render the LLM-corrected Mermaid code and re-run validation."""
        self._current_mermaid_code = fixed_code
        self.code_panel.set_code(fixed_code)
    
        # Parse the corrected Mermaid code back to parsed_data
        try:
            from ECD.dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        except ImportError:
            from dxf_generator import parse_mermaid_sequence, normalize_for_dxf
        try:
            nodes, edges = parse_mermaid_sequence(fixed_code)
            parsed_data = normalize_for_dxf(nodes, edges)
            if self.current_parsed_data:
                parsed_data["flags"] = self.current_parsed_data.get("flags", {})
                parsed_data["voltage"] = self.current_parsed_data.get("voltage", "")
                parsed_data["language"] = self.current_parsed_data.get("language", "en")
                parsed_data["complexity"] = self.current_parsed_data.get("complexity", "Standard")
                parsed_data["prompt"] = self.current_parsed_data.get("prompt", self._last_prompt)

            self.current_parsed_data = parsed_data
            
            self.current_doc = export_dxf(parsed_data, None)
            self.current_svg = render_doc_to_svg(self.current_doc)
            self._display_current_diagram()
            self.stacked_widget.setCurrentWidget(self.svg_widget)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Fix Render Error", f"Failed to render corrected diagram:\n\n{e}")
    
        # Clear stored findings — they've been consumed
        self.validation_panel._current_findings = []
        self.validation_panel.fix_btn.setEnabled(False)
    
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(
                "✓ Diagram patched by LLM — re-validating…", 4000
            )
    
        prompt = self.current_parsed_data.get("prompt", self._last_prompt) \
                if self.current_parsed_data else self._last_prompt
        self._run_validation(prompt, self.current_parsed_data)
    
    def _on_fix_failed(self, error_msg: str):
        """Surface the error in the validation panel without touching the diagram."""
        self.validation_panel.show_fix_error(error_msg)
        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage(f"Fix failed: {error_msg[:80]}", 5000)

    def reset_view(self):
        """Reset view to 100% fit-to-page baseline and center the diagram."""
        self.svg_widget.reset_view()

    def revert_to_original(self):
        """Restore layout_overrides and text_overrides to session baseline without altering zoom or pan position."""
        if not self.original_parsed_data:
            return

        # 1. Capture current view transform and scene center point
        current_transform = self.svg_widget.transform()
        center_scene_pt = self.svg_widget.mapToScene(self.svg_widget.viewport().rect().center())
        is_zoomed = not self.svg_widget.is_at_100_percent()

        # 2. Reset parsed data to session baseline
        import copy
        self.current_parsed_data = copy.deepcopy(self.original_parsed_data)
        self.current_parsed_data.pop("layout_overrides", None)
        self.current_parsed_data.pop("text_overrides", None)
        self.current_parsed_data.pop("component_position_overrides", None)
        self.original_parsed_data.pop("layout_overrides", None)
        self.original_parsed_data.pop("text_overrides", None)
        self.original_parsed_data.pop("component_position_overrides", None)
        self.undo_manager.clear()

        # 3. Re-render DXF and redisplay
        self.current_doc = export_dxf(self.current_parsed_data, None)
        self.current_svg = render_doc_to_svg(self.current_doc)
        self._display_current_diagram()

        # 4. If zoomed in, preserve exact view transform and pan center
        if is_zoomed:
            self.svg_widget.setTransform(current_transform)
            self.svg_widget.centerOn(center_scene_pt)

        # Disable the Revert to Original button since data is now at session baseline
        if self.parent_window and hasattr(self.parent_window, "sidebar"):
            self.parent_window.sidebar.reset_btn.setEnabled(False)

        if self.parent_window and hasattr(self.parent_window, "status"):
            self.parent_window.status.showMessage("Diagram data reverted to original state", 3000)

    def zoom_in(self):
        self.svg_widget.wheelEvent_scale(1.1)

    def zoom_out(self):
        self.svg_widget.wheelEvent_scale(1.0 / 1.1)

    def reset_zoom(self):
        self.reset_view()

    def _reset_fit_mode(self):
        """Restore fit-to-view mode (called on new generation / code apply)."""
        self.svg_widget.reset_view()

    def get_current_mermaid_code(self) -> str:
        return self.code_panel.get_code() or self._current_mermaid_code

    def get_updated_document(self):
        """Regenerate and return an up-to-date ezdxf Document containing all current layout and text overrides."""
        if self.current_parsed_data:
            try:
                from dxf_generator import export_dxf
            except ImportError:
                from ECD.dxf_generator import export_dxf
            self.current_doc = export_dxf(self.current_parsed_data, None)
        return self.current_doc

    def get_updated_svg(self):
        """Regenerate and return an up-to-date SVG string containing all current layout and text overrides."""
        doc = self.get_updated_document()
        if doc:
            try:
                from dxf_generator import render_doc_to_svg
            except ImportError:
                from ECD.dxf_generator import render_doc_to_svg
            self.current_svg = render_doc_to_svg(doc)
        return self.current_svg

    # ── SVG Export ────────────────────────────────────────────────────────────
    def export_svg(self, file_path: str, on_done=None):
        try:
            svg_data = self.get_updated_svg()
            if not svg_data:
                raise ValueError("No generated SVG found in memory.")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(svg_data)
            if on_done:
                on_done(True, f"✓ SVG saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"SVG save error: {e}")

    # ── PDF Export ────────────────────────────────────────────────────────────
    def export_pdf(self, file_path: str, on_done=None):
        try:
            doc = self.get_updated_document()
            if not doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_pdf(doc, file_path)
            if on_done:
                on_done(True, f"✓ PDF saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"PDF save error: {e}")

    # ── SVG-only PNG Export (diagram only, no UI chrome) ─────────────────────
    def export_svg_as_png(self, file_path: str, on_done=None):
        try:
            doc = self.get_updated_document()
            if not doc:
                raise ValueError("No generated DXF document found in memory.")
            render_doc_to_png(doc, file_path)
            if on_done:
                on_done(True, f"✓ PNG saved to {file_path}")
        except Exception as e:
            if on_done:
                on_done(False, f"PNG save error: {e}")