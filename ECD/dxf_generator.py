"""
dxf_exporter.py
================
Exports the electrical distribution diagram parsed_data to a DXF file
using the ezdxf library.

Layout strategy
---------------
Components are drawn as a vertical single-line diagram (SLD):
  Supply → MainCB → RCD/RCBO → Busbar → OutCB(s) → Loads
  Neutral Bar and Earth Bar hang off the busbar as horizontal branches.

Every component is drawn as a labeled rectangle (block).
Wire connections are LWPOLYLINE entities.
Neutral wires use a dashed linetype; earth wires use a dot-dash linetype.
Fault-path arrows (when present) are drawn as red dashed lines.

All coordinates are in millimetres.
"""

from __future__ import annotations
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
import ezdxf
from ezdxf import bbox as ezdxf_bbox
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment

try:
    from ECD import pin_model, symbols
except ImportError:
    import pin_model, symbols



@dataclass
class Node:
    id: str
    label: str
    group: Optional[str] = None
    order: int = 0


@dataclass
class Edge:
    src: str
    dst: str
    msg: str = ""


# ── Drawing constants (all in mm) ────────────────────────────────────────────

BOX_W        = 60       # component box width
BOX_H        = 20       # component box height
V_GAP        = 18       # vertical gap between boxes (centre-to-centre addition)
H_STEP       = V_GAP + BOX_H   # full vertical step between box centres
SIDE_OFFSET  = 90       # horizontal offset for NBar / EBar from centre column
FONT_H_MAIN  = 3.5      # main label font height
FONT_H_SMALL = 2.5      # sub-label font height
WIRE_OFFSET  = 2        # small inset so wires meet box edges cleanly

# Colours (AutoCAD colour index)
COL_PHASE   = colors.RED
COL_NEUTRAL = colors.BLUE
COL_EARTH   = colors.GREEN
COL_FAULT   = colors.MAGENTA
COL_BOX     = colors.WHITE
COL_TEXT    = colors.WHITE
COL_TITLE   = colors.CYAN

# Three-phase line colors
COL_L1      = colors.RED     # 1: Red
COL_L2      = colors.YELLOW  # 2: Yellow
COL_L3      = 30             # 30: Orange


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(label: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r'<br\s*/?>', ' | ', label)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _cx(x: float) -> float:
    """Return centre-x of a box whose left edge is at x."""
    return x + BOX_W / 2


def _cy(y: float) -> float:
    """Return centre-y of a box whose bottom edge is at y."""
    return y + BOX_H / 2


def _draw_box(msp, x: float, y: float, label: str,
              sublabel: str = "", layer: str = "COMPONENTS") -> None:
    """Draw a closed rectangle with centred text labels."""
    # FIX 1: close=True ensures the rectangle is properly closed.
    # Without this, web viewers like ShareCAD render an open polygon.
    msp.add_lwpolyline(
        [(x, y), (x + BOX_W, y),
         (x + BOX_W, y + BOX_H), (x, y + BOX_H)],
        close=True,
        dxfattribs={"layer": layer, "color": COL_BOX, "lineweight": 25},
    )

    # Main label (centred)
    cx, cy = _cx(x), _cy(y)
    if sublabel:
        # two lines
        msp.add_text(
            label,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_MAIN,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy + FONT_H_MAIN * 0.6),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            sublabel,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_SMALL,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy - FONT_H_MAIN * 0.6),
                        align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        msp.add_text(
            label,
            dxfattribs={
                "layer": layer,
                "height": FONT_H_MAIN,
                "color": COL_TEXT,
            },
        ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def _draw_wire(msp, pts: list[tuple[float, float]],
               color: int = COL_PHASE,
               layer: str = "WIRES_PHASE",
               linetype: str = "CONTINUOUS",
               lineweight: int = 25) -> None:
    """Draw a polyline wire between points."""
    msp.add_lwpolyline(
        pts,
        dxfattribs={
            "layer": layer,
            "color": color,
            "linetype": linetype,
            "lineweight": lineweight,
        },
        close=False,
    )


def _draw_label(msp, x: float, y: float, text: str,
                height: float = FONT_H_SMALL,
                color: int = COL_PHASE,
                layer: str = "WIRE_LABELS") -> None:
    msp.add_text(
        text,
        dxfattribs={"layer": layer, "height": height, "color": color},
    ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_LEFT)


def _add_linetypes(doc) -> None:
    ezdxf.setup_linetypes(doc)


# ── Tiered page sizes (landscape, in mm) ─────────────────────────────────────
PAGE_SIZES = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "CUSTOM_15": (700.0, 540.0),
}

def _get_page_size(n_circuits: int, phase_mode: str = "single") -> tuple[float, float]:
    """Return (width, height) in mm based on circuit count and phase mode."""
    if phase_mode == "three":
        if n_circuits <= 7:
            return PAGE_SIZES["A2"]
        else:
            return PAGE_SIZES["A1"]
            
    # For single phase
    if n_circuits <= 4:
        return PAGE_SIZES["A3"]
    elif n_circuits >= 12:
        return PAGE_SIZES["CUSTOM_15"]
    else:
        return PAGE_SIZES["A2"]


def _add_layers(doc) -> None:
    layers_def = {
        "BACKGROUND":    (250,            "Continuous"),
        "COMPONENTS":    (colors.WHITE,   "Continuous"),
        "WIRES_PHASE":   (COL_PHASE,      "Continuous"),
        "WIRES_NEUTRAL": (COL_NEUTRAL,    "DASHED"),
        "WIRES_EARTH":   (COL_EARTH,      "DASHDOT"),
        "WIRES_FAULT":   (COL_FAULT,      "DASHED"),
        "WIRE_LABELS":   (colors.YELLOW,  "Continuous"),
        "TITLE":         (COL_TITLE,      "Continuous"),
        "NOTES":         (colors.WHITE,   "Continuous"),
        "LEGEND":        (colors.WHITE,   "Continuous"),
    }
    for name, (color, lt) in layers_def.items():
        if name not in doc.layers:
            layer = doc.layers.add(name)   # create first …
            layer.dxf.color    = color     # … then set attrs explicitly
            layer.dxf.linetype = lt


def _sort_outcb_ids(component_ids: list[str]) -> list[str]:
    try:
        from ECD.pin_model import get_base_type
    except ImportError:
        from pin_model import get_base_type

    def _sort_key(cid: str) -> tuple[int, int]:
        match = re.search(r'\d+', cid)
        if match:
            return (0, int(match.group()))
        return (1, 0)

    outcbs = [cid for cid in component_ids if get_base_type(cid) == "outcb" and cid.lower() != "outcb"]
    if not outcbs and any(cid.lower() == "outcb" for cid in component_ids):
        orig = next((cid for cid in component_ids if cid.lower() == "outcb"), "outcb")
        return [orig]
    return sorted(outcbs, key=_sort_key)


