import unittest
import sys
import os

# Ensure the parent directory is in the path so we can import ECD
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ECD.pin_model import (
    PinDef,
    COMPONENT_PINS,
    get_pin_position,
    compute_component_positions,
    generate_netlist,
    validate_netlist
)

class PinModelTests(unittest.TestCase):
    def test_pin_definitions_exist_for_all_8_types(self):
        expected_types = ["supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "outcb", "loads"]
        for t in expected_types:
            self.assertIn(t, COMPONENT_PINS)
            self.assertGreater(len(COMPONENT_PINS[t]), 0)

    def test_get_pin_position(self):
        # Center at (10, 20)
        # maincb L_in has offset (0, 10)
        pos = get_pin_position("maincb", "L_in", (10.0, 20.0))
        self.assertEqual(pos, (10.0, 30.0))
        
        # supply N_out has offset (-45, -10)
        pos = get_pin_position("supply", "N_out", (10.0, 20.0))
        self.assertEqual(pos, (-35.0, 10.0))

        # Test invalid pin raises ValueError
        with self.assertRaises(ValueError):
            get_pin_position("maincb", "InvalidPin", (10.0, 20.0))

    def test_compute_component_positions_single_load(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("loads", "Loads"),
            ]
        }
        positions = compute_component_positions(parsed_data)
        
        # main vertical column checks (x = 0)
        self.assertEqual(positions["supply"][0], 0.0)
        self.assertEqual(positions["maincb"][0], 0.0)
        self.assertEqual(positions["rcd"][0], 0.0)
        self.assertEqual(positions["bus"][0], 0.0)
        
        # Check vertical stacking order
        self.assertTrue(positions["supply"][1] > positions["maincb"][1])
        self.assertTrue(positions["maincb"][1] > positions["rcd"][1])
        self.assertTrue(positions["rcd"][1] > positions["bus"][1])
        
        # Side bars checks
        self.assertEqual(positions["nbar"], (-45.0, positions["bus"][1]))
        self.assertEqual(positions["ebar"], (-60.0, positions["bus"][1] - 19.0)) # H_STEP / 2 = 19
        
        # Single load check
        self.assertEqual(positions["loads"], (0.0, positions["bus"][1] - 38.0))

    def test_compute_component_positions_multi_load(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("outcb_1", "Lighting CB"),
                ("outcb_2", "Socket CB"),
                ("loads", "Loads"),
            ]
        }
        positions = compute_component_positions(parsed_data)
        
        # Busbar position
        bus_y = positions["bus"][1]
        
        # outcb_1 and outcb_2 should be spread horizontally at y = bus_y - 38
        self.assertEqual(positions["outcb_1"][1], bus_y - 38.0)
        self.assertEqual(positions["outcb_2"][1], bus_y - 38.0)
        
        # X positions: spacing = 30, n = 2, start_x = -15
        self.assertEqual(positions["outcb_1"][0], -15.0)
        self.assertEqual(positions["outcb_2"][0], 15.0)
        
        # Corresponding virtual loads
        self.assertEqual(positions["load_1"], (-15.0, bus_y - 76.0))
        self.assertEqual(positions["load_2"], (15.0, bus_y - 76.0))

    def test_generate_and_validate_correct_netlist(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("outcb_1", "Lighting CB"),
                ("outcb_2", "Socket CB"),
                ("loads", "Loads"),
            ],
            "flags": {
                "show_neutral": True,
                "show_earth": True
            }
        }
        positions = compute_component_positions(parsed_data)
        netlist = generate_netlist(parsed_data, positions)
        
        # Check components list
        self.assertIn("supply", netlist["components"])
        self.assertIn("maincb", netlist["components"])
        self.assertIn("rcd", netlist["components"])
        self.assertIn("bus", netlist["components"])
        self.assertIn("nbar", netlist["components"])
        self.assertIn("ebar", netlist["components"])
        self.assertIn("outcb_1", netlist["components"])
        self.assertIn("outcb_2", netlist["components"])
        # Expanded virtual loads should be present instead of 'loads'
        self.assertNotIn("loads", netlist["components"])
        self.assertIn("load_1", netlist["components"])
        self.assertIn("load_2", netlist["components"])
        
        # Verify connections count
        self.assertGreater(len(netlist["connections"]), 0)
        
        # Run validation pass
        is_valid, errors = validate_netlist(netlist)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")

    def test_validate_broken_netlist_fails(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("loads", "Loads"),
            ],
            "flags": {
                "show_neutral": True,
                "show_earth": True
            }
        }
        positions = compute_component_positions(parsed_data)
        netlist = generate_netlist(parsed_data, positions)
        
        # Intentionally break the netlist: delete the L connection to the load
        l_conns = [c for c in netlist["connections"] if c["dst_component"] == "loads" and c["wire_type"] == "L"]
        for conn in l_conns:
            netlist["connections"].remove(conn)
            
        # Validation should fail
        is_valid, errors = validate_netlist(netlist)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing a Phase (L) connection" in err or "Phase (L) path" in err for err in errors))

    def test_no_duplicate_connections(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("loads", "Loads"),
            ],
            "flags": {
                "show_neutral": True,
                "show_earth": True
            }
        }
        positions = compute_component_positions(parsed_data)
        netlist = generate_netlist(parsed_data, positions)
        
        # Explicitly check for duplicate connections in the output list
        seen = set()
        for conn in netlist["connections"]:
            key = (conn["src_component"], conn["src_pin"], conn["dst_component"], conn["dst_pin"])
            self.assertNotIn(key, seen, f"Found duplicate connection: {key}")
            seen.add(key)

    def test_dynamic_tap_coordinates(self):
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("rcd", "RCD"),
                ("bus", "Busbar"),
                ("nbar", "Neutral Bar"),
                ("ebar", "Earth Bar"),
                ("outcb_1", "Lighting CB"),
                ("outcb_2", "Socket CB"),
                ("loads", "Loads"),
            ],
            "flags": {
                "show_neutral": True,
                "show_earth": True
            }
        }
        positions = compute_component_positions(parsed_data)
        netlist = generate_netlist(parsed_data, positions)
        
        bus_y = positions["bus"][1]
        
        # Verify bus -> outcb_1 L wire taps bus at outcb_1's X coordinate (-15.0)
        bus_conn_1 = next(c for c in netlist["connections"] if c["src_component"] == "bus" and c["dst_component"] == "outcb_1")
        self.assertEqual(bus_conn_1["src_pos"], [-15.0, bus_y])
        
        # Verify bus -> outcb_2 L wire taps bus at outcb_2's X coordinate (15.0)
        bus_conn_2 = next(c for c in netlist["connections"] if c["src_component"] == "bus" and c["dst_component"] == "outcb_2")
        self.assertEqual(bus_conn_2["src_pos"], [15.0, bus_y])
        
        # Verify nbar -> load_1 N wire taps N-rail at load_1's Y coordinate and x = -45.0
        nbar_conn_1 = next(c for c in netlist["connections"] if c["src_component"] == "nbar" and c["dst_component"] == "load_1")
        load_1_y = positions["load_1"][1]
        self.assertEqual(nbar_conn_1["src_pos"], [-45.0, load_1_y])
        
        # Verify ebar -> load_1 E wire taps E-rail at load_1's E_in Y coordinate (load_1_y - 4.0) and x = -60.0
        ebar_conn_1 = next(c for c in netlist["connections"] if c["src_component"] == "ebar" and c["dst_component"] == "load_1")
        self.assertEqual(ebar_conn_1["src_pos"], [-60.0, load_1_y - 4.0])

    def test_incompatible_connections_skipped(self):
        from ECD.dxf_generator import ensure_connections
        parsed_data = {
            "components": [
                ("supply", "Supply"),
                ("maincb", "Main Breaker"),
                ("ebar", "Earth Bar"),
                ("loads", "Loads")
            ],
            "connections": [
                ("supply", "maincb"),
                ("maincb", "loads"),
                ("maincb", "ebar"),     # Incompatible connection
                ("ebar", "rcd"),        # Incompatible connection
            ],
            "voltage": "230V",
            "phase_hint": "single"
        }
        connections = ensure_connections(parsed_data)
        # Verify the incompatible connections are skipped
        self.assertIn(("supply", "maincb"), connections)
        self.assertNotIn(("maincb", "ebar"), connections)
        self.assertNotIn(("ebar", "rcd"), connections)


if __name__ == "__main__":
    unittest.main()
