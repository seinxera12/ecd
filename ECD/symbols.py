"""
symbols.py
==========
Defines the DXF symbol block library for realistic electrical single-line
diagrams (Phase 2).

This module contains:
  1. init_symbols_layer() – ensures the 'SYMBOLS' layer is created.
  2. build_breaker_block() – registers the SYM_BREAKER block.
  3. build_mcb_block() – registers the SYM_MCB block (smaller breaker).
  4. build_rcd_block() – registers the SYM_RCD block (breaker with differential ring).
  5. build_lamp_block() – registers the SYM_LAMP block (circle with X).
  6. build_ground_block() – registers the SYM_GROUND block (earth symbol).
  7. get_or_create_terminal_row() – registers and returns a parametric SYM_TERMINAL_ROW_N block.
  8. build_junction_block() – registers the SYM_JUNCTION block (filled node dot).
  9. build_generic_block() – registers the SYM_GENERIC block (rectangle fallback).
 10. build_supply_3ph_block() – registers the SYM_SUPPLY_3PH block (three-phase source).
 11. build_breaker_3ph_block() – registers the SYM_BREAKER_3PH block (3-pole breaker).
 12. build_rcd_3ph_block() – registers the SYM_RCD_3PH block (3-pole RCD + CT ring).
 13. build_busbar_3ph_block() – registers the SYM_BUSBAR_3PH block (3-phase busbar).
 14. build_mcb_3ph_block() – registers the SYM_MCB_3PH block (3-pole MCB).
 15. build_motor_3ph_block() – registers the SYM_MOTOR_3PH block (motor circle "M3").
 16. register_all_symbols() – utility to register all standard blocks in a document.
"""

from __future__ import annotations
import ezdxf
from ezdxf.enums import TextEntityAlignment

def init_symbols_layer(doc) -> None:
    """Ensure the standard 'SYMBOLS' layer exists in the document."""
    if "SYMBOLS" not in doc.layers:
        doc.layers.add(name="SYMBOLS", color=7)  # White/Black color index


