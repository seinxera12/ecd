"""
pin_model.py
============
Defines the pin and net data model for realistic electrical single-line
diagram generation (Phase 1).

This module contains:
  1. PinDef dataclass – defines pin names, types (L/N/E), and relative coordinate offsets.
  2. COMPONENT_PINS – mapping of component types to lists of PinDef.
  3. PIN_WIRING_RULES – mapping of component-type pairs to their pin-to-pin wiring connections.
  4. get_pin_position() – resolver for absolute coordinates of a pin.
  5. compute_component_positions() – layout engine to calculate coordinates for all components.
  6. generate_netlist() – builds the complete netlist with all L/N/E wires.
  7. validate_netlist() – checks for dangling pins, load connectivity, and rail continuity.
"""

from __future__ import annotations
from dataclasses import dataclass
import re

# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PinDef:
    """Defines a single electrical connection pin on a component block."""
    name: str        # e.g., "L_in", "L_out", "N_in", "N_out", "E_in", "E_out"
    wire_type: str   # "L" (Phase/Live), "N" (Neutral), "E" (Earth/PE)
    x_offset: float  # horizontal offset in mm relative to the component center (0,0)
    y_offset: float  # vertical offset in mm relative to the component center (0,0)


# ── Component Pins Definitions ───────────────────────────────────────────────
# Dimensions are based on BOX_W = 60 and BOX_H = 20 for standard component boxes,
# and radii / leads from symbol_sample.py and mini_panel_diagram.py:
#   - SYM_BREAKER: top lead at y = 5.5, bottom lead at y = -5.5
#   - SYM_LAMP: top L_in stub at y = 7.0, Neutral at x = -4.0, Earth at y = -4.0
#   - SYM_TERMINAL_ROW: top N_in at y = 3.0, bottom N_out at y = -3.0
#
# Neutral and Earth trunk rails run at x = -45.0 and x = -60.0 relative to the L spine.

def determine_phase_mode_detailed(voltage: str | float | None, phase_hint: str | None) -> tuple[str, str | None, str | None]:
    """Determine phase mode ('single' or 'three') along with detailed reasoning metadata.
    
    Returns
    -------
    (phase_mode, reason_code, reason_message)
        reason_code: 'OVERRIDE', 'INFERRED', or None if unambiguous.
    """
    has_hint = bool(phase_hint and str(phase_hint).strip())
    hint_mode = None
    if has_hint:
        hint_lower = str(phase_hint).lower()
        if "three" in hint_lower or "3" in hint_lower:
            hint_mode = "three"
        elif "single" in hint_lower or "1" in hint_lower:
            hint_mode = "single"

    # Parse numeric voltage
    v_val = None
    v_str = str(voltage) if voltage is not None else ""
    if isinstance(voltage, (int, float)):
        v_val = float(voltage)
    elif voltage is not None:
        match = re.search(r"(\d+(?:\.\d+)?)", v_str)
        if match:
            v_val = float(match.group(1))

    v_implied_mode = "three" if (v_val is not None and v_val >= 400.0) else "single" if (v_val is not None and v_val <= 250.0) else None

    # Case 1: Explicit hint overrides implied voltage
    if hint_mode and v_implied_mode and hint_mode != v_implied_mode:
        v_desc = f"{int(v_val)}V" if (v_val and v_val.is_integer()) else f"{voltage}"
        msg = f"Voltage {v_desc} is typically {v_implied_mode}-phase, but '{phase_hint}' was explicitly requested — diagram generated as {hint_mode}-phase."
        return (hint_mode, "OVERRIDE", msg)

    if hint_mode:
        return (hint_mode, None, None)

    # Case 2: No phase hint given, phase mode inferred from voltage
    if v_val is not None:
        inferred_mode = "three" if v_val >= 400.0 else "single"
        if v_val >= 400.0:
            v_desc = f"{int(v_val)}V" if v_val.is_integer() else f"{voltage}"
            msg = f"No phase specified — inferred three-phase from stated voltage {v_desc}."
            return (inferred_mode, "INFERRED", msg)
        return (inferred_mode, None, None)

    return ("single", None, None)


def determine_phase_mode(voltage: str | float | None, phase_hint: str | None) -> str:
    """Determine phase mode ('single' or 'three') deterministically."""
    mode, _, _ = determine_phase_mode_detailed(voltage, phase_hint)
    return mode



