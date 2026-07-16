"""
run_diagram_tests.py
====================
Generates single-line diagrams for three distinct panel test cases,
exports them to DXF, and renders each to a PNG file stored directly
in the artifacts directory.
"""

from __future__ import annotations
import os
import sys
import matplotlib
matplotlib.use('Agg')  # Headless mode for Matplotlib
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# Ensure parent directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ECD.dxf_generator import export_dxf, render_doc_to_png, render_doc_to_svg, render_doc_to_pdf

ARTIFACT_DIR = r"C:\Users\Administrator\.gemini\antigravity-ide\brain\1bb65dcf-dde7-4a82-88af-67926f6e7c48"

def render_dxf_to_png(dxf_path: str, png_path: str) -> None:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Rendered PNG: {png_path}")

def run_tests():
    # Ensure export directory exists
    os.makedirs("exports", exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # 1. Minimal Panel (Supply + MainCB + Load)
    minimal_data = {
        "components": [
            ("supply", "Supply Source | 230V AC"),
            ("maincb", "Main MCB | 32A"),
            ("loads", "Single Load"),
        ],
        "flags": {
            "show_neutral": True,
            "show_earth": True
        },
        "voltage": "230V AC",
        "language": "en"
    }

    # 2. Full Panel (All 8 component types + RCD + nbar + ebar)
    full_data = {
        "components": [
            ("supply", "Supply | TN-S Grid"),
            ("maincb", "Main CB | 63A"),
            ("rcd", "Main RCD | 30mA"),
            ("rcbo", "Branch RCBO | 16A"),
            ("bus", "L-Busbar"),
            ("nbar", "Neutral Bar"),
            ("ebar", "Earth Bar"),
            ("outcb_1", "Outgoing MCB | 10A"),
            ("loads", "Loads"),
        ],
        "flags": {
            "show_neutral": True,
            "show_earth": True,
            "show_fault_paths": True,
            "show_protection_notes": True
        },
        "voltage": "230V AC",
        "language": "en"
    }

    # 3. Multi-circuit Panel (5+ outcb_N circuits)
    multi_data = {
        "components": [
            ("supply", "Main Power Supply"),
            ("maincb", "Main CB | 40A"),
            ("rcd", "RCD | 30mA"),
            ("bus", "Busbar"),
            ("nbar", "Neutral Bar"),
            ("ebar", "Earth Bar"),
            ("outcb_1", "MCB 1 | Lighting"),
            ("outcb_2", "MCB 2 | Sockets"),
            ("outcb_3", "MCB 3 | Heating"),
            ("outcb_4", "MCB 4 | AC"),
            ("outcb_5", "MCB 5 | EV Charger"),
            ("loads", "Loads"),
        ],
        "flags": {
            "show_neutral": True,
            "show_earth": True
        },
        "voltage": "230V AC",
        "language": "en"
    }

    # 4. Full Panel with Fault Paths enabled
    fault_path_data = {
        "components": [
            ("supply", "Supply | TN-S Grid"),
            ("maincb", "Main CB | 63A"),
            ("rcd", "Main RCD | 30mA"),
            ("bus", "L-Busbar"),
            ("nbar", "Neutral Bar"),
            ("ebar", "Earth Bar"),
            ("outcb_1", "Outgoing MCB | 10A"),
            ("loads", "Loads"),
        ],
        "flags": {
            "show_neutral": True,
            "show_earth": True,
            "show_fault_paths": True,
            "show_protection_notes": True
        },
        "voltage": "230V AC",
        "language": "en"
    }

    # 5. Stress case (8+ circuits with neutral, earth, fault paths, and notes)
    stress_data = {
        "components": [
            ("supply", "Supply | Stress Test Grid"),
            ("maincb", "Main CB | 100A"),
            ("rcd", "Main RCD | 100mA"),
            ("bus", "L-Busbar"),
            ("nbar", "Neutral Bar"),
            ("ebar", "Earth Bar"),
            ("outcb_1", "MCB 1 | Lighting"),
            ("outcb_2", "MCB 2 | Sockets"),
            ("outcb_3", "MCB 3 | Heating"),
            ("outcb_4", "MCB 4 | AC"),
            ("outcb_5", "MCB 5 | EV Charger"),
            ("outcb_6", "MCB 6 | Pumps"),
            ("outcb_7", "MCB 7 | Solar Inverter"),
            ("outcb_8", "MCB 8 | Aux Circuit"),
            ("loads", "Loads"),
        ],
        "flags": {
            "show_neutral": True,
            "show_earth": True,
            "show_fault_paths": True,
            "show_protection_notes": True
        },
        "voltage": "230V AC",
        "language": "en"
    }

    test_cases = [
        ("minimal", minimal_data),
        ("full", full_data),
        ("multi", multi_data),
        ("fault_path", fault_path_data),
        ("stress", stress_data)
    ]

    for name, parsed_data in test_cases:
        dxf_path = os.path.join(ARTIFACT_DIR, f"test_{name}.dxf")
        png_path = os.path.join(ARTIFACT_DIR, f"test_{name}.png")
        svg_path = os.path.join(ARTIFACT_DIR, f"test_{name}.svg")
        pdf_path = os.path.join(ARTIFACT_DIR, f"test_{name}.pdf")
        
        print(f"\n--- Generating: {name} ---")
        doc = export_dxf(parsed_data, None)
        doc.saveas(dxf_path)
        print(f"Generated and saved DXF: {dxf_path}")
        
        render_doc_to_png(doc, png_path)
        print(f"Rendered PNG: {png_path}")
        
        svg_str = render_doc_to_svg(doc)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_str)
        print(f"Rendered SVG: {svg_path}")
        
        render_doc_to_pdf(doc, pdf_path)
        print(f"Rendered PDF: {pdf_path}")

if __name__ == "__main__":
    run_tests()
