import unittest
import json
import copy
from PySide6.QtWidgets import QApplication
from ECD.undo_manager import UndoManager, DictStateCommand
from ECD.diagram_canvas import DiagramCanvas

# Ensure QApplication instance exists for QWidget tests
app = QApplication.instance() or QApplication([])


class TestPhase1DataModel(unittest.TestCase):

    def test_component_position_overrides_schema(self):
        """Test setting and retrieving component_position_overrides in parsed_data dict."""
        parsed_data = {
            "components": [("maincb", "Main Breaker"), ("outcb_1", "Branch Breaker 1")],
            "voltage": "230V",
        }
        
        # Add overrides
        pos_overrides = parsed_data.setdefault("component_position_overrides", {})
        pos_overrides["maincb"] = {"position": [12.5, 4.0]}
        pos_overrides["outcb_1"] = {"position": [-8.0, 30.2]}

        # Text overrides
        txt_overrides = parsed_data.setdefault("text_overrides", {})
        txt_overrides["maincb.label"] = "Custom Main Breaker 100A"

        self.assertIn("component_position_overrides", parsed_data)
        self.assertEqual(parsed_data["component_position_overrides"]["maincb"]["position"], [12.5, 4.0])
        self.assertEqual(parsed_data["component_position_overrides"]["outcb_1"]["position"], [-8.0, 30.2])
        self.assertEqual(parsed_data["text_overrides"]["maincb.label"], "Custom Main Breaker 100A")

    def test_json_roundtrip_persistence(self):
        """Test JSON serialization and deserialization of component_position_overrides."""
        original_data = {
            "components": [("maincb", "Main Breaker")],
            "component_position_overrides": {
                "maincb": {"position": [15.0, 20.0]},
                "load_1": {"position": [40.0, -10.0]}
            },
            "text_overrides": {
                "maincb.label": "Main Breaker 100A"
            }
        }

        # Serialize
        json_str = json.dumps(original_data, ensure_ascii=False, indent=2)

        # Deserialize
        loaded_data = json.loads(json_str)

        self.assertEqual(loaded_data["component_position_overrides"]["maincb"]["position"], [15.0, 20.0])
        self.assertEqual(loaded_data["component_position_overrides"]["load_1"]["position"], [40.0, -10.0])
        self.assertEqual(loaded_data["text_overrides"]["maincb.label"], "Main Breaker 100A")

    def test_revert_to_original_clears_all_overrides_and_undo_stack(self):
        """Test that revert_to_original clears layout_overrides, text_overrides, component_position_overrides, and clears UndoManager history."""
        canvas = DiagramCanvas()

        baseline_data = {
            "components": [("maincb", "Main Breaker")],
            "voltage": "230V",
        }

        canvas.original_parsed_data = copy.deepcopy(baseline_data)
        canvas.current_parsed_data = copy.deepcopy(baseline_data)

        # Add overrides to current_parsed_data
        canvas.current_parsed_data["layout_overrides"] = {"title_block": {"position": [10, 10]}}
        canvas.current_parsed_data["text_overrides"] = {"maincb.label": "Edited Label"}
        canvas.current_parsed_data["component_position_overrides"] = {"maincb": {"position": [5.0, 5.0]}}

        # Push a dummy undo command
        cmd = DictStateCommand("Move Symbol", lambda: None, lambda: None)
        canvas.undo_manager.push(cmd)
        self.assertTrue(canvas.undo_manager.can_undo())

        # Perform Revert to Original
        canvas.revert_to_original()

        # Verify all overrides cleared
        self.assertNotIn("layout_overrides", canvas.current_parsed_data)
        self.assertNotIn("text_overrides", canvas.current_parsed_data)
        self.assertNotIn("component_position_overrides", canvas.current_parsed_data)
        self.assertNotIn("layout_overrides", canvas.original_parsed_data)
        self.assertNotIn("text_overrides", canvas.original_parsed_data)
        self.assertNotIn("component_position_overrides", canvas.original_parsed_data)

        # Verify UndoManager stack cleared (new session started)
        self.assertFalse(canvas.undo_manager.can_undo())
        self.assertFalse(canvas.undo_manager.can_redo())

    def test_undo_manager_stack(self):
        """Test UndoManager push, undo, redo, and clear methods."""
        mgr = UndoManager()

        self.assertEqual(mgr.count, 0)
        self.assertFalse(mgr.can_undo())
        self.assertFalse(mgr.can_redo())

        state = {"value": "initial"}

        def do_change(val):
            state["value"] = val

        cmd = DictStateCommand("Change Value", lambda: do_change("new"), lambda: do_change("initial"))
        mgr.push(cmd)

        # Initial push executes
        do_change("new")
        self.assertEqual(state["value"], "new")
        self.assertEqual(mgr.count, 1)
        self.assertTrue(mgr.can_undo())

        # Undo
        mgr.undo()
        self.assertEqual(state["value"], "initial")
        self.assertTrue(mgr.can_redo())

        # Redo
        mgr.redo()
        self.assertEqual(state["value"], "new")

        # Clear
        mgr.clear()
        self.assertEqual(mgr.count, 0)
        self.assertFalse(mgr.can_undo())
        self.assertFalse(mgr.can_redo())


if __name__ == "__main__":
    unittest.main()