COMPONENT_PINS: dict[str, dict[str, list[PinDef]]] = {
    "supply": {
        "single": [
            PinDef("L_out", "L", 0.0, -10.0),
            PinDef("N_out", "N", -45.0, -10.0),
            PinDef("E_out", "E", -60.0, -10.0),
        ],
        "three": [
            PinDef("L1_out", "L1", -5.0, -10.0),
            PinDef("L2_out", "L2", 0.0, -10.0),
            PinDef("L3_out", "L3", 5.0, -10.0),
            PinDef("N_out", "N", -45.0, -10.0),
            PinDef("E_out", "E", -60.0, -10.0),
        ]
    },
    "maincb": {
        "single": [
            PinDef("L_in", "L", 0.0, 10.0),
            PinDef("L_out", "L", 0.0, -10.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 10.0),
            PinDef("L2_in", "L2", 0.0, 10.0),
            PinDef("L3_in", "L3", 5.0, 10.0),
            PinDef("L1_out", "L1", -5.0, -10.0),
            PinDef("L2_out", "L2", 0.0, -10.0),
            PinDef("L3_out", "L3", 5.0, -10.0),
        ]
    },
    "rcd": {
        "single": [
            PinDef("L_in", "L", 0.0, 10.0),
            PinDef("L_out", "L", 0.0, -10.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 10.0),
            PinDef("L2_in", "L2", 0.0, 10.0),
            PinDef("L3_in", "L3", 5.0, 10.0),
            PinDef("L1_out", "L1", -5.0, -10.0),
            PinDef("L2_out", "L2", 0.0, -10.0),
            PinDef("L3_out", "L3", 5.0, -10.0),
        ]
    },
    "rcbo": {
        "single": [
            PinDef("L_in", "L", 0.0, 10.0),
            PinDef("L_out", "L", 0.0, -10.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 10.0),
            PinDef("L2_in", "L2", 0.0, 10.0),
            PinDef("L3_in", "L3", 5.0, 10.0),
            PinDef("L1_out", "L1", -5.0, -10.0),
            PinDef("L2_out", "L2", 0.0, -10.0),
            PinDef("L3_out", "L3", 5.0, -10.0),
        ]
    },
    "bus": {
        "single": [
            PinDef("L_in", "L", 0.0, 0.0),
            PinDef("L_out", "L", 0.0, 0.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 3.0),
            PinDef("L2_in", "L2", 0.0, 0.0),
            PinDef("L3_in", "L3", 5.0, -3.0),
            PinDef("L1_out", "L1", -5.0, 3.0),
            PinDef("L2_out", "L2", 0.0, 0.0),
            PinDef("L3_out", "L3", 5.0, -3.0),
        ]
    },
    "nbar": {
        "single": [
            PinDef("N_in", "N", 0.0, 3.0),
            PinDef("N_out", "N", 0.0, -3.0),
        ],
        "three": [
            PinDef("N_in", "N", 0.0, 3.0),
            PinDef("N_out", "N", 0.0, -3.0),
        ]
    },
    "ebar": {
        "single": [
            PinDef("E_in", "E", 0.0, 3.0),
            PinDef("E_out", "E", 0.0, -3.0),
        ],
        "three": [
            PinDef("E_in", "E", 0.0, 3.0),
            PinDef("E_out", "E", 0.0, -3.0),
        ]
    },
    "outcb": {
        "single": [
            PinDef("L_in", "L", 0.0, 10.0),
            PinDef("L_out", "L", 0.0, -10.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 10.0),
            PinDef("L2_in", "L2", 0.0, 10.0),
            PinDef("L3_in", "L3", 5.0, 10.0),
            PinDef("L1_out", "L1", -5.0, -10.0),
            PinDef("L2_out", "L2", 0.0, -10.0),
            PinDef("L3_out", "L3", 5.0, -10.0),
        ]
    },
    "loads": {
        "single": [
            PinDef("L_in", "L", 0.0, 7.0),
            PinDef("N_in", "N", -4.0, 0.0),
            PinDef("E_in", "E", 0.0, -4.0),
        ],
        "three": [
            PinDef("L1_in", "L1", -5.0, 7.0),
            PinDef("L2_in", "L2", 0.0, 7.0),
            PinDef("L3_in", "L3", 5.0, 7.0),
            PinDef("N_in", "N", -5.0, 0.0),
            PinDef("E_in", "E", 0.0, -7.0),
        ]
    }
}


# ── Logical Wiring Rules ─────────────────────────────────────────────────────
# Maps (src_type, dst_type) -> list of (src_pin, dst_pin) connections

