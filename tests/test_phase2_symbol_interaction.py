import unittest
import copy
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from ECD.diagram_canvas import DiagramCanvas, SymbolItem, EditableTextItem
from ECD.dxf_generator import export_dxf

app = QApplication.instance() or QApplication([])


class TestPhase2SymbolInteraction(unittest.TestCase):

    def setUp(self):
        self.canvas = DiagramCanvas()
        self.parsed_data = {
            "components": [
                ("supply", "Main Supply"),
                ("maincb", "Main Breaker 100A"),
                ("outcb_1", "Branch Breaker 1 16A"),
                ("outcb_2", "Branch Breaker 2 16A"),
            ],
            "voltage": "230V",
        }
        self.canvas.original_parsed_data = copy.deepcopy(self.parsed_data)
        self.canvas.current_parsed_data = copy.deepcopy(self.parsed_data)
        doc = export_dxf(self.parsed_data, None)
        self.canvas.svg_widget.load_document(doc, {})

    def test_symbol_items_instantiation(self):
        """Test that per-symbol SymbolItems are instantiated for main diagram components."""
        symbol_items = self.canvas.svg_widget.symbol_items
        self.assertIn("maincb", symbol_items)
        self.assertIn("outcb_1", symbol_items)
        self.assertIn("outcb_2", symbol_items)
        self.assertIn("supply", symbol_items)

        item = symbol_items["maincb"]
        self.assertIsInstance(item, SymbolItem)
        self.assertTrue(item.flags() & SymbolItem.GraphicsItemFlag.ItemIsMovable)
        self.assertTrue(item.flags() & SymbolItem.GraphicsItemFlag.ItemIsSelectable)

    def test_selection_z_order(self):
        """Test that selecting a SymbolItem brings it to front Z-order (100.0)."""
        item = self.canvas.svg_widget.symbol_items["maincb"]
        self.assertEqual(item.zValue(), 1.0)

        # Select item
        item.setSelected(True)
        self.assertEqual(item.zValue(), 100.0)

        # Unselect item
        item.setSelected(False)
        self.assertEqual(item.zValue(), 1.0)

    def test_lock_toggle_and_drag_filtering(self):
        """Test locked symbol toggle and that locked symbols stay stationary during drag."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        outcb_1 = self.canvas.svg_widget.symbol_items["outcb_1"]

        # Lock maincb
        maincb.toggle_lock()
        self.assertTrue(maincb.is_locked)

        # Select both
        maincb.setSelected(True)
        outcb_1.setSelected(True)

        init_pos_main = maincb.pos()
        init_pos_out1 = outcb_1.pos()

        # Simulate store overrides with delta
        delta = [20.0, 10.0]
        m_out1 = [outcb_1.base_x + init_pos_out1.x() + delta[0], outcb_1.base_y - (init_pos_out1.y() + delta[1])]
        overrides = {
            "outcb_1": m_out1
        }
        initial_positions = {outcb_1: init_pos_out1}
        self.canvas.svg_widget.store_component_position_overrides(overrides, initial_positions)

        # Outcb_1 moves, maincb stays fixed
        self.assertEqual(outcb_1.pos(), QPointF(init_pos_out1.x() + 20.0, init_pos_out1.y() + 10.0))
        self.assertEqual(maincb.pos(), init_pos_main)

    def test_multi_symbol_drag_relative_spacing(self):
        """Test multi-symbol drag preserves relative spacing and records 1 undo action."""
        outcb_1 = self.canvas.svg_widget.symbol_items["outcb_1"]
        outcb_2 = self.canvas.svg_widget.symbol_items["outcb_2"]

        p1_init = outcb_1.pos()
        p2_init = outcb_2.pos()

        delta_x, delta_y = 15.0, -10.0
        m1 = [outcb_1.base_x + p1_init.x() + delta_x, outcb_1.base_y - (p1_init.y() + delta_y)]
        m2 = [outcb_2.base_x + p2_init.x() + delta_x, outcb_2.base_y - (p2_init.y() + delta_y)]
        overrides = {
            "outcb_1": m1,
            "outcb_2": m2
        }
        initial_positions = {outcb_1: p1_init, outcb_2: p2_init}

        self.canvas.svg_widget.store_component_position_overrides(overrides, initial_positions)

        # Verify updated positions in canvas and parsed_data
        self.assertEqual(outcb_1.pos(), QPointF(p1_init.x() + delta_x, p1_init.y() + delta_y))
        self.assertEqual(outcb_2.pos(), QPointF(p2_init.x() + delta_x, p2_init.y() + delta_y))

        comp_ov = self.canvas.current_parsed_data["component_position_overrides"]
        self.assertEqual(comp_ov["outcb_1"]["position"], m1)
        self.assertEqual(comp_ov["outcb_2"]["position"], m2)

        # Test Undo
        self.assertTrue(self.canvas.undo_manager.can_undo())
        self.canvas.undo_manager.undo()

        self.assertEqual(outcb_1.pos(), p1_init)
        self.assertEqual(outcb_2.pos(), p2_init)

        # Test Redo
        self.assertTrue(self.canvas.undo_manager.can_redo())
        self.canvas.undo_manager.redo()

        self.assertEqual(outcb_1.pos(), QPointF(p1_init.x() + delta_x, p1_init.y() + delta_y))

    def test_text_override_single_undo_action(self):
        """Test that committing a label text edit records 1 undo action."""
        self.canvas.svg_widget.store_text_override("maincb.label", "Custom Main Breaker")
        txt_ov = self.canvas.current_parsed_data["text_overrides"]
        self.assertEqual(txt_ov["maincb.label"], "Custom Main Breaker")

        self.assertTrue(self.canvas.undo_manager.can_undo())
        self.canvas.undo_manager.undo()

        self.assertNotIn("maincb.label", self.canvas.current_parsed_data.get("text_overrides", {}))


if __name__ == "__main__":
    unittest.main()