def build_breaker_block(doc):
    """SYM_BREAKER: IEC-style main circuit breaker switch-gap.
    
    Vertical height: Spans from y = -10.0 to y = 10.0 (matching pins).
    """
    if "SYM_BREAKER" in doc.blocks:
        return doc.blocks.get("SYM_BREAKER")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_BREAKER")
    
    gap = 3.0
    # Bottom lead to y = -10.0
    blk.add_line((0.0, -10.0), (0.0, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
    # Top lead to y = 10.0
    blk.add_line((0.0, gap / 2), (0.0, 10.0), dxfattribs={"layer": "SYMBOLS"})
    # Diagonal switch stroke
    blk.add_line((-1.5, -gap / 2), (1.5, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_mcb_block(doc):
    """SYM_MCB: Smaller circuit breaker switch-gap (for branch outgoing circuit breakers).
    
    Vertical height: Spans from y = -10.0 to y = 10.0 (matching pins).
    """
    if "SYM_MCB" in doc.blocks:
        return doc.blocks.get("SYM_MCB")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_MCB")
    
    gap = 2.0
    # Bottom lead to y = -10.0
    blk.add_line((0.0, -10.0), (0.0, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
    # Top lead to y = 10.0
    blk.add_line((0.0, gap / 2), (0.0, 10.0), dxfattribs={"layer": "SYMBOLS"})
    # Diagonal switch stroke
    blk.add_line((-1.0, -gap / 2), (1.0, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_rcd_block(doc):
    """SYM_RCD: RCD switch-gap (main breaker geometry + differential CT sensor ring).
    
    Vertical height: Spans from y = -10.0 to y = 10.0 (matching pins).
    CT Ring: Circle of radius 2.5 centered at (0,0).
    """
    if "SYM_RCD" in doc.blocks:
        return doc.blocks.get("SYM_RCD")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_RCD")
    
    gap = 3.0
    # Bottom lead to y = -10.0
    blk.add_line((0.0, -10.0), (0.0, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
    # Top lead to y = 10.0
    blk.add_line((0.0, gap / 2), (0.0, 10.0), dxfattribs={"layer": "SYMBOLS"})
    # Diagonal switch stroke
    blk.add_line((-1.5, -gap / 2), (1.5, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    # CT sensor ring (zero-sequence current transformer indicator)
    blk.add_circle(center=(0.0, 0.0), radius=2.5, dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_lamp_block(doc):
    """SYM_LAMP: IEC-style lamp/load symbol (circle with X inside + short vertical stub).
    
    Height: Circle radius = 4.0, lead stub goes up to y = 7.0.
    """
    if "SYM_LAMP" in doc.blocks:
        return doc.blocks.get("SYM_LAMP")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_LAMP")
    
    radius = 4.0
    # Main outer circle
    blk.add_circle(center=(0.0, 0.0), radius=radius, dxfattribs={"layer": "SYMBOLS"})
    # Internal X cross
    offset = radius * 0.707  # sqrt(2)/2 approx
    blk.add_line((-offset, -offset), (offset, offset), dxfattribs={"layer": "SYMBOLS"})
    blk.add_line((-offset, offset), (offset, -offset), dxfattribs={"layer": "SYMBOLS"})
    # Top lead stub (L connection point at y = 7.0)
    blk.add_line((0.0, radius), (0.0, radius + 3.0), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_ground_block(doc):
    """SYM_GROUND: Standard earth/ground symbol (top lead + 3 shrinking horizontal bars).
    
    Spans from y = 3.0 (connection point) to y = -4.0 (tip of bottom bar).
    """
    if "SYM_GROUND" in doc.blocks:
        return doc.blocks.get("SYM_GROUND")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_GROUND")
    
    # Top lead down to origin (0,0)
    blk.add_line((0.0, 3.0), (0.0, 0.0), dxfattribs={"layer": "SYMBOLS"})
    # Three shrinking horizontal bars
    for width, y in [(6.0, 0.0), (4.0, -2.0), (2.0, -4.0)]:
        blk.add_line((-width / 2, y), (width / 2, y), dxfattribs={"layer": "SYMBOLS"})
        
    return blk


def get_or_create_terminal_row(doc, n: int, spacing: float = 6.0) -> str:
    """SYM_TERMINAL_ROW_N: Parametric terminal row for neutral/earth bus bars.
    
    Creates a unique block 'SYM_TERMINAL_ROW_<n>' with a rectangle enclosing
    n evenly-spaced circular terminal points. Returns the name of the block.
    """
    name = f"SYM_TERMINAL_ROW_{n}"
    if name in doc.blocks:
        return name
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name=name)
    
    total_w = spacing * (n - 1) + 6.0
    half = total_w / 2
    # Outer enclosing border box
    blk.add_lwpolyline(
        [(-half, -3.0), (half, -3.0), (half, 3.0), (-half, 3.0)],
        close=True,
        dxfattribs={"layer": "SYMBOLS"}
    )
    # n evenly spaced terminal circles
    start_x = -spacing * (n - 1) / 2
    for i in range(n):
        x = start_x + i * spacing
        blk.add_circle(center=(x, 0.0), radius=1.0, dxfattribs={"layer": "SYMBOLS"})
        
    return name


def build_junction_block(doc):
    """SYM_JUNCTION: Solid filled circle representing an electrical connection node."""
    if "SYM_JUNCTION" in doc.blocks:
        return doc.blocks.get("SYM_JUNCTION")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_JUNCTION")
    
    r = 0.6
    # Add solid fill hatch
    hatch = blk.add_hatch(color=7, dxfattribs={"layer": "SYMBOLS"})
    hatch.paths.add_polyline_path(
        [(r, 0.0), (0.0, r), (-r, 0.0), (0.0, -r)],
        is_closed=True
    )
    # Circle border
    blk.add_circle(center=(0.0, 0.0), radius=r, dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_generic_block(doc):
    """SYM_GENERIC: Fallback symbol for unknown component types.
    
    A simple rectangle (box) placeholder, spans from y = -5.0 to y = 5.0.
    """
    if "SYM_GENERIC" in doc.blocks:
        return doc.blocks.get("SYM_GENERIC")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_GENERIC")
    
    half_w, half_h = 6.0, 5.0
    blk.add_lwpolyline(
        [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)],
        close=True,
        dxfattribs={"layer": "SYMBOLS"}
    )
    # Short vertical leads top and bottom for connection
    blk.add_line((0.0, half_h), (0.0, half_h + 3.0), dxfattribs={"layer": "SYMBOLS"})
    blk.add_line((0.0, -half_h), (0.0, -half_h - 3.0), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_supply_3ph_block(doc):
    """SYM_SUPPLY_3PH: Three-phase incoming source marker (star/wye junction).
    
    Three vertical stubs descend from above and converge at a horizontal
    connecting bar (└───┴───┘ shape) at y = -10.0, with "L1", "L2", "L3"
    labels placed at the top (y = 2.0).
    """
    if "SYM_SUPPLY_3PH" in doc.blocks:
        return doc.blocks.get("SYM_SUPPLY_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_SUPPLY_3PH")
    
    bar_y = -10.0  # horizontal connecting bar at the bottom
    
    # Three vertical incoming stubs from top down to bar
    for x in (-5.0, 0.0, 5.0):
        blk.add_line((x, 0.0), (x, bar_y), dxfattribs={"layer": "SYMBOLS"})
    
    # Horizontal connecting bar (the └───┴───┘ junction)
    blk.add_line((-5.0, bar_y), (5.0, bar_y), dxfattribs={"layer": "SYMBOLS"})
    
    # Add L1, L2, L3 labels above the stubs
    phases = [("L1", -5.0), ("L2", 0.0), ("L3", 5.0)]
    for name, x in phases:
        blk.add_text(
            name,
            dxfattribs={"layer": "SYMBOLS", "height": 2.0}
        ).set_placement((x, 2.0), align=TextEntityAlignment.MIDDLE_CENTER)
    
    return blk


def build_breaker_3ph_block(doc):
    """SYM_BREAKER_3PH: Three-pole main circuit breaker (IEC single-line style).
    
    Three parallel switch-gap strokes at x = -5, 0, +5.
    Each pole spans y = -10 to y = +10 (matching pin offsets).
    A horizontal tie-bar at y = 5 indicates mechanical ganging.
    """
    if "SYM_BREAKER_3PH" in doc.blocks:
        return doc.blocks.get("SYM_BREAKER_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_BREAKER_3PH")
    
    gap = 3.0
    for x in (-5.0, 0.0, 5.0):
        # Bottom lead
        blk.add_line((x, -10.0), (x, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
        # Top lead
        blk.add_line((x, gap / 2), (x, 10.0), dxfattribs={"layer": "SYMBOLS"})
        # Diagonal switch stroke
        blk.add_line((x - 1.5, -gap / 2), (x + 1.5, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    
    # Horizontal mechanical tie-bar across all three poles
    blk.add_line((-5.0, 5.0), (5.0, 5.0), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_rcd_3ph_block(doc):
    """SYM_RCD_3PH: Three-pole RCD (breaker + differential CT sensor ring).
    
    Same three-pole switch-gap geometry as SYM_BREAKER_3PH, plus a CT sensor
    ring (circle r=7.0) centered at (0, 0) enclosing all three poles.
    The radius is sized to geometrically enclose the pole strokes at x = ±5,
    matching the proportional margin the single-phase SYM_RCD ring has.
    """
    if "SYM_RCD_3PH" in doc.blocks:
        return doc.blocks.get("SYM_RCD_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_RCD_3PH")
    
    gap = 3.0
    for x in (-5.0, 0.0, 5.0):
        # Bottom lead
        blk.add_line((x, -10.0), (x, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
        # Top lead
        blk.add_line((x, gap / 2), (x, 10.0), dxfattribs={"layer": "SYMBOLS"})
        # Diagonal switch stroke
        blk.add_line((x - 1.5, -gap / 2), (x + 1.5, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    
    # Horizontal mechanical tie-bar across all three poles
    blk.add_line((-5.0, 5.0), (5.0, 5.0), dxfattribs={"layer": "SYMBOLS"})
    
    # CT sensor ring enclosing all three poles (r=7.0 to cover x=±5 with margin)
    blk.add_circle(center=(0.0, 0.0), radius=7.0, dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_busbar_3ph_block(doc):
    """SYM_BUSBAR_3PH: Three-phase busbar visual block.
    
    Three long horizontal parallel lines representing the L1, L2, L3
    copper bus bars, spaced vertically at y = +3, 0, -3.
    Each line spans from x = -15 to x = +15.
    """
    if "SYM_BUSBAR_3PH" in doc.blocks:
        return doc.blocks.get("SYM_BUSBAR_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_BUSBAR_3PH")
    
    bar_half_len = 15.0
    spacing = 3.0  # vertical gap between bars
    # L1 (top), L2 (center), L3 (bottom)
    for y in (spacing, 0.0, -spacing):
        blk.add_line((-bar_half_len, y), (bar_half_len, y),
                     dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_mcb_3ph_block(doc):
    """SYM_MCB_3PH: Three-pole branch MCB (smaller gap, for outgoing circuit breakers).
    
    Three parallel switch-gap strokes at x = -5, 0, +5 with gap = 2.0.
    Each pole spans y = -10 to y = +10 (matching pin offsets).
    A horizontal tie-bar at y = 4 indicates mechanical ganging.
    """
    if "SYM_MCB_3PH" in doc.blocks:
        return doc.blocks.get("SYM_MCB_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_MCB_3PH")
    
    gap = 2.0
    for x in (-5.0, 0.0, 5.0):
        # Bottom lead
        blk.add_line((x, -10.0), (x, -gap / 2), dxfattribs={"layer": "SYMBOLS"})
        # Top lead
        blk.add_line((x, gap / 2), (x, 10.0), dxfattribs={"layer": "SYMBOLS"})
        # Diagonal switch stroke
        blk.add_line((x - 1.0, -gap / 2), (x + 1.0, gap / 2), dxfattribs={"layer": "SYMBOLS"})
    
    # Horizontal mechanical tie-bar across all three poles
    blk.add_line((-5.0, 4.0), (5.0, 4.0), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def build_motor_3ph_block(doc):
    """SYM_MOTOR_3PH: Three-phase motor load symbol.
    
    Circle of radius 5.0 at (0, 0) with "M3" text label centered inside.
    Three top lead stubs from y = 5 to y = 7 at x = -5, 0, +5 (L1, L2, L3 entry).
    Earth stub from (0, -5) to (0, -7) matching E_in pin at y = -7.
    """
    if "SYM_MOTOR_3PH" in doc.blocks:
        return doc.blocks.get("SYM_MOTOR_3PH")
        
    init_symbols_layer(doc)
    blk = doc.blocks.new(name="SYM_MOTOR_3PH")
    
    radius = 5.0
    # Motor circle
    blk.add_circle(center=(0.0, 0.0), radius=radius, dxfattribs={"layer": "SYMBOLS"})
    
    # "M3" label centered in the circle
    blk.add_text(
        "M3",
        dxfattribs={"layer": "SYMBOLS", "height": 3.5}
    ).set_placement((0.0, 0.0), align=TextEntityAlignment.MIDDLE_CENTER)
    
    # Three top lead stubs (L1, L2, L3 connection points at y = 7.0)
    for x in (-5.0, 0.0, 5.0):
        blk.add_line((x, radius), (x, 7.0), dxfattribs={"layer": "SYMBOLS"})
    
    # Earth stub at bottom (E_in at y = -7.0)
    blk.add_line((0.0, -radius), (0.0, -7.0), dxfattribs={"layer": "SYMBOLS"})
    
    return blk


def register_all_symbols(doc) -> None:
    """Register all standard symbols inside the given DXF document."""
    build_breaker_block(doc)
    build_mcb_block(doc)
    build_rcd_block(doc)
    build_lamp_block(doc)
    build_ground_block(doc)
    build_junction_block(doc)
    build_generic_block(doc)
    # Three-phase symbols
    build_supply_3ph_block(doc)
    build_breaker_3ph_block(doc)
    build_rcd_3ph_block(doc)
    build_busbar_3ph_block(doc)
    build_mcb_3ph_block(doc)
    build_motor_3ph_block(doc)
