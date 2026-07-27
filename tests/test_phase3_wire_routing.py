import unittest
import copy
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from ECD.diagram_canvas import DiagramCanvas
from ECD.dxf_generator import export_dxf, route_wire_bend
from ECD.pin_model import get_pin_position

app = QApplication.instance() or QApplication([])


class TestPhase3WireRouting(unittest.TestCase):

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

    def test_wire_items_population(self):
        """Test that wire items are populated during load_document from netlist connections."""
        wire_items = self.canvas.svg_widget.wire_items
        self.assertGreater(len(wire_items), 0)

        # Check wire structure
        wire = wire_items[0]
        self.assertIn("src_cid", wire)
        self.assertIn("dst_cid", wire)
        self.assertIn("item", wire)
        self.assertIsNotNone(wire["item"].path())

    def test_live_connected_wire_update_on_drag(self):
        """Test that update_connected_wires updates paths for moved symbols only (Q12, Q21)."""
        wire_items = self.canvas.svg_widget.wire_items

        # Find wire connecting maincb -> outcb_1
        target_wire = None
        for w in wire_items:
            if w["src_cid"] == "maincb" or w["dst_cid"] == "maincb":
                target_wire = w
                break
        self.assertIsNotNone(target_wire)

        path_before = target_wire["item"].path()

        # Simulate moving maincb
        maincb_item = self.canvas.svg_widget.symbol_items.get("maincb")
        self.assertIsNotNone(maincb_item)
        maincb_item.setPos(50.0, -30.0)

        # Trigger live wire update
        self.canvas.svg_widget.update_connected_wires({"maincb"})

        path_after = target_wire["item"].path()
        self.assertNotEqual(path_before, path_after)

    def test_manhattan_route_wire_bend(self):
        """Test route_wire_bend orthogonal Manhattan 90-degree bend calculation."""
        p1 = (0.0, 100.0)
        p2 = (50.0, 20.0)

        bend_pts = route_wire_bend(p1, p2)
        self.assertEqual(len(bend_pts), 3)
        self.assertEqual(bend_pts[0], (0.0, 100.0))
        self.assertEqual(bend_pts[1], (0.0, 20.0))
        self.assertEqual(bend_pts[2], (50.0, 20.0))

    def test_pin_position_resolution(self):
        """Test resolving absolute pin coordinates for component positions."""
        pos = (10.0, 20.0)
        pin_pos = get_pin_position("maincb", "L_out", pos, "single")
        self.assertEqual(pin_pos, (10.0, 10.0))  # 20.0 - 10.0 = 10.0

    def test_wire_path_restored_on_undo(self):
        """Test that connected wires restore their original path on Ctrl+Z undo."""
        wire_items = self.canvas.svg_widget.wire_items
        target_wire = next(w for w in wire_items if w["src_cid"] == "maincb" or w["dst_cid"] == "maincb")
        path_initial = target_wire["item"].path()

        maincb_item = self.canvas.svg_widget.symbol_items["maincb"]
        init_p = maincb_item.pos()

        # Move item and commit position override
        maincb_item.setPos(50.0, -20.0)
        self.canvas.svg_widget.update_connected_wires({"maincb"})
        overrides = {"maincb": [maincb_item.base_x + 50.0, maincb_item.base_y - 20.0]}
        initial_positions = {maincb_item: init_p}
        self.canvas.svg_widget.store_component_position_overrides(overrides, initial_positions)

        path_moved = target_wire["item"].path()
        self.assertNotEqual(path_initial, path_moved)

        # Trigger Undo (Ctrl+Z)
        self.canvas.undo_manager.undo()
        path_undone = target_wire["item"].path()
        self.assertEqual(path_initial, path_undone)


if __name__ == "__main__":
    unittest.main()
