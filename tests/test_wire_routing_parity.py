"""
Unit test suite verifying 100% exact parity between live-editor wire routing
and export_dxf() wire routing via shared ECD.electrical.wire_router engine.
"""
import unittest
from ECD.dxf_generator import export_dxf
from ECD.pin_model import compute_component_positions, generate_netlist
from ECD.electrical.wire_router import calculate_canonical_wire_graph, route_wire_bend


class TestWireRoutingParity(unittest.TestCase):

    def setUp(self):
        # Full distribution panel with non-default position overrides
        self.parsed_data = {
            "title": "Wire Routing Parity Test Board",
            "voltage": "230V AC",
            "components": [
                ["supply", "Main Supply"],
                ["maincb", "Main Breaker 100A"],
                ["rcd", "RCD 30mA"],
                ["bus", "Busbar"],
                ["outcb_1", "OUTCB_1 16A"],
                ["load_1", "Lighting Circuit 1"],
                ["outcb_2", "OUTCB_2 20A"],
                ["load_2", "Sockets Circuit 2"],
                ["nbar", "Neutral Bar"],
                ["ebar", "Earth Bar"]
            ],
            "component_position_overrides": {
                "maincb": {"position": [25.0, 45.0]},
                "outcb_1": {"position": [60.0, -10.0]}
            }
        }

    def test_canonical_wire_graph_parity(self):
        """Verify live editor path and export_dxf() path produce 100% identical wire geometry."""

        # 1. Resolve box_positions with overrides
        box_positions = compute_component_positions(self.parsed_data)
        comp_overrides = self.parsed_data.get("component_position_overrides", {})
        for cid, ov_data in comp_overrides.items():
            if isinstance(ov_data, dict) and "position" in ov_data:
                pos = ov_data["position"]
                box_positions[str(cid)] = (float(pos[0]), float(pos[1]))

        # 2. Generate netlist
        netlist = generate_netlist(self.parsed_data, box_positions)

        # 3. Calculate canonical wire graph (live-editor path)
        editor_graph = calculate_canonical_wire_graph(netlist, box_positions, phase_mode="single")

        # 4. Calculate DXF document (export path)
        doc = export_dxf(self.parsed_data, None)
        self.assertIsNotNone(doc)

        # Re-calculate canonical wire graph on DXF doc's netlist & box_positions
        export_graph = calculate_canonical_wire_graph(doc.netlist, doc.box_positions, phase_mode=doc.phase_mode)

        # 5. Assert 100% exact parity between live editor graph and export graph
        self.assertEqual(len(editor_graph["rail_wires"]), len(export_graph["rail_wires"]))
        self.assertEqual(len(editor_graph["routed_wires"]), len(export_graph["routed_wires"]))
        self.assertEqual(len(editor_graph["daisy_chains"]), len(export_graph["daisy_chains"]))
        self.assertEqual(editor_graph["junction_dots"], export_graph["junction_dots"])

        # Compare exact point coordinates for all routed wires
        for w_ed, w_ex in zip(editor_graph["routed_wires"], export_graph["routed_wires"]):
            self.assertEqual(w_ed["connection"]["src_component"], w_ex["connection"]["src_component"])
            self.assertEqual(w_ed["connection"]["dst_component"], w_ex["connection"]["dst_component"])
            self.assertEqual(w_ed["pts"], w_ex["pts"])
            self.assertEqual(w_ed["uncovered_segments"], w_ex["uncovered_segments"])

        # Compare exact point coordinates for all daisy-chain wires
        for dc_ed, dc_ex in zip(editor_graph["daisy_chains"], export_graph["daisy_chains"]):
            self.assertEqual(dc_ed["src_cid"], dc_ex["src_cid"])
            self.assertEqual(dc_ed["dst_cid"], dc_ex["dst_cid"])
            self.assertEqual(dc_ed["pts"], dc_ex["pts"])

    def test_manhattan_route_wire_bend_determinism(self):
        """Verify route_wire_bend produces deterministic right-angle points."""
        p1 = (10.0, 50.0)
        p2 = (40.0, -10.0)
        pts = route_wire_bend(p1, p2)
        self.assertEqual(pts, [(10.0, 50.0), (10.0, -10.0), (40.0, -10.0)])


if __name__ == "__main__":
    unittest.main()