PIN_WIRING_RULES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("supply", "maincb"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("supply", "rcd"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("supply", "rcbo"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("supply", "bus"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("supply", "nbar"): [("N_out", "N_in")],
    ("supply", "ebar"): [("E_out", "E_in")],
    
    ("maincb", "rcd"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("maincb", "rcbo"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("maincb", "bus"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("maincb", "loads"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    
    ("rcd", "bus"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("rcd", "outcb"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("rcd", "loads"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],

    ("rcbo", "bus"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("rcbo", "outcb"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("rcbo", "loads"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    
    ("bus", "outcb"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    ("bus", "loads"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    
    ("outcb", "loads"): [("L_out", "L_in"), ("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")],
    
    ("nbar", "loads"): [("N_out", "N_in")],
    ("ebar", "loads"): [("E_out", "E_in")],
}


# ── Resolvers & Helper Functions ─────────────────────────────────────────────

def get_base_type(component_id: str) -> str:
    """Normalize dynamic IDs (e.g. 'outcb_1' -> 'outcb', 'load_1' -> 'loads')."""
    cid = component_id.lower()
    if re.match(r'^(supply|grid|mains|source|generator|gen|solar|pv)(?:_|\d|\b|$)', cid):
        return "supply"
    if re.match(r'^(outcb|outgoingcb|outcr|outgoingcr|mcb|cb)(?:_|\d|\b|$)', cid):
        return "outcb"
    if re.match(r'^(loads?|socket|outlet|lamp|motor|heater|charger|lighting|pump|fan|ac|aircon|ev|cooker|oven|hob|appliance|device)(?:_|\d|\b|$)', cid):
        return "loads"
    return cid


def get_pin_position(component_id: str, pin_name: str, comp_pos: tuple[float, float], phase_mode: str = "single") -> tuple[float, float]:
    """Get the absolute (x, y) coordinate of a component's pin.
    
    Parameters
    ----------
    component_id : str
        The unique ID of the component (e.g., 'maincb', 'outcb_1').
    pin_name : str
        The name of the pin (e.g., 'L1_in', 'L_out').
    comp_pos : tuple[float, float]
        The absolute insertion coordinate (x, y) of the component.
    phase_mode : str
        The phase mode of the component ('single' or 'three').
    """
    base_type = get_base_type(component_id)
    pins_by_mode = COMPONENT_PINS.get(base_type)
    if pins_by_mode is None:
        if phase_mode == "three":
            pins = [
                PinDef("L1_in", "L1", -5.0, 10.0),
                PinDef("L2_in", "L2", 0.0, 10.0),
                PinDef("L3_in", "L3", 5.0, 10.0),
                PinDef("L1_out", "L1", -5.0, -10.0),
                PinDef("L2_out", "L2", 0.0, -10.0),
                PinDef("L3_out", "L3", 5.0, -10.0),
            ]
        else:
            pins = [
                PinDef("L_in", "L", 0.0, 10.0),
                PinDef("L_out", "L", 0.0, -10.0),
            ]
    else:
        pins = pins_by_mode.get(phase_mode, pins_by_mode.get("single"))
        
    for pin in pins:
        if pin.name == pin_name:
            return (comp_pos[0] + pin.x_offset, comp_pos[1] + pin.y_offset)
    
    raise ValueError(f"Pin '{pin_name}' not found for component type '{base_type}' in phase mode '{phase_mode}'")


# ── Component Placement/Layout ────────────────────────────────────────────────

def compute_component_positions(parsed_data: dict, phase_mode: str = None, start_y: float = None) -> dict[str, tuple[float, float]]:
    """Determine coordinates for all components in parsed_data.
    
    Layout strategy (matches Phase 3 schematic look):
      - supply, maincb, rcd/rcbo, and bus are vertically stacked at x = 0.
      - outcb_N and their corresponding loads are spread horizontally under the busbar.
      - nbar (Neutral Bar) is at x = -45.
      - ebar (Earth Bar) is at x = -60.
    """
    if phase_mode is None:
        voltage = parsed_data.get("voltage")
        phase_hint = parsed_data.get("phase_hint") or parsed_data.get("flags", {}).get("phase_hint")
        phase_mode = determine_phase_mode(voltage, phase_hint)

    components = parsed_data.get("components", [])
    comp_map = {cid.lower(): lbl for cid, lbl in components}
    
    # Identify outgoing branch breakers
    outcb_ids = sorted(
        [cid for cid in comp_map if get_base_type(cid) == "outcb" and cid != "outcb"],
        key=lambda s: int(re.search(r'\d+', s).group()) if re.search(r'\d+', s) else 0,
    )
    if not outcb_ids and "outcb" in comp_map:
        outcb_ids = ["outcb"]
        
    main_column = []
    known_types = {"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads"}
    for cid, _ in components:
        cid_lower = cid.lower()
        bt = get_base_type(cid_lower)
        if cid_lower in ["supply", "maincb", "rcd", "rcbo", "bus"] or (
            cid_lower not in known_types 
            and bt != "outcb" 
            and bt != "loads"
        ):
            if cid_lower not in main_column:
                main_column.append(cid_lower)
            
    # Vertical coordinates parameters
    H_STEP = 38.0
    if start_y is None:
        start_y = 100.0
    
    positions: dict[str, tuple[float, float]] = {}
    
    # 1. Place the main vertical column (L spine)
    supply_cids = [cid.lower() for cid, _ in components if get_base_type(cid.lower()) == "supply"]
    if len(supply_cids) > 1:
        # Dual supplies placed side-by-side at x = -35.0 and x = +35.0 above ATS
        positions[supply_cids[0]] = (-35.0, start_y)
        positions[supply_cids[1]] = (35.0, start_y)
        main_column = [c for c in main_column if c not in supply_cids]
        for i, cid in enumerate(main_column):
            positions[cid] = (0.0, start_y - (i + 1) * H_STEP)
    else:
        for i, cid in enumerate(main_column):
            positions[cid] = (0.0, start_y - i * H_STEP)
        
    # Get the busbar Y coordinate (or fallback if no busbar)
    bus_y = positions.get("bus", (0.0, start_y - len(main_column) * H_STEP))[1]
    
    # 2. Place outgoing breakers and loads horizontally
    spacing = 45.0 if phase_mode == "three" else 30.0
    load_ids = [cid.lower() for cid, _ in components if get_base_type(cid.lower()) == "loads"]
    
    if outcb_ids:
        n_cb = len(outcb_ids)
        start_x = -(spacing * (n_cb - 1)) / 2
        
        for i, cb_id in enumerate(outcb_ids):
            cx = start_x + i * spacing
            # Breakers are placed one step below the busbar
            positions[cb_id] = (cx, bus_y - H_STEP)
            
            # Loads are placed two steps below the busbar, matching their breaker
            match = re.search(r'\d+', cb_id)
            suffix = match.group() if match else ""
            load_id = cb_id.replace("outcb_", "load_")
            if load_id not in comp_map:
                loads_variant = cb_id.replace("outcb_", "loads_")
                if loads_variant in comp_map:
                    load_id = loads_variant
                else:
                    matching_load = next((l for l in load_ids if l.endswith(f"_{suffix}") or l.endswith(suffix)), None)
                    if matching_load:
                        load_id = matching_load
            positions[load_id] = (cx, bus_y - 2 * H_STEP)
    else:
        # No breakers, but could have multiple load-type components
        if load_ids:
            n_loads = len(load_ids)
            start_x = -(spacing * (n_loads - 1)) / 2
            for i, load_id in enumerate(load_ids):
                cx = start_x + i * spacing
                # Loads are placed one step below the busbar since there are no breakers
                positions[load_id] = (cx, bus_y - H_STEP)
            
    # 3. Place side branch bars (nbar and ebar)
    # Single-phase: at fixed x = -45.0 / -60.0 if <= 3 circuits (to preserve regression baseline),
    # otherwise dynamic to prevent overlaps.
    # Three-phase: always dynamically positioned left of the leftmost breaker/load.
    n_horizontal = len(outcb_ids) if outcb_ids else len(load_ids)
    if phase_mode == "single" and n_horizontal <= 3:
        nbar_x = -45.0
        ebar_x = -60.0
    elif n_horizontal > 0:
        leftmost_x = -(spacing * (n_horizontal - 1)) / 2
        term_half_w = (6.0 * (n_horizontal + 1)) / 2.0
        nbar_x = leftmost_x - term_half_w - 20.0
        ebar_x = nbar_x - 15.0
    else:
        nbar_x = -45.0
        ebar_x = -60.0
 
    if "nbar" in comp_map:
        positions["nbar"] = (nbar_x, bus_y)  # aligned with busbar vertically
    if "ebar" in comp_map:
        positions["ebar"] = (ebar_x, bus_y - H_STEP / 2)  # slightly lower than busbar
        
    # 4. Fallback for any other component not placed yet (e.g. unclassified/orphaned custom components)
    custom_x = 45.0
    if n_horizontal > 0:
        rightmost_x = (spacing * (n_horizontal - 1)) / 2
        custom_x = max(custom_x, rightmost_x + 30.0)
    
    unplaced_count = 0
    for cid, _ in components:
        cid_lower = cid.lower()
        if cid_lower not in positions and get_base_type(cid_lower) != "loads" and get_base_type(cid_lower) != "outcb":
            positions[cid_lower] = (custom_x, start_y - unplaced_count * H_STEP)
            unplaced_count += 1
            
    # Apply manual component_position_overrides if present (manual overrides take precedence)
    comp_overrides = parsed_data.get("component_position_overrides", {})
    if comp_overrides:
        for cid, ov in comp_overrides.items():
            if isinstance(ov, dict) and "position" in ov:
                pos = ov["position"]
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    positions[str(cid).lower()] = (float(pos[0]), float(pos[1]))

    return positions


# ── Netlist Generation ────────────────────────────────────────────────────────

def generate_netlist(parsed_data: dict, component_positions: dict[str, tuple[float, float]], phase_mode: str = None) -> dict:
    """Resolve components and their electrical wire connections into a netlist.
    
    Parameters
    ----------
    parsed_data : dict
        Contains 'components', 'connections' (from ensure_connections), and 'flags'.
    component_positions : dict[str, tuple[float, float]]
        Computed coordinates for each component ID.
    phase_mode : str
        The phase mode of the diagram ('single' or 'three').
    """
    try:
        from ECD.dxf_generator import ensure_connections
    except ImportError:
        from dxf_generator import ensure_connections
        
    if phase_mode is None:
        voltage = parsed_data.get("voltage")
        phase_hint = parsed_data.get("phase_hint") or parsed_data.get("flags", {}).get("phase_hint")
        phase_mode = determine_phase_mode(voltage, phase_hint)
    
    components = parsed_data.get("components", [])
    flags = parsed_data.get("flags", {})
    
    # Normalize list of components
    comp_map = {cid.lower(): lbl for cid, lbl in components}
    show_neutral = flags.get("show_neutral", "nbar" in comp_map)
    show_earth = flags.get("show_earth", "ebar" in comp_map)
    # If the component is present, it must be wired regardless of the flag.
    # The flag controls whether the component is *included*, not whether it's *connected*.
    wire_neutral = show_neutral or "nbar" in comp_map
    wire_earth = show_earth or "ebar" in comp_map
    
    outcb_ids = sorted(
        [cid for cid in comp_map if get_base_type(cid) == "outcb" and cid != "outcb"],
        key=lambda s: int(re.search(r'\d+', s).group()) if re.search(r'\d+', s) else 0,
    )
    if not outcb_ids and "outcb" in comp_map:
        outcb_ids = ["outcb"]
        
    # Build netlist components metadata
    netlist_components = {}
    for cid, label in components:
        cid_lower = cid.lower()
        
        # If loads is dynamic, expand it in the netlist to match breakers
        if cid_lower == "loads" and outcb_ids:
            for cb_id in outcb_ids:
                load_id = cb_id.replace("outcb_", "load_")
                if load_id in component_positions:
                    pos = component_positions[load_id]
                    base_type = "loads"
                    pins_info = []
                    pins = COMPONENT_PINS[base_type].get(phase_mode, COMPONENT_PINS[base_type]["single"])
                    for pin in pins:
                        pins_info.append({
                            "name": pin.name,
                            "wire_type": pin.wire_type,
                            "position": [pos[0] + pin.x_offset, pos[1] + pin.y_offset]
                        })
                    netlist_components[load_id] = {
                        "id": load_id,
                        "type": base_type,
                        "label": f"Load for {cb_id}",
                        "position": list(pos),
                        "position_source": "computed",
                        "pins": pins_info
                    }
            continue
            
        if cid_lower in component_positions:
            pos = component_positions[cid_lower]
            base_type = get_base_type(cid_lower)
            pins_info = []
            pins_by_mode = COMPONENT_PINS.get(base_type)
            if pins_by_mode is None:
                pins = [
                    PinDef("L_in", "L", 0.0, 5.0),
                    PinDef("L_out", "L", 0.0, -5.0),
                ]
            else:
                pins = pins_by_mode.get(phase_mode, pins_by_mode.get("single"))
            for pin in pins:
                pins_info.append({
                    "name": pin.name,
                    "wire_type": pin.wire_type,
                    "position": [pos[0] + pin.x_offset, pos[1] + pin.y_offset]
                })
            netlist_components[cid_lower] = {
                "id": cid_lower,
                "type": base_type,
                "label": label,
                "position": list(pos),
                "position_source": "computed",
                "pins": pins_info
            }
            
    # Always ensure dynamic loads are added to netlist if breakers exist,
    # even if "loads" was not explicitly listed in the input components
    if outcb_ids:
        for cb_id in outcb_ids:
            load_id = cb_id.replace("outcb_", "load_")
            if load_id in component_positions and load_id not in netlist_components:
                pos = component_positions[load_id]
                base_type = "loads"
                pins_info = []
                pins = COMPONENT_PINS[base_type].get(phase_mode, COMPONENT_PINS[base_type]["single"])
                for pin in pins:
                    pins_info.append({
                        "name": pin.name,
                        "wire_type": pin.wire_type,
                        "position": [pos[0] + pin.x_offset, pos[1] + pin.y_offset]
                    })
                netlist_components[load_id] = {
                    "id": load_id,
                    "type": base_type,
                    "label": f"Load for {cb_id}",
                    "position": list(pos),
                    "position_source": "computed",
                    "pins": pins_info
                }
            
    # Resolve connections
    connections = ensure_connections(parsed_data)
    # Ensure outcb -> loads connections are backfilled if missing in LLM response
    if outcb_ids:
        connections_list = list(connections)
        for outcb_id in outcb_ids:
            if not any(src.lower() == outcb_id.lower() and (dst.lower() == "loads" or get_base_type(dst) == "loads") for src, dst in connections_list):
                connections_list.append((outcb_id, "loads"))
        connections = connections_list
        
    netlist_connections = []
    
    # 1. Wire L (Phase) path and dynamic loads connections using logical connections
    for src, dst in connections:
        src_lower = src.lower()
        dst_lower = dst.lower()
        
        # Resolve virtual loads ids
        if dst_lower == "loads" and outcb_ids:
            if get_base_type(src_lower) == "outcb" and src_lower != "outcb":
                match = re.search(r'\d+', src_lower)
                suffix = match.group() if match else "1"
                dst_mapped = f"load_{suffix}"
            else:
                dst_mapped = "load_1"  # default fallback
        else:
            dst_mapped = dst_lower
            
        if src_lower not in netlist_components or dst_mapped not in netlist_components:
            continue
            
        src_base = get_base_type(src_lower)
        dst_base = get_base_type(dst_mapped)
        
        # Find wiring rule
        rules = PIN_WIRING_RULES.get((src_base, dst_base), [])
        if not rules:
            if phase_mode == "three":
                rules = [("L1_out", "L1_in"), ("L2_out", "L2_in"), ("L3_out", "L3_in")]
            else:
                rules = [("L_out", "L_in")]

        for src_pin, dst_pin in rules:
            # Skip neutral connections if neutral is disabled
            src_pins_dict = COMPONENT_PINS.get(src_base)
            if src_pins_dict:
                src_pin_list = src_pins_dict.get(phase_mode, src_pins_dict.get("single"))
            else:
                src_pin_list = [PinDef("L_in", "L", 0.0, 5.0), PinDef("L_out", "L", 0.0, -5.0)]
                
            pin_def = next((p for p in src_pin_list if p.name == src_pin), None)
            if not pin_def:
                continue
            if pin_def.wire_type == "N" and not show_neutral:
                continue
                
            p1 = get_pin_position(src_lower, src_pin, component_positions[src_lower], phase_mode)
            p2 = get_pin_position(dst_mapped, dst_pin, component_positions[dst_mapped], phase_mode)
            
            # ISSUE 3: Bus should tap L at the target's horizontal position
            # For three-phase busbar, tap L1/L2/L3 at the target branch breaker L1/L2/L3 x offset
            if src_base == "bus":
                bus_pos = component_positions[src_lower]
                dst_pos = component_positions[dst_mapped]
                p1 = (dst_pos[0] + pin_def.x_offset, bus_pos[1] + pin_def.y_offset)
                
            netlist_connections.append({
                "src_component": src_lower,
                "src_pin": src_pin,
                "src_pos": list(p1),
                "dst_component": dst_mapped,
                "dst_pin": dst_pin,
                "dst_pos": list(p2),
                "wire_type": pin_def.wire_type
            })
            
    # 2. Wire N (Neutral) path — if nbar is present it must be connected
    if wire_neutral and "nbar" in netlist_components:
        nbar_x = component_positions["nbar"][0]
        n_horizontal = len(outcb_ids) if outcb_ids else len([c for c in netlist_components if get_base_type(c) == "loads"])
        nbar_x_tap = -45.0 if (phase_mode == "single" and n_horizontal <= 3) else nbar_x
        # ISSUE 1: Neutral bypasses breakers/RCDs. Connect supply -> nbar directly.
        if "supply" in netlist_components:
            p1 = (nbar_x_tap, component_positions["supply"][1] - 10.0)
            p2 = get_pin_position("nbar", "N_in", component_positions["nbar"], phase_mode)
            netlist_connections.append({
                "src_component": "supply",
                "src_pin": "N_out",
                "src_pos": list(p1),
                "dst_component": "nbar",
                "dst_pin": "N_in",
                "dst_pos": list(p2),
                "wire_type": "N"
            })
            
        # Wire nbar to each load
        load_ids = [cid for cid in netlist_components if get_base_type(cid) == "loads"]
        for load_id in load_ids:
            # ISSUE 3: nbar should feed Neutral at the load's own horizontal position on N-rail
            load_pos = component_positions[load_id]
            p1 = (nbar_x_tap, load_pos[1])
            p2 = get_pin_position(load_id, "N_in", load_pos, phase_mode)
            netlist_connections.append({
                "src_component": "nbar",
                "src_pin": "N_out",
                "src_pos": list(p1),
                "dst_component": load_id,
                "dst_pin": "N_in",
                "dst_pos": list(p2),
                "wire_type": "N"
            })
            
    # 3. Wire E (Earth) path — if ebar is present it must be connected
    if wire_earth and "ebar" in netlist_components:
        ebar_x = component_positions["ebar"][0]
        n_horizontal = len(outcb_ids) if outcb_ids else len([c for c in netlist_components if get_base_type(c) == "loads"])
        ebar_x_tap = -60.0 if (phase_mode == "single" and n_horizontal <= 3) else ebar_x
        # Supply E_out connects to ebar E_in
        if "supply" in netlist_components:
            p1 = (ebar_x_tap, component_positions["supply"][1] - 10.0)
            p2 = get_pin_position("ebar", "E_in", component_positions["ebar"], phase_mode)
            netlist_connections.append({
                "src_component": "supply",
                "src_pin": "E_out",
                "src_pos": list(p1),
                "dst_component": "ebar",
                "dst_pin": "E_in",
                "dst_pos": list(p2),
                "wire_type": "E"
            })
            
        # Optional N-E link if both bars exist
        if "nbar" in netlist_components:
            p1 = get_pin_position("nbar", "N_out", component_positions["nbar"], phase_mode)
            p2 = get_pin_position("ebar", "E_in", component_positions["ebar"], phase_mode)
            netlist_connections.append({
                "src_component": "nbar",
                "src_pin": "N_out",
                "src_pos": list(p1),
                "dst_component": "ebar",
                "dst_pin": "E_in",
                "dst_pos": list(p2),
                "wire_type": "E"  # N-E bond wire
            })
            
        # Wire ebar to each load
        load_ids = [cid for cid in netlist_components if get_base_type(cid) == "loads"]
        for load_id in load_ids:
            # ISSUE 3: ebar should feed Earth at the load's own horizontal position on E-rail
            load_pos = component_positions[load_id]
            p2 = get_pin_position(load_id, "E_in", load_pos, phase_mode)
            p1 = (ebar_x_tap, p2[1]) # Align tap vertically with E_in to make horizontal line
            netlist_connections.append({
                "src_component": "ebar",
                "src_pin": "E_out",
                "src_pos": list(p1),
                "dst_component": load_id,
                "dst_pin": "E_in",
                "dst_pos": list(p2),
                "wire_type": "E"
            })
            
    # Filter out duplicate connections (no identical source and destination pins)
    seen_connections = set()
    unique_connections = []
    for conn in netlist_connections:
        key = (conn["src_component"], conn["src_pin"], conn["dst_component"], conn["dst_pin"])
        if key in seen_connections:
            continue
        seen_connections.add(key)
        unique_connections.append(conn)
    netlist_connections = unique_connections
        
    return {
        "components": netlist_components,
        "connections": netlist_connections,
        "flags": flags
    }


# ── Netlist Validation Pass ──────────────────────────────────────────────────

def validate_netlist(netlist: dict) -> tuple[bool, list[str]]:
    """Perform validation checks on the generated netlist.
    
    Checks:
      1. All load components have active connections on their L_in pins.
      2. If Neutral is enabled (nbar present), loads must have active N_in connections.
      3. If Earth is enabled (ebar present), loads must have active E_in connections.
      4. Graph connectivity tracing: verifies continuous paths from supply output pins
         to all load input pins for L, N, and E nets.
    """
    components = netlist.get("components", {})
    connections = netlist.get("connections", [])
    errors = []
    
    # 1. Identify present loads and check N/E status
    load_ids = [cid for cid, comp in components.items() if comp["type"] == "loads"]
    flags = netlist.get("flags", {})
    show_neutral = flags.get("show_neutral", False)
    show_earth = flags.get("show_earth", False)
    
    has_nbar = "nbar" in components
    has_ebar = "ebar" in components
    has_supply = "supply" in components
    
    if not load_ids:
        errors.append("Validation Error: No load components found in netlist.")
        return False, errors
        
    # Map pin connections for rapid lookup
    # pin_key format: "component_id.pin_name"
    pin_connections: dict[str, list[dict]] = {}
    for conn in connections:
        src_pin_key = f"{conn['src_component']}.{conn['src_pin']}"
        dst_pin_key = f"{conn['dst_component']}.{conn['dst_pin']}"
        
        pin_connections.setdefault(src_pin_key, []).append(conn)
        pin_connections.setdefault(dst_pin_key, []).append(conn)
        
    supply_comp = components.get("supply", {})
    supply_pins = [p["name"] for p in supply_comp.get("pins", [])]
    is_three_phase = "L1_out" in supply_pins

    # Check that each load has L_in / L1_in / L2_in / L3_in, and conditionally N_in and E_in connected
    for load_id in load_ids:
        if is_three_phase:
            for phase_suffix in ["1", "2", "3"]:
                p_in_key = f"{load_id}.L{phase_suffix}_in"
                if p_in_key not in pin_connections:
                    errors.append(f"Load '{load_id}' is missing a Phase (L{phase_suffix}) connection on L{phase_suffix}_in.")
        else:
            l_in_key = f"{load_id}.L_in"
            if l_in_key not in pin_connections:
                errors.append(f"Load '{load_id}' is missing a Phase (L) connection on L_in.")
                
        n_in_key = f"{load_id}.N_in"
        e_in_key = f"{load_id}.E_in"
        
        if has_nbar and n_in_key not in pin_connections:
            errors.append(f"Load '{load_id}' is missing a Neutral (N) connection on N_in.")
            
        if has_ebar and e_in_key not in pin_connections:
            errors.append(f"Load '{load_id}' is missing an Earth (E) connection on E_in.")
            
    # 2. Graph Continuity Tracing (DFS)
    def trace_net(start_comp: str, start_pin: str, target_pin_name: str, net_type: str) -> set[str]:
        """DFS trace starting from supply pin, following connections of the matching net type."""
        visited_pins = set()
        reached_loads = set()
        
        start_key = f"{start_comp}.{start_pin}"
        if start_key not in pin_connections:
            return reached_loads
            
        stack = [start_key]
        visited_pins.add(start_key)
        
        while stack:
            curr = stack.pop()
            curr_comp, curr_pin = curr.split(".", 1)
            
            # Check if this is one of our target load input pins
            if get_base_type(curr_comp) == "loads" and curr_pin == target_pin_name:
                reached_loads.add(curr_comp)
                
            # Get connections touching this pin
            for conn in pin_connections.get(curr, []):
                # Only traverse matching wire types
                if conn["wire_type"] != net_type:
                    continue
                    
                # Identify next pin key
                next_src = f"{conn['src_component']}.{conn['src_pin']}"
                next_dst = f"{conn['dst_component']}.{conn['dst_pin']}"
                next_key = next_dst if curr == next_src else next_src
                
                if next_key not in visited_pins:
                    visited_pins.add(next_key)
                    stack.append(next_key)
                    
                    # Also push peer pin on same component (e.g., L_in to L_out pass-through)
                    peer_comp, peer_pin = next_key.split(".", 1)
                    comp_type = get_base_type(peer_comp)
                    
                    if comp_type not in ["supply", "bus", "loads"]:
                        # Auto-propagate L_in <-> L_out, N_in <-> N_out, E_in <-> E_out
                        peer_suffix = "_out" if peer_pin.endswith("_in") else "_in"
                        peer_base = peer_pin.split("_")[0]
                        comp_peer_pin = f"{peer_base}{peer_suffix}"
                        
                        comp_peer_key = f"{peer_comp}.{comp_peer_pin}"
                        if comp_peer_key not in visited_pins:
                            visited_pins.add(comp_peer_key)
                            stack.append(comp_peer_key)
                            
                    elif comp_type == "bus":
                        # Bus distributes L_in / L1_in / L2_in / L3_in to all matching L_out / L1_out / L2_out / L3_out pins
                        peer_base = peer_pin.split("_")[0]  # E.g. "L1" or "L"
                        if peer_pin.endswith("_in") and peer_base in ["L", "L1", "L2", "L3"]:
                            bus_peer_key = f"{peer_comp}.{peer_base}_out"
                            if bus_peer_key not in visited_pins:
                                visited_pins.add(bus_peer_key)
                                stack.append(bus_peer_key)
                                
        return reached_loads

    # Detect phase_mode from netlist components (e.g. if 'supply' has L1_out pin)
    supply_comp = components.get("supply", {})
    supply_pins = [p["name"] for p in supply_comp.get("pins", [])]
    is_three_phase = "L1_out" in supply_pins

    if has_supply:
        if is_three_phase:
            # Trace L1, L2, L3 separately
            for phase_suffix in ["1", "2", "3"]:
                p_out = f"L{phase_suffix}_out"
                p_in = f"L{phase_suffix}_in"
                reached = trace_net("supply", p_out, p_in, f"L{phase_suffix}")
                for load_id in load_ids:
                    if load_id not in reached:
                        errors.append(f"Continuity Error: Phase L{phase_suffix} path from supply to load '{load_id}' is broken.")
        else:
            # Phase (L) continuity check
            reached_l = trace_net("supply", "L_out", "L_in", "L")
            for load_id in load_ids:
                if load_id not in reached_l:
                    errors.append(f"Continuity Error: Phase (L) path from supply to load '{load_id}' is broken.")
                
        # Neutral (N) continuity check
        if has_nbar:
            reached_n = trace_net("supply", "N_out", "N_in", "N")
            for load_id in load_ids:
                if load_id not in reached_n:
                    errors.append(f"Continuity Error: Neutral (N) path from supply to load '{load_id}' is broken.")
                    
        # Earth (E) continuity check
        if has_ebar:
            reached_e = trace_net("supply", "E_out", "E_in", "E")
            for load_id in load_ids:
                if load_id not in reached_e:
                    errors.append(f"Continuity Error: Earth (E) path from supply to load '{load_id}' is broken.")
    else:
        errors.append("Validation Warning: No supply source found. Continuity cannot be fully traced.")
        
    # 3. Check nbar and ebar are reachable from supply (if present)
    if has_supply and has_nbar:
        # Check if any N-type connection reaches nbar
        nbar_reached = False
        for conn in connections:
            if conn["dst_component"] == "nbar" and conn["wire_type"] == "N":
                nbar_reached = True
                break
            if conn["src_component"] == "nbar" and conn["wire_type"] == "N":
                nbar_reached = True
                break
        if not nbar_reached:
            errors.append("Connectivity Error: Neutral Bar (nbar) is present but has no Neutral (N) connection to supply.")
            
    if has_supply and has_ebar:
        # Check if any E-type connection reaches ebar
        ebar_reached = False
        for conn in connections:
            if conn["dst_component"] == "ebar" and conn["wire_type"] == "E":
                ebar_reached = True
                break
            if conn["src_component"] == "ebar" and conn["wire_type"] == "E":
                ebar_reached = True
                break
        if not ebar_reached:
            errors.append("Connectivity Error: Earth Bar (ebar) is present but has no Earth (E) connection to supply.")

    is_ok = len(errors) == 0
    return is_ok, errors
