"""Unit tests for Phase 4 Export Integration (component_position_overrides & text_overrides in DXF, SVG, PNG, PDF)."""
import os
import unittest
from ECD.dxf_generator import export_dxf, render_doc_to_svg, render_doc_to_png, render_doc_to_pdf


class TestPhase4ExportIntegration(unittest.TestCase):

    def setUp(self):
        self.parsed_data = {
            "title": "Phase 4 Export Test Panel",
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
            ],
            "component_position_overrides": {
                "maincb": {"position": [25.0, 45.0]},
                "outcb_1": {"position": [60.0, -10.0]}
            },
            "text_overrides": {
                "maincb.label": "Custom Main Breaker 100A"
            }
        }

    def test_dxf_export_with_component_position_overrides(self):
        """Verify export_dxf applies component_position_overrides to block references, netlist, and text."""
        doc = export_dxf(self.parsed_data, None)
        self.assertIsNotNone(doc)

        # 1. Verify box_positions contains overridden coordinates
        self.assertEqual(doc.box_positions["maincb"], (25.0, 45.0))
        self.assertEqual(doc.box_positions["outcb_1"], (60.0, -10.0))

        # 2. Verify modelspace block reference inserts match overrides
        msp = doc.modelspace()
        maincb_bref = next((e for e in msp if e.dxftype() == "INSERT" and getattr(e, "component_id", None) == "maincb"), None)
        self.assertIsNotNone(maincb_bref)
        self.assertEqual(maincb_bref.dxf.insert.x, 25.0)
        self.assertEqual(maincb_bref.dxf.insert.y, 45.0)

        outcb1_bref = next((e for e in msp if e.dxftype() == "INSERT" and getattr(e, "component_id", None) == "outcb_1"), None)
        self.assertIsNotNone(outcb1_bref)
        self.assertEqual(outcb1_bref.dxf.insert.x, 60.0)
        self.assertEqual(outcb1_bref.dxf.insert.y, -10.0)

        # 3. Verify text label override is exported
        maincb_text = next((e for e in msp if e.dxftype() == "TEXT" and getattr(e, "label_id", None) == "maincb.label"), None)
        self.assertIsNotNone(maincb_text)
        self.assertEqual(maincb_text.dxf.text, "Custom Main Breaker 100A")

    def test_svg_png_pdf_export_rendering(self):
        """Verify SVG, PNG, and PDF exports generate cleanly with position overrides."""
        doc = export_dxf(self.parsed_data, None)
        self.assertIsNotNone(doc)

        # SVG export
        svg_str = render_doc_to_svg(doc)
        self.assertTrue(len(svg_str) > 0)
        self.assertIn("<svg", svg_str)

        # PNG export
        png_path = os.path.join("scratch", "test_phase4_export.png")
        render_doc_to_png(doc, png_path)
        self.assertTrue(os.path.exists(png_path))
        self.assertTrue(os.path.getsize(png_path) > 0)

        # PDF export
        pdf_path = os.path.join("scratch", "test_phase4_export.pdf")
        render_doc_to_pdf(doc, pdf_path)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(os.path.getsize(pdf_path) > 0)


if __name__ == "__main__":
    unittest.main()