def ensure_connections(parsed_data: dict) -> list[tuple[str, str]]:
    """Return deterministic connectivity for the component list, backfilling any missing standard edges."""
    components = parsed_data.get("components", [])
    component_ids = [cid for cid, _ in components if isinstance(cid, str)]
    if not component_ids:
        return []

    try:
        from ECD.pin_model import get_base_type
    except ImportError:
        from pin_model import get_base_type

    # Start with the parsed connections if present, otherwise build defaults
    raw_conns = parsed_data.get("connections")
    connections: list[tuple[str, str]] = []
    seen = set()

    def add_edge(src: str, dst: str) -> None:
        if not src or not dst or src == dst:
            return
        src_lower = src.lower()
        dst_lower = dst.lower()
        # Find exact case-matching IDs in component_ids
        src_id = next((c for c in component_ids if c.lower() == src_lower), src)
        dst_id = next((c for c in component_ids if c.lower() == dst_lower), dst)
        if src_id not in component_ids or dst_id not in component_ids:
            return
        if (src_id, dst_id) in seen:
            return
        seen.add((src_id, dst_id))
        connections.append((src_id, dst_id))

    if raw_conns:
        # Load existing connections
        for src, dst in raw_conns:
            add_edge(src, dst)
    else:
        # Generate default connections in sequence
        outcb_ids = _sort_outcb_ids(component_ids)
        if outcb_ids:
            if "loads" not in component_ids:
                component_ids.append("loads")

        has_maincb = "maincb" in component_ids
        has_rcd = "rcd" in component_ids or "rcbo" in component_ids
        has_bus = "bus" in component_ids
        has_loads = "loads" in component_ids

        # 1. Main trunk vertical spine
        main_column = []
        known_types = {"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads"}
        for cid in component_ids:
            cid_lower = cid.lower()
            bt = get_base_type(cid_lower)
            if cid_lower in ["supply", "maincb", "rcd", "rcbo", "bus"] or (
                cid_lower not in known_types 
                and bt != "outcb" 
                and bt != "loads"
            ):
                if cid_lower not in main_column:
                    main_column.append(cid_lower)
                    
        for src, dst in zip(main_column, main_column[1:]):
            add_edge(src, dst)
            
        # 2. Connect the end of the vertical spine
        if main_column:
            last_trunk = main_column[-1]
            if last_trunk != "bus" and has_bus:
                add_edge(last_trunk, "bus")
            elif last_trunk != "bus":
                if outcb_ids:
                    for outcb_id in outcb_ids:
                        add_edge(last_trunk, outcb_id)
                elif has_loads:
                    add_edge(last_trunk, "loads")

        load_ids = [cid for cid in component_ids if get_base_type(cid) == "loads" and cid != "loads"]

        if has_bus:
            if outcb_ids:
                for outcb_id in outcb_ids:
                    add_edge("bus", outcb_id)
            else:
                if has_loads:
                    add_edge("bus", "loads")
                for load_id in load_ids:
                    add_edge("bus", load_id)

        # Dynamic loads
        if outcb_ids:
            for outcb_id in outcb_ids:
                add_edge(outcb_id, "loads")
        elif has_loads or load_ids:
            target = "loads" if has_loads else load_ids[0]
            if not any(dst == target for _, dst in connections):
                for source in ["bus", "rcd", "rcbo", "maincb", "supply"]:
                    if source in component_ids:
                        add_edge(source, target)
                        break

        if load_ids and outcb_ids:
            for outcb_id in outcb_ids:
                match = re.search(r'\d+', outcb_id)
                suffix = match.group() if match else ""
                matching_load = next((l for l in load_ids if l.endswith(f"_{suffix}") or l.endswith(suffix)), None)
                if matching_load:
                    add_edge(outcb_id, matching_load)
                else:
                    add_edge(outcb_id, load_ids[0])

        for edge in parsed_data.get("edges", []):
            add_edge(edge.src, edge.dst)

    # ── Backfill standard missing connections ──
    outcb_ids = _sort_outcb_ids(component_ids)
    
    # 1. outcb -> loads
    if outcb_ids:
        for outcb_id in outcb_ids:
            if not any(src.lower() == outcb_id.lower() and (dst.lower() == "loads" or get_base_type(dst) == "loads") for src, dst in connections):
                add_edge(outcb_id, "loads")
                
    # 2. supply -> maincb
    if "supply" in component_ids and "maincb" in component_ids:
        if not any(src.lower() == "supply" and dst.lower() == "maincb" for src, dst in connections):
            add_edge("supply", "maincb")
            
    # 3. maincb -> rcd
    rcd_key = "rcd" if "rcd" in component_ids else ("rcbo" if "rcbo" in component_ids else None)
    if "maincb" in component_ids and rcd_key:
        if not any(src.lower() == "maincb" and dst.lower() == rcd_key.lower() for src, dst in connections):
            add_edge("maincb", rcd_key)
            
    # 4. rcd -> bus
    if rcd_key and "bus" in component_ids:
        if not any(src.lower() == rcd_key.lower() and dst.lower() == "bus" for src, dst in connections):
            add_edge(rcd_key, "bus")
            
    # 5. maincb -> bus (if no RCD)
    if "maincb" in component_ids and "bus" in component_ids and not rcd_key:
        if not any(src.lower() == "maincb" and dst.lower() == "bus" for src, dst in connections):
            add_edge("maincb", "bus")
            
    # 6. bus -> outcb_N
    if "bus" in component_ids and outcb_ids:
        for outcb_id in outcb_ids:
            if not any(src.lower() == "bus" and dst.lower() == outcb_id.lower() for src, dst in connections):
                add_edge("bus", outcb_id)

    # Append any user-defined or custom edges from the sequence diagram
    for edge in parsed_data.get("edges", []):
        src = edge.src.lower()
        dst = edge.dst.lower()
        if src in component_ids and dst in component_ids:
            add_edge(src, dst)

    # Filter out direct connections from upstream to loads if branch breakers exist
    # to prevent drawing bypass lines that overlap/hide branch breakers
    if outcb_ids:
        filtered_connections = []
        for src, dst in connections:
            src_base = get_base_type(src)
            dst_base = get_base_type(dst)
            if src_base in ("supply", "maincb", "rcd", "rcbo", "bus") and dst_base == "loads":
                continue
            filtered_connections.append((src, dst))
        connections = filtered_connections

    return connections


