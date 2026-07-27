import unittest
import copy
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QKeyEvent
from ECD.diagram_canvas import DiagramCanvas, SymbolItem, EditableTextItem
from ECD.dxf_generator import export_dxf

app = QApplication.instance() or QApplication([])


class TestPhase21ArrowMovement(unittest.TestCase):

    def setUp(self):
        self.canvas = DiagramCanvas()
        self.parsed_data = {
            "components": [
                ("supply", "Main Supply"),
                ("maincb", "Main Breaker 100A"),
                ("outcb_1", "Branch Breaker 1 16A"),
            ],
            "voltage": "230V",
        }
        self.canvas.original_parsed_data = copy.deepcopy(self.parsed_data)
        self.canvas.current_parsed_data = copy.deepcopy(self.parsed_data)
        doc = export_dxf(self.parsed_data, None)
        self.canvas.svg_widget.load_document(doc, {})

    def send_key(self, key, modifiers=Qt.KeyboardModifier.NoModifier):
        event = QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)
        self.canvas.svg_widget.keyPressEvent(event)

    def test_single_symbol_1mm_nudge(self):
        """1. Pressing arrow key moves current selection by 1mm per press."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)

        initial_pos = maincb.pos()
        self.send_key(Qt.Key.Key_Right)
        self.assertEqual(maincb.pos().x(), initial_pos.x() + 1.0)
        self.assertEqual(maincb.pos().y(), initial_pos.y())

        self.send_key(Qt.Key.Key_Down)
        self.assertEqual(maincb.pos().y(), initial_pos.y() + 1.0)

    def test_shift_arrow_10mm_nudge(self):
        """2. Holding Shift moves current selection by 10mm per press."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)

        initial_pos = maincb.pos()
        self.send_key(Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(maincb.pos().x(), initial_pos.x() - 10.0)

        self.send_key(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(maincb.pos().y(), initial_pos.y() - 10.0)

    def test_multi_selection_relative_spacing(self):
        """3. Multi-selection moves together, preserving relative spacing."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        outcb_1 = self.canvas.svg_widget.symbol_items["outcb_1"]

        maincb.setSelected(True)
        outcb_1.setSelected(True)

        init_maincb = maincb.pos()
        init_outcb = outcb_1.pos()
        initial_spacing = outcb_1.pos() - maincb.pos()

        self.send_key(Qt.Key.Key_Right)
        self.send_key(Qt.Key.Key_Right)

        self.assertEqual(maincb.pos().x(), init_maincb.x() + 2.0)
        self.assertEqual(outcb_1.pos().x(), init_outcb.x() + 2.0)

        new_spacing = outcb_1.pos() - maincb.pos()
        self.assertEqual(initial_spacing.x(), new_spacing.x())
        self.assertEqual(initial_spacing.y(), new_spacing.y())

    def test_locked_symbol_stay_in_place(self):
        """4. Locked symbols do not move during arrow key movement."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        outcb_1 = self.canvas.svg_widget.symbol_items["outcb_1"]

        maincb.setSelected(True)
        outcb_1.setSelected(True)
        maincb.toggle_lock()  # Lock maincb

        init_maincb = maincb.pos()
        init_outcb = outcb_1.pos()

        self.send_key(Qt.Key.Key_Right)

        # Locked maincb stays in place
        self.assertEqual(maincb.pos(), init_maincb)
        # Unlocked outcb_1 moves by 1mm
        self.assertEqual(outcb_1.pos().x(), init_outcb.x() + 1.0)

    def test_undo_granularity_per_press(self):
        """5. Each individual key press is its own separate undo entry."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)
        init_pos = maincb.pos()

        # Press Left 3 times
        self.send_key(Qt.Key.Key_Left)
        self.send_key(Qt.Key.Key_Left)
        self.send_key(Qt.Key.Key_Left)

        self.assertEqual(maincb.pos().x(), init_pos.x() - 3.0)

        # Undo step 1
        self.canvas.undo_manager.undo()
        self.assertEqual(maincb.pos().x(), init_pos.x() - 2.0)

        # Undo step 2
        self.canvas.undo_manager.undo()
        self.assertEqual(maincb.pos().x(), init_pos.x() - 1.0)

        # Undo step 3
        self.canvas.undo_manager.undo()
        self.assertEqual(maincb.pos().x(), init_pos.x())

    def test_text_editing_guard(self):
        """6. Arrow keys do not move symbols while a label is actively being text-edited."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)

        # Find text child
        text_item = next(c for c in maincb.childItems() if isinstance(c, EditableTextItem))
        text_item.start_editing()

        init_pos = maincb.pos()
        self.send_key(Qt.Key.Key_Right)

        # Symbol position must NOT change while text item is editing
        self.assertEqual(maincb.pos(), init_pos)

    def test_persistence_component_position_overrides(self):
        """7. Resulting positions are written to component_position_overrides and survive reload."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)

        self.send_key(Qt.Key.Key_Right)
        self.send_key(Qt.Key.Key_Down)

        overrides = self.canvas.current_parsed_data.get("component_position_overrides", {})
        self.assertIn("maincb", overrides)
        expected_x = maincb.base_x + maincb.pos().x()
        expected_y = maincb.base_y - maincb.pos().y()

        self.assertAlmostEqual(overrides["maincb"]["position"][0], expected_x)
        self.assertAlmostEqual(overrides["maincb"]["position"][1], expected_y)

        target_x = maincb.pos().x()
        target_y = maincb.pos().y()

        # Export and reload document
        new_doc = export_dxf(self.canvas.current_parsed_data, None)
        self.canvas.svg_widget.load_document(new_doc, {})

        reloaded_maincb = self.canvas.svg_widget.symbol_items["maincb"]
        actual_modelspace_x = reloaded_maincb.base_x + reloaded_maincb.pos().x()
        actual_modelspace_y = reloaded_maincb.base_y - reloaded_maincb.pos().y()

        self.assertAlmostEqual(actual_modelspace_x, expected_x)
        self.assertAlmostEqual(actual_modelspace_y, expected_y)

    def test_section_group_undo(self):
        """8. Ctrl+Z undoes movement/resizing of section groups (Title Block, Legend, Load Schedule)."""
        legend = self.canvas.svg_widget.group_items.get("legend")
        if not legend:
            self.skipTest("No legend group in test document")

        init_pos = legend.pos()
        init_scale = legend.scale()

        # Simulate dragging legend
        self.canvas.svg_widget.store_layout_override("legend", QPointF(5.0, 5.0), init_scale, init_pos, init_scale)

        self.assertEqual(legend.pos(), QPointF(5.0, 5.0))
        self.assertEqual(legend.scale(), init_scale)

        # Undo via Ctrl+Z
        self.canvas.undo_manager.undo()

        self.assertEqual(legend.pos(), init_pos)
        self.assertEqual(legend.scale(), init_scale)

    def test_section_group_arrow_movement(self):
        """9. Arrow keys nudge selected section groups and support Ctrl+Z undo."""
        legend = self.canvas.svg_widget.group_items.get("legend")
        if not legend:
            self.skipTest("No legend group in test document")

        legend.setSelected(True)
        init_pos = legend.pos()

        self.send_key(Qt.Key.Key_Right)
        self.assertEqual(legend.pos().x(), init_pos.x() + 1.0)

        # Undo nudge
        self.canvas.undo_manager.undo()
        self.assertEqual(legend.pos().x(), init_pos.x())

    def test_text_label_undo_redo(self):
        """10. Editing label text visually updates on Ctrl+Z undo and Ctrl+Shift+Z redo."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        text_item = next(c for c in maincb.childItems() if isinstance(c, EditableTextItem))
        
        orig_text = text_item.toPlainText()
        
        text_item.start_editing()
        text_item.setPlainText("New Custom Text 100A")
        text_item.stop_editing()
        
        self.assertEqual(text_item.toPlainText(), "New Custom Text 100A")
        self.assertEqual(self.canvas.current_parsed_data.get("text_overrides", {}).get(text_item.label_id), "New Custom Text 100A")

        # Undo via Ctrl+Z
        self.canvas.undo_manager.undo()
        self.assertEqual(text_item.toPlainText(), orig_text)
        self.assertNotIn(text_item.label_id, self.canvas.current_parsed_data.get("text_overrides", {}))

        # Redo via Ctrl+Shift+Z
        self.canvas.undo_manager.redo()
        self.assertEqual(text_item.toPlainText(), "New Custom Text 100A")
        self.assertEqual(self.canvas.current_parsed_data.get("text_overrides", {}).get(text_item.label_id), "New Custom Text 100A")


if __name__ == "__main__":
    unittest.main()
