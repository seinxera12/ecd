"""Unit test suite for Phase 5 Persistence and Full Regression Pass."""
import os
import json
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ECD.diagram_canvas import DiagramCanvas, DiagramGroupItem, SymbolItem, EditableTextItem
from ECD.dxf_generator import export_dxf


class TestPhase5PersistenceAndRegression(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = DiagramCanvas()
        self.parsed_data = {
            "title": "Phase 5 Persistence & Regression Test Panel",
            "voltage": "230V AC",
            "components": [
                ["supply", "Main Supply"],
                ["maincb", "Main Breaker 100A"],
                ["rcd", "RCD 30mA"],
                ["bus", "Busbar"],
                ["outcb_1", "OUTCB_1 16A"],
                ["load_1", "Lighting Circuit 1"],
                ["nbar", "Neutral Bar"],
                ["ebar", "Earth Bar"]
            ]
        }
        self.doc = export_dxf(self.parsed_data, None)
        self.canvas.current_doc = self.doc
        self.canvas.current_parsed_data = self.parsed_data.copy()
        self.canvas.original_parsed_data = self.parsed_data.copy()
        self.canvas.svg_widget.load_document(self.doc, {})

    def test_json_persistence_save_and_load(self):
        """1. Verify save to JSON and reload preserves per-symbol, text, and group overrides."""
        # Make a symbol override
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        initial_pos = maincb.pos()
        maincb.setSelected(True)
        maincb.setPos(initial_pos.x() + 15.0, initial_pos.y() - 10.0)
        
        # Save to dict / JSON format
        save_data = dict(self.canvas.current_parsed_data)
        save_data["component_position_overrides"] = {
            "maincb": {"position": [maincb.base_x + 15.0, maincb.base_y + 10.0]}
        }
        save_data["text_overrides"] = {
            "maincb.label": "Edited Main Breaker 125A"
        }
        save_data["layout_overrides"] = {
            "legend": {"position": [5.0, 5.0], "scale": 1.1}
        }
        
        json_path = os.path.join("scratch", "test_phase5_persistence.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2)

        # Re-load into canvas
        with open(json_path, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        self.canvas.current_parsed_data = loaded_data
        self.canvas.original_parsed_data = loaded_data.copy()
        new_doc = export_dxf(loaded_data, None)
        self.canvas.svg_widget.load_document(new_doc, loaded_data.get("layout_overrides", {}))

        # Check loaded overrides
        self.assertEqual(loaded_data["component_position_overrides"]["maincb"]["position"], [maincb.base_x + 15.0, maincb.base_y + 10.0])
        self.assertEqual(loaded_data["text_overrides"]["maincb.label"], "Edited Main Breaker 125A")
        self.assertEqual(loaded_data["layout_overrides"]["legend"]["scale"], 1.1)

    def test_restore_generated_layout_resets_history(self):
        """2. Verify Restore Generated Layout clears overrides and resets undo history stack."""
        maincb = self.canvas.svg_widget.symbol_items["maincb"]
        maincb.setSelected(True)
        
        # Move maincb
        self.canvas.svg_widget.store_component_position_overrides(
            {"maincb": [20.0, 40.0]}, {"maincb": maincb.pos()}
        )
        self.assertTrue(self.canvas.undo_manager.can_undo())
        self.assertIn("maincb", self.canvas.current_parsed_data.get("component_position_overrides", {}))

        # Perform Revert / Restore Generated Layout
        self.canvas.revert_to_original()
        self.assertNotIn("component_position_overrides", self.canvas.current_parsed_data)
        self.assertFalse(self.canvas.undo_manager.can_undo())

    def test_section_group_regression(self):
        """3. Verify section groups (Title Block, Legend, Load Schedule) move & support undo."""
        legend = self.canvas.svg_widget.group_items.get("legend")
        if not legend:
            self.skipTest("No legend group in test document")

        init_pos = legend.pos()
        legend.setSelected(True)
        
        # Move legend
        legend.setPos(init_pos.x() + 5.0, init_pos.y() + 5.0)
        self.canvas.svg_widget.store_layout_override("legend", (init_pos.x() + 5.0, init_pos.y() + 5.0), 1.0, (init_pos.x(), init_pos.y()), 1.0)
        
        self.assertTrue(self.canvas.undo_manager.can_undo())
        self.canvas.undo_manager.undo()
        self.assertEqual(legend.pos(), init_pos)


if __name__ == "__main__":
    unittest.main()