def parse_mermaid_sequence(mermaid: str):
    nodes = {}
    edges = []
    groups = {}
    order = 0
    current_group = None

    for line in mermaid.splitlines():
        line = line.strip()
        if not line:
            continue

        # box "Group Name"
        m = re.match(r'box .*?"(.+?)"', line)
        if m:
            current_group = m.group(1)
            continue

        if line == "end":
            current_group = None
            continue

        # participant A as Label
        m = re.match(r'participant\s+(\w+)\s+as\s+(.+)', line)
        if m:
            pid, label = m.groups()
            nodes[pid] = Node(
                id=pid,
                label=label.strip(),
                group=current_group,
                order=order,
            )
            order += 1
            continue

        # A->>B: message
        m = re.match(r'(\w+)->>\s*(\w+):\s*(.+)', line)
        if m:
            src, dst, msg = m.groups()
            edges.append(Edge(src, dst, msg))
            continue

    return list(nodes.values()), edges

def normalize_for_dxf(nodes, edges):
    # Order nodes top → bottom based on appearance
    nodes = sorted(nodes, key=lambda n: n.order)

    components = []
    for n in nodes:
        cid = n.id.lower()
        components.append((cid, n.label))

    parsed_data = {
        "components": components,
        "flags": {
            "show_neutral": False,
            "show_earth": False,
            "show_fault_paths": False,
        },
        "voltage": "",
        "language": "en",
        "edges": edges,  # keep for wiring phase
    }
    parsed_data["connections"] = ensure_connections(parsed_data)
    return parsed_data


