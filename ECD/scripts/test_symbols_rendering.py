"""
test_symbols_rendering.py
=========================
Standalone test script to render all the built DXF symbols in a grid layout
into one scratch DXF file.

Run:
    venv\\Scripts\\python.exe test_symbols_rendering.py
    
Open:
    test_symbols_rendering.dxf (in QCAD or LibreCAD) to inspect.
"""

from __future__ import annotations
import sys
import os
import ezdxf
from ezdxf.enums import TextEntityAlignment

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ECD.symbols import (
    register_all_symbols,
    get_or_create_terminal_row,
    init_symbols_layer
)

def main():
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric
    
    # Initialize symbols and layer
    init_symbols_layer(doc)
    register_all_symbols(doc)
    
    # Register some dynamic terminal block rows
    get_or_create_terminal_row(doc, n=2)
    get_or_create_terminal_row(doc, n=4)
    get_or_create_terminal_row(doc, n=6)
    
    msp = doc.modelspace()
    
    # Layout symbols in a grid
    # Column X coordinates (widened to 40 to accommodate three-phase symbols)
    x_coords = [0.0, 40.0, 80.0, 120.0, 160.0]
    
    # Row Y coordinates
    y_row1 = 100.0   # Single-phase row 1
    y_row2 = 60.0    # Single-phase row 2
    y_row3 = 20.0    # Three-phase row 3
    y_row4 = -30.0   # Three-phase row 4
    
    # Helper to add a label below the insertion point
    def add_label(text: str, x: float, y: float):
        msp.add_text(
            text,
            dxfattribs={"height": 2.0, "layer": "SYMBOLS"}
        ).set_placement((x, y - 15.0), align=TextEntityAlignment.MIDDLE_CENTER)
        
    # --- Row 1: Single-phase symbols ---
    # 1. SYM_BREAKER
    msp.add_blockref("SYM_BREAKER", insert=(x_coords[0], y_row1))
    add_label("SYM_BREAKER", x_coords[0], y_row1)
    
    # 2. SYM_MCB
    msp.add_blockref("SYM_MCB", insert=(x_coords[1], y_row1))
    add_label("SYM_MCB", x_coords[1], y_row1)
    
    # 3. SYM_RCD
    msp.add_blockref("SYM_RCD", insert=(x_coords[2], y_row1))
    add_label("SYM_RCD", x_coords[2], y_row1)
    
    # 4. SYM_LAMP
    msp.add_blockref("SYM_LAMP", insert=(x_coords[3], y_row1))
    add_label("SYM_LAMP", x_coords[3], y_row1)
    
    # --- Row 2: Utility symbols ---
    # 5. SYM_GROUND
    msp.add_blockref("SYM_GROUND", insert=(x_coords[0], y_row2))
    add_label("SYM_GROUND", x_coords[0], y_row2)
    
    # 6. SYM_JUNCTION
    msp.add_blockref("SYM_JUNCTION", insert=(x_coords[1], y_row2))
    add_label("SYM_JUNCTION", x_coords[1], y_row2)
    
    # 7. Dynamic Terminal Rows (2, 4, 6 terminals)
    msp.add_blockref("SYM_TERMINAL_ROW_2", insert=(x_coords[2], y_row2))
    add_label("SYM_TERM_ROW_2", x_coords[2], y_row2)
    
    msp.add_blockref("SYM_TERMINAL_ROW_4", insert=(x_coords[3], y_row2))
    add_label("SYM_TERM_ROW_4", x_coords[3], y_row2)
    
    msp.add_blockref("SYM_TERMINAL_ROW_6", insert=(x_coords[4], y_row2))
    add_label("SYM_TERM_ROW_6", x_coords[4], y_row2)
    
    # --- Row 3: Three-phase symbols (breakers/supply) ---
    # 8. SYM_SUPPLY_3PH
    msp.add_blockref("SYM_SUPPLY_3PH", insert=(x_coords[0], y_row3))
    add_label("SYM_SUPPLY_3PH", x_coords[0], y_row3)
    
    # 9. SYM_BREAKER_3PH
    msp.add_blockref("SYM_BREAKER_3PH", insert=(x_coords[1], y_row3))
    add_label("SYM_BREAKER_3PH", x_coords[1], y_row3)
    
    # 10. SYM_RCD_3PH
    msp.add_blockref("SYM_RCD_3PH", insert=(x_coords[2], y_row3))
    add_label("SYM_RCD_3PH", x_coords[2], y_row3)
    
    # --- Row 4: Three-phase symbols (busbar/mcb/motor) ---
    # 11. SYM_BUSBAR_3PH
    msp.add_blockref("SYM_BUSBAR_3PH", insert=(x_coords[0], y_row4))
    add_label("SYM_BUSBAR_3PH", x_coords[0], y_row4)
    
    # 12. SYM_MCB_3PH
    msp.add_blockref("SYM_MCB_3PH", insert=(x_coords[1], y_row4))
    add_label("SYM_MCB_3PH", x_coords[1], y_row4)
    
    # 13. SYM_MOTOR_3PH
    msp.add_blockref("SYM_MOTOR_3PH", insert=(x_coords[2], y_row4))
    add_label("SYM_MOTOR_3PH", x_coords[2], y_row4)
    
    # Save the drawing
    output_filename = os.path.join("renders", "test_symbols_rendering.dxf")
    os.makedirs("renders", exist_ok=True)
    doc.saveas(output_filename)
    print(f"Successfully generated '{output_filename}' grid model.")

if __name__ == "__main__":
    main()