def subtract_intervals(val_min: float, val_max: float, covered: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Subtract covered (min, max) intervals from the interval (val_min, val_max)."""
    uncovered = [(val_min, val_max)]
    for cv_min, cv_max in covered:
        next_uncovered = []
        for uv_min, uv_max in uncovered:
            if cv_max <= uv_min or cv_min >= uv_max:
                # No overlap
                next_uncovered.append((uv_min, uv_max))
            else:
                # Overlap
                if cv_min > uv_min:
                    next_uncovered.append((uv_min, cv_min))
                if cv_max < uv_max:
                    next_uncovered.append((cv_max, uv_max))
        uncovered = next_uncovered
    return uncovered


def route_wire_bend(p1: tuple[float, float], p2: tuple[float, float]) -> list[tuple[float, float]]:
    """Generate Manhattan right-angle bend points between p1 and p2."""
    x1, y1 = p1
    x2, y2 = p2
    
    if abs(x1 - x2) < 0.1:
        return [(x1, y1), (x1, y2)]
    if abs(y1 - y2) < 0.1:
        return [(x1, y1), (x2, y1)]
        
    # Manhattan bend: vertical first, then horizontal
    return [(x1, y1), (x1, y2), (x2, y2)]


def export_dxf(parsed_data: dict, output_path: str = None) -> Optional[ezdxf.document.Drawing]:
    """
    Convert parsed_data (as produced by MermaidGenerator / OllamaClient)
    into a DXF electrical single-line diagram.

    Parameters
    ----------
    parsed_data : dict
        Keys used:
          "components"  – list of (id, label) tuples
          "flags"       – dict with show_neutral, show_earth, show_rcd,
                          show_fault_paths, show_protection_notes
          "voltage"     – string e.g. "230V AC"
          "language"    – "en" or "ja"
    output_path : str
        Destination file path (should end in .dxf).
    """

    # ── Unpack parsed_data ────────────────────────────────────────────────────
    components: list[tuple[str, str]] = parsed_data.get("components", [])
    flags: dict = parsed_data.get("flags", {})
    voltage: str = parsed_data.get("voltage", "")
    language: str = parsed_data.get("language", "en")
    connections: list[tuple[str, str]] = parsed_data.get("connections") or ensure_connections(parsed_data)

    comp_map = {cid: _clean(lbl) for cid, lbl in components}

    show_neutral  = flags.get("show_neutral",  "nbar" in comp_map)
    show_earth    = flags.get("show_earth",    "ebar" in comp_map)
    show_rcd      = flags.get("show_rcd",      "rcd"  in comp_map or "rcbo" in comp_map)
    show_faults   = flags.get("show_fault_paths", False)
    show_notes    = flags.get("show_protection_notes", False)

    # Outgoing branch breakers
    outcb_ids = sorted(
        [cid for cid in comp_map if pin_model.get_base_type(cid) == "outcb" and cid != "outcb"],
        key=lambda s: int(re.search(r'\d+', s).group()) if re.search(r'\d+', s) else 0,
    )
    if not outcb_ids and "outcb" in comp_map:
        outcb_ids = ["outcb"]
        
    # Unconditionally ensure outcb -> loads connections exist if there are branch breakers
    if outcb_ids:
        for outcb_id in outcb_ids:
            if not any(src == outcb_id and (dst == "loads" or pin_model.get_base_type(dst) == "loads") for src, dst in connections):
                connections.append((outcb_id, "loads"))

 
    box_positions = pin_model.compute_component_positions(parsed_data)
    netlist = pin_model.generate_netlist(parsed_data, box_positions)
    
    # Resolve phase mode for symbol selection
    phase_hint = parsed_data.get("phase_hint") or flags.get("phase_hint")
    phase_mode = pin_model.determine_phase_mode(voltage, phase_hint)
    

    # ── Create DXF document ───────────────────────────────────────────────────
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"]   = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric
    doc.header["$LUNITS"]     = 4  # millimetres
    _add_linetypes(doc)
    _add_layers(doc)
    msp = doc.modelspace()

    # ── Tiered page sizing ─────────────────────────────────────────────────────
    n_circuits = len(outcb_ids) if outcb_ids else 1
    page_w, page_h = _get_page_size(n_circuits, phase_mode)

    # Calculate content bounding box for centering within the page
    x_coords = [pos[0] for pos in box_positions.values()]
    y_coords = [pos[1] for pos in box_positions.values()]
    
    # Account for ground symbol below ebar
    if "ebar" in box_positions:
        y_coords.append(box_positions["ebar"][1] - 20.0)

    content_cx = (min(x_coords) + max(x_coords)) / 2.0
    content_cy = (min(y_coords) + max(y_coords)) / 2.0

    # Page bounds centered on content
    min_x = content_cx - page_w / 2.0
    max_x = content_cx + page_w / 2.0
    min_y = content_cy - page_h / 2.0
    max_y = content_cy + page_h / 2.0
    
    # Compile legend items early to calculate required height
    if phase_mode == "three":
        legend_wires = [
            (COL_L1, "Continuous", "Phase L1"),
            (COL_L2, "Continuous", "Phase L2"),
            (COL_L3, "Continuous", "Phase L3"),
        ]
    else:
        legend_wires = [
            (COL_PHASE, "Continuous", "Phase (L)"),
        ]

    if show_neutral:
        legend_wires.append((COL_NEUTRAL, "DASHED",    "Neutral (N)"))
    if show_earth:
        legend_wires.append((COL_EARTH,   "DASHDOT",   "Earth / PE (E)"))
    if show_faults:
        legend_wires.append((COL_FAULT,   "DASHED",    "Fault Current Path"))

    if phase_mode == "three":
        legend_symbols = []
        if "supply" in comp_map:
            legend_symbols.append(("SYM_SUPPLY_3PH",  "Three-Phase Supply"))
        if "maincb" in comp_map:
            legend_symbols.append(("SYM_BREAKER_3PH", "Main Breaker (maincb)"))
        if outcb_ids:
            legend_symbols.append(("SYM_MCB_3PH",     "Outgoing MCB (outcb)"))
        if show_rcd:
            legend_symbols.append(("SYM_RCD_3PH", "RCD / RCBO"))
        if any(pin_model.get_base_type(cid) == "loads" for cid in comp_map):
            legend_symbols.append(("SYM_MOTOR_3PH", "Motor Load"))
    else:
        legend_symbols = []
        if "maincb" in comp_map:
            legend_symbols.append(("SYM_BREAKER", "Main Breaker (maincb)"))
        if outcb_ids:
            legend_symbols.append(("SYM_MCB",     "Outgoing MCB (outcb)"))
        if show_rcd:
            legend_symbols.append(("SYM_RCD", "RCD / RCBO"))
        if any(pin_model.get_base_type(cid) == "loads" for cid in comp_map):
            legend_symbols.append(("SYM_LAMP", "Load / Lamp"))

    if show_earth and "ebar" in comp_map:
        legend_symbols.append(("SYM_GROUND", "Earth Terminus"))
        
    has_terminal = "nbar" in comp_map or "ebar" in comp_map or any("terminal" in cid for cid in comp_map)
    if has_terminal:
        legend_symbols.append(("SYM_TERMINAL_ROW_2", "Terminal Block"))
        
    has_junctions = ("bus" in comp_map and len(outcb_ids) > 0) or (show_neutral and "nbar" in comp_map) or (show_earth and "ebar" in comp_map)
    if has_junctions:
        legend_symbols.append(("SYM_JUNCTION", "Junction Dot"))

    has_custom = any(pin_model.get_base_type(cid) not in {"supply", "maincb", "rcd", "rcbo", "bus", "nbar", "ebar", "loads", "outcb"} for cid in comp_map)
    if has_custom:
        legend_symbols.append(("SYM_GENERIC", "Custom Device"))

    n_legend_items = len(legend_wires) + len(legend_symbols)
    legend_height = n_legend_items * 12.0 + 15.0
    
    col_x = 0.0
    start_y = 100.0

    # ── Draw background rectangle ─────────────────────────────────────────────
    # (Removed to prevent visual box-like border around exported PNGs)

    # ── Title block ───────────────────────────────────────────────────────────
    title_lines = [
        "Generated by Electrical Diagram Generator",
        f"Voltage: {voltage}" if voltage else " Not Specified",
        "ELECTRICAL DISTRIBUTION DIAGRAM",
    ]
    tx = (min(x_coords) + max(x_coords)) / 2.0
    ty = max_y - 30.0
    title_entities = []
    for line in title_lines:
        if line:
            t_ent = msp.add_text(
                line,
                dxfattribs={"layer": "TITLE", "height": FONT_H_MAIN + 1.0,
                            "color": COL_TITLE},
            )
            t_ent.set_placement((tx, ty), align=TextEntityAlignment.BOTTOM_CENTER)
            title_entities.append(t_ent)
            ty += (FONT_H_MAIN + 1.0) * 2.0

    # ── Draw component symbols ────────────────────────────────────────────────
    # Ensure symbols are registered
    symbols.register_all_symbols(doc)
    
    for cid, (bx, by) in box_positions.items():
        base_type = pin_model.get_base_type(cid)
        block_name = None
        
        if base_type == "supply":
            if phase_mode == "three":
                block_name = "SYM_SUPPLY_3PH"
            # Single-phase supply has no symbol block (drawn as text label in Phase 3A)
        elif base_type == "maincb":
            block_name = "SYM_BREAKER_3PH" if phase_mode == "three" else "SYM_BREAKER"
        elif base_type == "rcd" or base_type == "rcbo":
            block_name = "SYM_RCD_3PH" if phase_mode == "three" else "SYM_RCD"
        elif base_type == "outcb":
            block_name = "SYM_MCB_3PH" if phase_mode == "three" else "SYM_MCB"
        elif base_type == "loads":
            block_name = "SYM_MOTOR_3PH" if phase_mode == "three" else "SYM_LAMP"
        elif base_type == "ebar":
            # Parametric terminal row: size equals loads count + 1
            n_loads = len(outcb_ids) if outcb_ids else 1
            block_name = symbols.get_or_create_terminal_row(doc, n=n_loads + 1)
        elif base_type == "nbar":
            n_loads = len(outcb_ids) if outcb_ids else 1
            block_name = symbols.get_or_create_terminal_row(doc, n=n_loads + 1)
        elif base_type == "bus":
            # Bus is represented by the horizontal phase wire(s), no symbol block
            pass
        else:
            # Unknown component type — use generic fallback rectangle
            block_name = "SYM_GENERIC"
            
        if block_name:
            msp.add_blockref(block_name, insert=(bx, by))
            
        # Draw labels for components
        label = comp_map.get(cid)
        if not label:
            if pin_model.get_base_type(cid) == "loads":
                label = comp_map.get("loads", "LOAD")
            else:
                label = cid.upper()
                
        # For outgoing breakers, override the diagram label to OUTCB_(number)
        if base_type == "outcb":
            match = re.search(r'\d+', cid)
            suffix = match.group() if match else "1"
            label = f"OUTCB_{suffix}"
                
        # Split label at ' | ' for two-line display
        parts = label.split(" | ", 1)
        main_lbl = parts[0]
        sub_lbl  = parts[1] if len(parts) > 1 else ""
        
        # Always force short labels for EBar / NBar regardless of LLM output
        if cid == "nbar":
            main_lbl = "NBar"
        elif cid == "ebar":
            main_lbl = "EBar"
        
        if base_type == "supply":
            msp.add_text(
                main_lbl,
                dxfattribs={"height": FONT_H_MAIN, "layer": "COMPONENTS"}
            ).set_placement((bx + 3.0, by), align=TextEntityAlignment.MIDDLE_LEFT)
        elif base_type in ["loads", "nbar", "ebar"]:
            # Labels for loads are drawn in the Load Schedule on the right side of the sheet.
            # Labels for nbar/ebar are drawn at the top of the vertical rails above the figure.
            pass
        else:
            # Shift busbar label up slightly to prevent overlapping the horizontal wire
            y_offset = 4.0 if cid == "bus" else 0.0
            x_offset = 3.5 if base_type == "outcb" else 8.0
            msp.add_text(
                main_lbl,
                dxfattribs={"height": FONT_H_SMALL, "layer": "COMPONENTS"}
            ).set_placement((bx + x_offset, by + y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
            if sub_lbl:
                msp.add_text(
                    sub_lbl,
                    dxfattribs={"height": FONT_H_SMALL - 0.5, "layer": "COMPONENTS"}
                  ).set_placement((bx + x_offset, by - 3.0 + y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
                      
    # Insert ground symbol below ebar
    if "ebar" in box_positions:
        ex, ey = box_positions["ebar"]
        msp.add_blockref("SYM_GROUND", insert=(ex, ey - 20.0))
        msp.add_text(
            "GND",
            dxfattribs={"height": FONT_H_SMALL, "layer": "COMPONENTS"}
        ).set_placement((ex - 6.0, ey - 20.0), align=TextEntityAlignment.MIDDLE_RIGHT)

    # ── Draw wires from netlist connections ──────────────────────────────────
    nbar_x = box_positions["nbar"][0] if "nbar" in box_positions else -45.0
    ebar_x = box_positions["ebar"][0] if "ebar" in box_positions else -60.0

    nbar_y_coords = []
    ebar_y_coords = []
    bus_x_coords = [0.0]
    
    if "ebar" in box_positions:
        ebar_y_coords.append(box_positions["ebar"][1] - 17.0)
        
    for conn in netlist["connections"]:
        src_pos = conn["src_pos"]
        dst_pos = conn["dst_pos"]
        wtype = conn["wire_type"]
        
        if wtype == "N":
            if abs(src_pos[0] - nbar_x) < 0.1:
                nbar_y_coords.append(src_pos[1])
                if conn["dst_component"].startswith("load"):
                    nbar_y_coords.append(src_pos[1] - 10.0)
            if abs(dst_pos[0] - nbar_x) < 0.1:
                nbar_y_coords.append(dst_pos[1])
        elif wtype == "E":
            if abs(src_pos[0] - ebar_x) < 0.1:
                ebar_y_coords.append(src_pos[1])
                if conn["dst_component"].startswith("load"):
                    ebar_y_coords.append(src_pos[1] - 22.0)
            if abs(dst_pos[0] - ebar_x) < 0.1:
                ebar_y_coords.append(dst_pos[1])
        elif wtype in ("L", "L1", "L2", "L3") and conn["src_component"] == "bus":
            bus_x_coords.append(src_pos[0])
            
    # Interval tracking for overlap avoidance
    from collections import defaultdict
    covered_x_intervals = defaultdict(list)
    covered_y_intervals = defaultdict(list)
    
    # 1. Draw persistent L-rail busbar
    if "bus" in box_positions:
        bus_y = box_positions["bus"][1]
        x_min, x_max = min(bus_x_coords), max(bus_x_coords)
        if phase_mode == "three":
            spacing = 3.0
            for offset_y in (spacing, 0.0, -spacing):
                _draw_wire(
                    msp,
                    [(x_min, bus_y + offset_y), (x_max, bus_y + offset_y)],
                    color=COL_PHASE,
                    layer="WIRES_PHASE",
                    linetype="CONTINUOUS",
                    lineweight=25
                )
                covered_x_intervals[("L", bus_y + offset_y)].append((x_min, x_max))
        else:
            _draw_wire(
                msp,
                [(x_min, bus_y), (x_max, bus_y)],
                color=COL_PHASE,
                layer="WIRES_PHASE",
                linetype="CONTINUOUS",
                lineweight=25
            )
            covered_x_intervals[("L", bus_y)].append((x_min, x_max))
        
    # 2. Draw persistent N-rail
    if "nbar" in box_positions and nbar_y_coords:
        y_min, y_max = min(nbar_y_coords), max(nbar_y_coords)
        _draw_wire(
            msp,
            [(nbar_x, y_min), (nbar_x, y_max)],
            color=COL_NEUTRAL,
            layer="WIRES_NEUTRAL",
            linetype="DASHED",
            lineweight=18
        )
        covered_y_intervals[("N", nbar_x)].append((y_min, y_max))
        
    # 3. Draw persistent E-rail
    if "ebar" in box_positions and ebar_y_coords:
        y_min, y_max = min(ebar_y_coords), max(ebar_y_coords)
        _draw_wire(
            msp,
            [(ebar_x, y_min), (ebar_x, y_max)],
            color=COL_EARTH,
            layer="WIRES_EARTH",
            linetype="DASHDOT",
            lineweight=13
        )
        covered_y_intervals[("E", ebar_x)].append((y_min, y_max))

    # Compile junction dots set
    junction_dots = set()
    
    # 4. Draw routed connections
    for conn in netlist["connections"]:
        src_pos = conn["src_pos"]
        dst_pos = conn["dst_pos"]
        wtype = conn["wire_type"]
        
        # Populate junction dots at tap points on rails
        if wtype in ("L", "L1", "L2", "L3") and "bus" in box_positions:
            bus_y = box_positions["bus"][1]
            is_on_bus_src = abs(src_pos[1] - bus_y) <= 3.1 if phase_mode == "three" else abs(src_pos[1] - bus_y) < 0.1
            if conn["src_component"] == "bus" and is_on_bus_src:
                junction_dots.add(tuple(src_pos))
            is_on_bus_dst = abs(dst_pos[1] - bus_y) <= 3.1 if phase_mode == "three" else abs(dst_pos[1] - bus_y) < 0.1
            if conn["dst_component"] == "bus" and is_on_bus_dst:
                junction_dots.add(tuple(dst_pos))
        elif wtype == "N" and "nbar" in box_positions:
            if conn["src_component"] == "nbar" and conn["dst_component"].startswith("load"):
                junction_dots.add(tuple(dst_pos))
        elif wtype == "E" and "ebar" in box_positions:
            if conn["src_component"] == "ebar" and conn["dst_component"].startswith("load"):
                junction_dots.add(tuple(dst_pos))
            if conn["src_component"] == "nbar" and conn["dst_component"] == "ebar":
                junction_dots.add((nbar_x, dst_pos[1]))
                
        # Skip drawing Neutral/Earth wires to loads here; drawn as daisy chains below
        if conn["dst_component"].startswith("load") and wtype in ("N", "E"):
            continue
            
        # Route standard wire with Manhattan bend
        pts = route_wire_bend(src_pos, dst_pos)
        
        # Draw each segment, skipping if collinear with persistent rails
        for p_s, p_e in zip(pts, pts[1:]):
            is_horizontal = abs(p_s[1] - p_e[1]) < 0.1
            is_vertical = abs(p_s[0] - p_e[0]) < 0.1
            
            if is_horizontal:
                y_val = p_s[1]
                x_min, x_max = min(p_s[0], p_e[0]), max(p_s[0], p_e[0])
                parts = subtract_intervals(x_min, x_max, covered_x_intervals[(wtype, y_val)])
                for ux_min, ux_max in parts:
                    if wtype == "L":
                        layer = "WIRES_PHASE"
                        color = COL_PHASE
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L1":
                        layer = "WIRES_PHASE"
                        color = COL_L1
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L2":
                        layer = "WIRES_PHASE"
                        color = COL_L2
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L3":
                        layer = "WIRES_PHASE"
                        color = COL_L3
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "N":
                        layer = "WIRES_NEUTRAL"
                        color = COL_NEUTRAL
                        linetype = "DASHED"
                        lineweight = 18
                    elif wtype == "E":
                        layer = "WIRES_EARTH"
                        color = COL_EARTH
                        linetype = "DASHDOT"
                        lineweight = 13
                    else:
                        layer = "WIRES_PHASE"
                        color = COL_PHASE
                        linetype = "CONTINUOUS"
                        lineweight = 25
                        
                    _draw_wire(msp, [(ux_min, y_val), (ux_max, y_val)], color=color, layer=layer, linetype=linetype, lineweight=lineweight)
                    covered_x_intervals[(wtype, y_val)].append((ux_min, ux_max))
                    
            elif is_vertical:
                x_val = p_s[0]
                y_min, y_max = min(p_s[1], p_e[1]), max(p_s[1], p_e[1])
                parts = subtract_intervals(y_min, y_max, covered_y_intervals[(wtype, x_val)])
                for uy_min, uy_max in parts:
                    if wtype == "L":
                        layer = "WIRES_PHASE"
                        color = COL_PHASE
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L1":
                        layer = "WIRES_PHASE"
                        color = COL_L1
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L2":
                        layer = "WIRES_PHASE"
                        color = COL_L2
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "L3":
                        layer = "WIRES_PHASE"
                        color = COL_L3
                        linetype = "CONTINUOUS"
                        lineweight = 25
                    elif wtype == "N":
                        layer = "WIRES_NEUTRAL"
                        color = COL_NEUTRAL
                        linetype = "DASHED"
                        lineweight = 18
                    elif wtype == "E":
                        layer = "WIRES_EARTH"
                        color = COL_EARTH
                        linetype = "DASHDOT"
                        lineweight = 13
                    else:
                        layer = "WIRES_PHASE"
                        color = COL_PHASE
                        linetype = "CONTINUOUS"
                        lineweight = 25
                        
                    _draw_wire(msp, [(x_val, uy_min), (x_val, uy_max)], color=color, layer=layer, linetype=linetype, lineweight=lineweight)
                    covered_y_intervals[(wtype, x_val)].append((uy_min, uy_max))


    # Draw daisy-chained Neutral and Earth wires to loads to prevent overlapping horizontal runs
    # Draw daisy-chained Neutral and Earth wires to loads to prevent overlapping horizontal runs
    load_n_conns = []
    load_e_conns = []
    for conn in netlist["connections"]:
        dst = conn["dst_component"]
        wtype = conn["wire_type"]
        if dst.startswith("load") and wtype == "N":
            load_n_conns.append(conn)
        elif dst.startswith("load") and wtype == "E":
            load_e_conns.append(conn)
            
    def draw_daisy_chain(conns, rail_x, y_bend, color, layer, linetype, lineweight, wtype):
        if not conns:
            return
        # Split into left and right groups relative to the rail_x
        left_conns = [c for c in conns if c["dst_pos"][0] < rail_x]
        right_conns = [c for c in conns if c["dst_pos"][0] >= rail_x]
        
        # Sort left group descending (closest to rail_x first, e.g., -50, -70)
        left_conns.sort(key=lambda c: c["dst_pos"][0], reverse=True)
        # Sort right group ascending (closest to rail_x first, e.g., -20, 20, 60)
        right_conns.sort(key=lambda c: c["dst_pos"][0])
        
        # Draw left group daisy chain
        if left_conns:
            first = left_conns[0]
            src = first["src_pos"]
            dst = first["dst_pos"]
            pts = [src, (src[0], y_bend), (dst[0], y_bend), dst]
            _draw_wire(msp, pts, color=color, layer=layer, linetype=linetype, lineweight=lineweight)
            covered_x_intervals[(wtype, y_bend)].append((min(src[0], dst[0]), max(src[0], dst[0])))
            covered_y_intervals[(wtype, dst[0])].append((min(y_bend, dst[1]), max(y_bend, dst[1])))
            
            for i in range(1, len(left_conns)):
                prev_dst = left_conns[i-1]["dst_pos"]
                curr_dst = left_conns[i]["dst_pos"]
                pts = [prev_dst, (prev_dst[0], y_bend), (curr_dst[0], y_bend), curr_dst]
                _draw_wire(msp, pts, color=color, layer=layer, linetype=linetype, lineweight=lineweight)
                covered_x_intervals[(wtype, y_bend)].append((min(prev_dst[0], curr_dst[0]), max(prev_dst[0], curr_dst[0])))
                covered_y_intervals[(wtype, curr_dst[0])].append((min(y_bend, curr_dst[1]), max(y_bend, curr_dst[1])))
                
        # Draw right group daisy chain
        if right_conns:
            first = right_conns[0]
            src = first["src_pos"]
            dst = first["dst_pos"]
            pts = [src, (src[0], y_bend), (dst[0], y_bend), dst]
            _draw_wire(msp, pts, color=color, layer=layer, linetype=linetype, lineweight=lineweight)
            covered_x_intervals[(wtype, y_bend)].append((min(src[0], dst[0]), max(src[0], dst[0])))
            covered_y_intervals[(wtype, dst[0])].append((min(y_bend, dst[1]), max(y_bend, dst[1])))
            
            for i in range(1, len(right_conns)):
                prev_dst = right_conns[i-1]["dst_pos"]
                curr_dst = right_conns[i]["dst_pos"]
                pts = [prev_dst, (prev_dst[0], y_bend), (curr_dst[0], y_bend), curr_dst]
                _draw_wire(msp, pts, color=color, layer=layer, linetype=linetype, lineweight=lineweight)
                covered_x_intervals[(wtype, y_bend)].append((min(prev_dst[0], curr_dst[0]), max(prev_dst[0], curr_dst[0])))
                covered_y_intervals[(wtype, curr_dst[0])].append((min(y_bend, curr_dst[1]), max(y_bend, curr_dst[1])))

    # Render Neutral daisy chains
    if load_n_conns:
        y_bend_n = load_n_conns[0]["src_pos"][1] - 10.0
        draw_daisy_chain(load_n_conns, nbar_x, y_bend_n, COL_NEUTRAL, "WIRES_NEUTRAL", "DASHED", 18, "N")
        
    # Render Earth daisy chains
    if load_e_conns:
        y_bend_e = load_e_conns[0]["src_pos"][1] - 22.0
        draw_daisy_chain(load_e_conns, ebar_x, y_bend_e, COL_EARTH, "WIRES_EARTH", "DASHDOT", 13, "E")

    # Draw junction dots
    for pt in junction_dots:
        msp.add_blockref("SYM_JUNCTION", insert=pt)

    # ── Fault path: ebar → rcd → maincb (dashed magenta) ────────────────────
    if show_faults and "ebar" in box_positions:
        
        rcd_key = "rcd" if "rcd" in box_positions else ("rcbo" if "rcbo" in box_positions else None)
        p_start = pin_model.get_pin_position("ebar", "E_out", box_positions["ebar"])
        rcd_pos = box_positions[rcd_key]
        maincb_pos = box_positions["maincb"]
        
        # Connect ebar.E_out -> (mid_x, rcd_y) -> (0, maincb_y) using bend logic
        mid_x = ebar_x / 2.0
        w1 = route_wire_bend(p_start, (mid_x, rcd_pos[1]))
        w2 = route_wire_bend((mid_x, rcd_pos[1]), (0.0, maincb_pos[1]))
        
        for p_s, p_e in zip(w1, w1[1:]):
            _draw_wire(msp, [p_s, p_e], color=COL_FAULT, layer="WIRES_FAULT", linetype="DASHED", lineweight=13)
        for p_s, p_e in zip(w2, w2[1:]):
            _draw_wire(msp, [p_s, p_e], color=COL_FAULT, layer="WIRES_FAULT", linetype="DASHED", lineweight=13)
            
        # Draw label at fault_x
        fl_lbl = "故障電流経路 (E)" if language == "ja" else "Fault Current Path (E)"
        _draw_label(msp, mid_x + 20.0, rcd_pos[1] - 4.0, fl_lbl, color=COL_FAULT)

    # ── Protection notes ──────────────────────────────────────────────────────
    if show_notes:
        notes = []
        if "maincb" in box_positions:
            bx, by = box_positions["maincb"]
            notes.append((bx + 8.0, by - 6.0,
                          "Overload / Short-circuit protection"))
        rcd_key = "rcd" if "rcd" in box_positions else ("rcbo" if "rcbo" in box_positions else None)
        if rcd_key:
            bx, by = box_positions[rcd_key]
            notes.append((bx + 8.0, by - 6.0,
                          "RCD: 30mA trip threshold"))
        for nx, ny, note_text in notes:
            msp.add_text(
                f"* {note_text}",
                dxfattribs={"height": FONT_H_SMALL - 0.5, "layer": "NOTES", "color": colors.YELLOW}
            ).set_placement((nx, ny), align=TextEntityAlignment.MIDDLE_LEFT)

    # ── Legend block (bottom-left) ────────────────────────────────────────────
    lx = min_x + 25.0
    ly = min_y + legend_height + 2.0
    
    # Ensure SYM_TERMINAL_ROW_2 is registered/created
    symbols.get_or_create_terminal_row(doc, n=2)

    # 1. Draw wire style legend items
    for color, lt, desc in legend_wires:
        _draw_wire(msp, [(lx, ly), (lx + 15.0, ly)],
                   color=color, layer="LEGEND", linetype=lt, lineweight=18)
        _draw_label(msp, lx + 20.0, ly, desc, color=color, layer="LEGEND")
        ly -= 12.0
        
    # 2. Draw symbol legend items
    for block_name, desc in legend_symbols:
        if block_name == "SYM_GROUND":
            # Ground symbol is placed at ly, with a short wire segment above it
            _draw_wire(msp, [(lx + 7.5, ly + 4.0), (lx + 7.5, ly)],
                       color=COL_EARTH, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(lx + 7.5, ly), dxfattribs={"layer": "LEGEND"})
        elif block_name == "SYM_JUNCTION":
            # Junction dot is drawn simply as a block reference on top of a normal white line
            _draw_wire(msp, [(lx, ly), (lx + 15.0, ly)],
                       color=colors.WHITE, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(lx + 7.5, ly), dxfattribs={"layer": "LEGEND"})
        else:
            wcolor = COL_PHASE
            if block_name == "SYM_TERMINAL_ROW_2":
                wcolor = colors.WHITE
            _draw_wire(msp, [(lx, ly), (lx + 15.0, ly)],
                       color=wcolor, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(lx + 7.5, ly), dxfattribs={"layer": "LEGEND"})
            
        _draw_label(msp, lx + 20.0, ly, desc, color=colors.WHITE, layer="LEGEND")
        ly -= 12.0

    # ── Draw NBar / EBar Labels above the figure (directly above vertical lines) ──
    if "nbar" in box_positions:
        nx = box_positions["nbar"][0]
        ny = max(nbar_y_coords) + 3.0 if nbar_y_coords else 95.0
        msp.add_text(
            "NBar",
            dxfattribs={"height": FONT_H_SMALL + 0.5, "layer": "NOTES", "color": COL_TITLE}
        ).set_placement((nx, ny), align=TextEntityAlignment.BOTTOM_CENTER)
    if "ebar" in box_positions:
        ex = box_positions["ebar"][0]
        ey = max(ebar_y_coords) + 3.0 if ebar_y_coords else 95.0
        msp.add_text(
            "EBar",
            dxfattribs={"height": FONT_H_SMALL + 0.5, "layer": "NOTES", "color": COL_TITLE}
        ).set_placement((ex, ey), align=TextEntityAlignment.BOTTOM_CENTER)

    # ── Draw Load Schedule (right side of diagram) ────────────────────────────
    load_items = []
    if outcb_ids:
        for cb_id in outcb_ids:
            match = re.search(r'\d+', cb_id)
            suffix = match.group() if match else ""
            load_id = f"load_{suffix}"
            
            # Fetch the original breaker name (with detailed specs like MCB 1 | 10A)
            lbl = comp_map.get(cb_id) or comp_map.get(load_id)
            if not lbl:
                loads_lbl = comp_map.get("loads", "LOAD")
                parts = loads_lbl.split(" | ")
                idx = int(suffix) - 1 if suffix.isdigit() else 0
                if idx < len(parts):
                    lbl = parts[idx]
                else:
                    lbl = f"Load {suffix}"
            
            # Format nicely for the table (e.g., Outgoing Breaker, MCB 1, 10A)
            lbl = lbl.replace(" | ", ", ")
            load_items.append((cb_id.upper(), lbl))
    else:
        lbl = comp_map.get("loads", "LOAD")
        load_items.append(("LOAD", lbl))

    rx = max_x - 112.0
    ry = max_y - 60.0
    
    msp.add_text(
        "LOAD SCHEDULE",
        dxfattribs={"height": FONT_H_SMALL + 0.5, "layer": "NOTES", "color": colors.WHITE}
    ).set_placement((rx, ry), align=TextEntityAlignment.MIDDLE_LEFT)
    
    msp.add_line((rx, ry - 3.0), (rx + 90.0, ry - 3.0), dxfattribs={"layer": "NOTES", "color": colors.WHITE})
    
    ry -= 10.0
    for tag, desc in load_items:
        if len(desc) > 55:
            desc = desc[:52] + "…"
        text = f"{tag}: {desc}"
        msp.add_text(
            text,
            dxfattribs={"height": FONT_H_SMALL, "layer": "NOTES", "color": colors.WHITE}
        ).set_placement((rx, ry), align=TextEntityAlignment.MIDDLE_LEFT)
        ry -= 8.0

    # ── Bounding box corner lines (defines the margin extents cleanly) ───────
    msp.add_line((min_x, min_y), (min_x + 0.1, min_y), dxfattribs={"layer": "TITLE", "color": 250})
    msp.add_line((max_x, max_y), (max_x - 0.1, max_y), dxfattribs={"layer": "TITLE", "color": 250})
    # Update title horizontal position to align with diagram-only content centroid
    try:
        diagram_layers = {"COMPONENTS", "WIRES_PHASE", "WIRES_NEUTRAL", "WIRES_EARTH", "WIRES_FAULT"}
        diagram_entities = [e for e in msp if e.dxf.layer in diagram_layers]
        if diagram_entities:
            diag_bb = ezdxf_bbox.extents(diagram_entities)
            diagram_tx = (diag_bb.extmin.x + diag_bb.extmax.x) / 2.0
            for t_ent in title_entities:
                placement = t_ent.get_placement()
                curr_y = placement[1][1]
                t_ent.set_placement((diagram_tx, curr_y), align=TextEntityAlignment.BOTTOM_CENTER)
    except Exception as te:
        print(f"Warning: could not align title to diagram midpoint: {te}")

    # Use fixed page bounds for viewport — not content-derived
    ex0, ey0 = min_x, min_y
    ex1, ey1 = max_x, max_y

    # Zoom the default viewport to the fixed page size
    doc.set_modelspace_vport(
        height=page_h,
        center=(content_cx, content_cy),
    )

    if output_path is None:
        return doc

    # ── Save with patched extents ─────────────────────────────────────────────
    stream = io.StringIO()
    doc.write(stream)
    raw = stream.getvalue().replace('\r\n', '\n')  # normalize line endings for regex

    def _patch_point(text: str, varname: str, x: float, y: float,
                     z: float = 0.0) -> str:
        """Replace the x/y/z values of a DXF header point variable."""
        # Pattern matches DXF group codes 10/20/30 that follow the var name tag
        escaped = re.escape(varname)
        pattern = (
            r'(\$' + escaped + r'\n 10\n)[^\n]+'
            r'(\n 20\n)[^\n]+(\n 30\n)[^\n]+'
        )
        return re.sub(
            pattern,
            lambda m: f'{m.group(1)}{x}{m.group(2)}{y}{m.group(3)}{z}',
            text,
        )

    raw = _patch_point(raw, 'EXTMIN', ex0, ey0)
    raw = _patch_point(raw, 'EXTMAX', ex1, ey1)
    # LIMMIN/LIMMAX are 2-D points (no group 30), so patch x/y only
    def _patch_point2d(text: str, varname: str, x: float, y: float) -> str:
        escaped = re.escape(varname)
        pattern = r'(\$' + escaped + r'\n 10\n)[^\n]+(\n 20\n)[^\n]+'
        return re.sub(
            pattern,
            lambda m: f'{m.group(1)}{x}{m.group(2)}{y}',
            text,
        )
    raw = _patch_point2d(raw, 'LIMMIN', ex0, ey0)
    raw = _patch_point2d(raw, 'LIMMAX', ex1, ey1)

    with open(output_path, 'w', encoding='utf-8') as fh:
        fh.write(raw)
    return doc

def mermaid_to_dxf(mermaid_code: str, output_path: str):
    nodes, edges = parse_mermaid_sequence(mermaid_code)
    parsed_data = normalize_for_dxf(nodes, edges)
    export_dxf(parsed_data, output_path)

def render_doc_to_svg(doc: ezdxf.document.Drawing) -> str:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing.layout import Page
    
    msp = doc.modelspace()
    backend = SVGBackend()
    ctx = RenderContext(doc)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    page = Page(width=0, height=0)
    return backend.get_string(page=page)

def render_doc_to_png(doc: ezdxf.document.Drawing, png_path: str) -> None:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib.pyplot as plt
    
    msp = doc.modelspace()
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    plt.close(fig)

def render_doc_to_pdf(doc: ezdxf.document.Drawing, pdf_path: str) -> None:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib.pyplot as plt
    
    msp = doc.modelspace()
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)