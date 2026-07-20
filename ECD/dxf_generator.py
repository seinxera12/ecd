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
        "PAGE_MARGIN":   (250,            "Continuous"),
        "COMPONENTS":    (colors.WHITE,   "Continuous"),
        "WIRES_PHASE":   (COL_PHASE,      "Continuous"),
        "WIRES_NEUTRAL": (COL_NEUTRAL,    "DASHED"),
        "WIRES_EARTH":   (COL_EARTH,      "DASHDOT"),
        "WIRES_FAULT":   (COL_FAULT,      "DASHED"),
        "WIRE_LABELS":   (colors.YELLOW,  "Continuous"),
        "TITLE":         (COL_TITLE,      "Continuous"),
        "NOTES":         (colors.WHITE,   "Continuous"),
        "LEGEND":        (colors.WHITE,   "Continuous"),
        "LOAD_SCHEDULE": (colors.WHITE,   "Continuous"),
    }
    for name, (color, lt) in layers_def.items():
        if name not in doc.layers:
            layer = doc.layers.add(name)   # create first …
            layer.dxf.color    = color     # … then set attrs explicitly
            layer.dxf.linetype = lt

def extract_circuit_info(cb_id: str, label_text: str) -> tuple[str, str]:
    """Extract clean description and rating string from circuit label text."""
    rating = ""
    desc = label_text
    
    m_rating = re.search(r'\b(\d+(?:\.\d+)?\s*(?:A|kA|kW|W|V|HP))\b', label_text, re.IGNORECASE)
    if m_rating:
        rating = m_rating.group(1).upper().replace(" ", "")
        
    parts = [p.strip() for p in label_text.split("|") if p.strip()]
    desc_parts = []
    for p in parts:
        if not re.search(r'\b\d+\s*A\b', p, re.IGNORECASE) and not re.match(r'^(MCB|CB|OUTCB)\s*\d+$', p, re.IGNORECASE):
            desc_parts.append(p)
            
    if desc_parts:
        desc = " ".join(desc_parts)
    else:
        desc = parts[0] if parts else label_text
        
    desc = re.sub(r'\s*\(\s*\d+\s*A\s*\)', '', desc, flags=re.IGNORECASE).strip()
    return desc, rating


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
    text_overrides = parsed_data.get("text_overrides", {})

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

 
    # Resolve phase mode for component placement and symbol selection
    phase_hint = parsed_data.get("phase_hint") or flags.get("phase_hint")
    phase_mode = pin_model.determine_phase_mode(voltage, phase_hint)

    box_positions = pin_model.compute_component_positions(parsed_data, phase_mode=phase_mode)
    netlist = pin_model.generate_netlist(parsed_data, box_positions)
    
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
    legend_height = n_legend_items * 16.0 + 15.0
    
    col_x = 0.0
    start_y = 100.0

    # ── Draw background rectangle ─────────────────────────────────────────────
    # (Removed to prevent visual box-like border around exported PNGs)

    # ── Title block ───────────────────────────────────────────────────────────
    if language == "ja":
        v_lbl = f"電圧: {voltage}" if voltage else "電圧: 未指定"
        p_lbl = "三相" if phase_mode == "three" else "単相"
    else:
        v_lbl = f"Voltage: {voltage}" if voltage else "Voltage: Unspecified"
        p_lbl = "Three-Phase" if phase_mode == "three" else "Single-Phase"
    voltage_line = f"{v_lbl} | {p_lbl}"

    title_items = [
        ("Generated by Electrical Diagram Generator", FONT_H_MAIN + 0.5),
        (voltage_line, FONT_H_MAIN + 0.5),
        ("ELECTRICAL DISTRIBUTION DIAGRAM", FONT_H_MAIN + 2.5),  # Main heading (increased size)
    ]
    tx = (min(x_coords) + max(x_coords)) / 2.0
    max_main_y = max(y_coords) if y_coords else 100.0
    ty = max_main_y + 12.0
    title_entities = []
    for i, (line_str, font_h) in enumerate(title_items):
        if line_str:
            label_id = f"title.line_{i}"
            display_text = text_overrides.get(label_id, line_str)
            t_ent = msp.add_text(
                display_text,
                dxfattribs={"layer": "TITLE", "height": font_h, "color": COL_TITLE},
            )
            t_ent.set_placement((tx, ty), align=TextEntityAlignment.BOTTOM_CENTER)
            t_ent.label_id = label_id
            title_entities.append(t_ent)
            ty += font_h * 1.85

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
                label = comp_map.get("loads", "負荷" if language == "ja" else "LOAD")
            elif base_type == "supply":
                label = "主電源" if language == "ja" else "Main Supply"
            elif base_type == "maincb":
                label = "主遮断器" if language == "ja" else "Main Breaker"
            elif base_type == "rcd" or base_type == "rcbo":
                label = "漏電遮断器" if language == "ja" else "RCD / RCBO"
            elif base_type == "bus":
                label = "母線 (配電)" if language == "ja" else "Busbar (Distribution)"
            else:
                label = cid.upper()
                
        # For outgoing breakers, override the diagram label to OUTCB_(number) or 分岐遮断器_(number)
        if base_type == "outcb":
            match = re.search(r'\d+', cid)
            suffix = match.group() if match else "1"
            label = f"分岐遮断器_{suffix}" if language == "ja" else f"OUTCB_{suffix}"

        # Automatic Japanese component label translation lookup
        if language == "ja":
            lbl_lower = label.lower().strip()
            jp_map = {
                "main supply": "主電源",
                "main supply (unspecified)": "主電源 (未指定)",
                "main breaker": "主遮断器",
                "main circuit breaker": "主遮断器",
                "rcd": "漏電遮断器",
                "rcbo": "漏電遮断器 (RCBO)",
                "rcd (earth fault protection)": "漏電遮断器 (地絡保護)",
                "rcd (30ma)": "漏電遮断器 (30mA)",
                "busbar": "母線 (配電)",
                "busbar (distribution)": "母線 (配電)",
            }
            for eng_k, jp_v in jp_map.items():
                if eng_k in lbl_lower:
                    label = re.sub(eng_k, jp_v, label, flags=re.IGNORECASE)
                
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
            offset = 12.0 if phase_mode == "three" else 5.0
            label_id = f"{cid}.label"
            display_text = text_overrides.get(label_id, main_lbl)
            t_ent = msp.add_text(
                display_text,
                dxfattribs={"height": FONT_H_MAIN, "layer": "COMPONENTS"}
            )
            t_ent.set_placement((bx + offset, by), align=TextEntityAlignment.MIDDLE_LEFT)
            t_ent.label_id = label_id
        elif base_type in ["loads", "nbar", "ebar"]:
            # Labels for loads are drawn in the Load Schedule on the right side of the sheet.
            # Labels for nbar/ebar are drawn at the top of the vertical rails above the figure.
            pass
        else:
            # Shift busbar label up to prevent overlapping the horizontal wire
            y_offset = 9.5 if cid == "bus" else 0.0
            if base_type == "outcb":
                x_offset = 8.0 if phase_mode == "three" else 5.0
            else:
                x_offset = 12.0 if phase_mode == "three" else 8.0
            
            label_id = f"{cid}.label"
            display_text = text_overrides.get(label_id, main_lbl)
            t_ent = msp.add_text(
                display_text,
                dxfattribs={"height": FONT_H_SMALL, "layer": "COMPONENTS"}
            )
            t_ent.set_placement((bx + x_offset, by + y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
            t_ent.label_id = label_id
            
            if sub_lbl:
                label_id_sub = f"{cid}.rating"
                display_sub = text_overrides.get(label_id_sub, sub_lbl)
                t_ent_sub = msp.add_text(
                    display_sub,
                    dxfattribs={"height": FONT_H_SMALL - 0.5, "layer": "COMPONENTS"}
                )
                t_ent_sub.set_placement((bx + x_offset, by - 3.0 + y_offset), align=TextEntityAlignment.MIDDLE_LEFT)
                t_ent_sub.label_id = label_id_sub
                      
    # Insert ground symbol below ebar
    if "ebar" in box_positions:
        ex, ey = box_positions["ebar"]
        msp.add_blockref("SYM_GROUND", insert=(ex, ey - 20.0))
        label_id = "gnd.label"
        display_text = text_overrides.get(label_id, "GND")
        t_ent = msp.add_text(
            display_text,
            dxfattribs={"height": FONT_H_SMALL, "layer": "COMPONENTS"}
        )
        t_ent.set_placement((ex - 6.0, ey - 20.0), align=TextEntityAlignment.MIDDLE_RIGHT)
        t_ent.label_id = label_id

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

    # Draw NBar / EBar Labels above the vertical rails
    if "nbar" in box_positions:
        nx = nbar_x
        ny = max(nbar_y_coords) + 3.0 if nbar_y_coords else box_positions["nbar"][1] + 10.0
        label_id = "nbar.title"
        default_n_text = "NBar"
        display_text = text_overrides.get(label_id, default_n_text)
        t_ent = msp.add_text(
            display_text,
            dxfattribs={"height": FONT_H_SMALL + 0.5, "layer": "NOTES", "color": COL_TITLE}
        )
        t_ent.set_placement((nx, ny), align=TextEntityAlignment.BOTTOM_CENTER)
        t_ent.label_id = label_id

    if "ebar" in box_positions:
        ex = ebar_x
        ey = max(ebar_y_coords) + 3.0 if ebar_y_coords else box_positions["ebar"][1] + 10.0
        label_id = "ebar.title"
        default_e_text = "EBar"
        display_text = text_overrides.get(label_id, default_e_text)
        t_ent = msp.add_text(
            display_text,
            dxfattribs={"height": FONT_H_SMALL + 0.5, "layer": "NOTES", "color": COL_TITLE}
        )
        t_ent.set_placement((ex, ey), align=TextEntityAlignment.BOTTOM_CENTER)
        t_ent.label_id = label_id

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

    # Compile legend items early to calculate required height
    if phase_mode == "three":
        legend_wires = [
            (COL_L1, "Continuous", "L1相" if language == "ja" else "Phase L1"),
            (COL_L2, "Continuous", "L2相" if language == "ja" else "Phase L2"),
            (COL_L3, "Continuous", "L3相" if language == "ja" else "Phase L3"),
        ]
    else:
        legend_wires = [
            (COL_PHASE, "Continuous", "電圧線 (L)" if language == "ja" else "Phase (L)"),
        ]

    if show_neutral:
        legend_wires.append((COL_NEUTRAL, "DASHED",    "中性線 (N)" if language == "ja" else "Neutral (N)"))
    if show_earth:
        legend_wires.append((COL_EARTH,   "DASHDOT",   "接地線 / PE (E)" if language == "ja" else "Earth / PE (E)"))
    if show_faults:
        legend_wires.append((COL_FAULT,   "DASHED",    "事故電流経路" if language == "ja" else "Fault Current Path"))

    if phase_mode == "three":
        legend_symbols = []
        if "supply" in comp_map:
            legend_symbols.append(("SYM_SUPPLY_3PH",  "三相電源" if language == "ja" else "Three-Phase Supply"))
        if "maincb" in comp_map:
            legend_symbols.append(("SYM_BREAKER_3PH", "主遮断器 (maincb)" if language == "ja" else "Main Breaker (maincb)"))
        if outcb_ids:
            legend_symbols.append(("SYM_MCB_3PH",     "分岐遮断器 (outcb)" if language == "ja" else "Outgoing MCB (outcb)"))
        if show_rcd:
            legend_symbols.append(("SYM_RCD_3PH", "漏電遮断器 (RCD)" if language == "ja" else "RCD / RCBO"))
        if any(pin_model.get_base_type(cid) == "loads" for cid in comp_map):
            legend_symbols.append(("SYM_MOTOR_3PH", "三相モーター負荷" if language == "ja" else "Motor Load"))
    else:
        legend_symbols = []
        if "maincb" in comp_map:
            legend_symbols.append(("SYM_BREAKER", "主遮断器 (maincb)" if language == "ja" else "Main Breaker (maincb)"))
        if outcb_ids:
            legend_symbols.append(("SYM_MCB",     "分岐遮断器 (outcb)" if language == "ja" else "Outgoing MCB (outcb)"))
        if show_rcd:
            legend_symbols.append(("SYM_RCD", "漏電遮断器 (RCD)" if language == "ja" else "RCD / RCBO"))
        if any(pin_model.get_base_type(cid) == "loads" for cid in comp_map):
            legend_symbols.append(("SYM_LAMP", "負荷 / 照明" if language == "ja" else "Load / Lamp"))

    if show_earth and "ebar" in comp_map:
        legend_symbols.append(("SYM_GROUND", "接地端子" if language == "ja" else "Earth Terminus"))
        
    has_terminal = "nbar" in comp_map or "ebar" in comp_map or any("terminal" in cid for cid in comp_map)
    if has_terminal:
        legend_symbols.append(("SYM_TERMINAL_ROW_2", "端子台" if language == "ja" else "Terminal Block"))
        
    has_junctions = ("bus" in comp_map and len(outcb_ids) > 0) or (show_neutral and "nbar" in comp_map) or (show_earth and "ebar" in comp_map)
    if has_junctions:
        legend_symbols.append(("SYM_JUNCTION", "接続点" if language == "ja" else "Junction Dot"))



    # ── Legend & Load Schedule positioning (centered below main diagram) ──────
    min_main_y = min(y_coords) if y_coords else 0.0
    main_diagram_bottom_y = min_main_y - 25.0
    bottom_boxes_top_y = min(main_diagram_bottom_y - 12.0, -70.0)

    leg_w = 175.0
    sched_w = 175.0
    box_gap = 10.0
    total_bottom_w = leg_w + sched_w + box_gap
    
    diagram_center_x = (min(x_coords) + max(x_coords)) / 2.0 if x_coords else content_cx
    bottom_start_x = diagram_center_x - (total_bottom_w / 2.0)

    # ── Legend block (bottom-left below main diagram) ─────────────────────────
    leg_h = 95.0
    leg_x0 = bottom_start_x
    leg_x1 = leg_x0 + leg_w
    leg_y1 = bottom_boxes_top_y
    leg_y0 = leg_y1 - leg_h
    
    msp.add_line((leg_x0, leg_y0), (leg_x1, leg_y0), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    msp.add_line((leg_x1, leg_y0), (leg_x1, leg_y1), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    msp.add_line((leg_x1, leg_y1), (leg_x0, leg_y1), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    msp.add_line((leg_x0, leg_y1), (leg_x0, leg_y0), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    
    title_text = "凡例" if language == "ja" else "LEGEND"
    t_ent = msp.add_text(
        text_overrides.get("legend.title", title_text),
        dxfattribs={"height": FONT_H_SMALL + 0.8, "layer": "LEGEND", "color": COL_TITLE}
    )
    t_ent.set_placement(((leg_x0 + leg_x1) / 2.0, leg_y1 - 5.0), align=TextEntityAlignment.MIDDLE_CENTER)
    t_ent.label_id = "legend.title"
    
    msp.add_line((leg_x0, leg_y1 - 9.0), (leg_x1, leg_y1 - 9.0), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    
    col_mid_x = leg_x0 + (leg_w / 2.0)
    msp.add_line((col_mid_x, leg_y1 - 9.0), (col_mid_x, leg_y0), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    
    wires_title = "配線" if language == "ja" else "WIRES"
    t_ent = msp.add_text(
        wires_title,
        dxfattribs={"height": FONT_H_SMALL, "layer": "LEGEND", "color": colors.WHITE}
    )
    t_ent.set_placement(((leg_x0 + col_mid_x) / 2.0, leg_y1 - 13.5), align=TextEntityAlignment.MIDDLE_CENTER)
    
    symbols_title = "シンボル" if language == "ja" else "SYMBOLS"
    t_ent = msp.add_text(
        symbols_title,
        dxfattribs={"height": FONT_H_SMALL, "layer": "LEGEND", "color": colors.WHITE}
    )
    t_ent.set_placement(((col_mid_x + leg_x1) / 2.0, leg_y1 - 13.5), align=TextEntityAlignment.MIDDLE_CENTER)
    
    msp.add_line((leg_x0, leg_y1 - 17.0), (leg_x1, leg_y1 - 17.0), dxfattribs={"layer": "LEGEND", "color": colors.WHITE})
    
    symbols.get_or_create_terminal_row(doc, n=2)
    
    ly_wire = leg_y1 - 23.0
    for color, lt, desc in legend_wires:
        _draw_wire(msp, [(leg_x0 + 6.0, ly_wire), (leg_x0 + 22.0, ly_wire)],
                   color=color, layer="LEGEND", linetype=lt, lineweight=18)
        _draw_label(msp, leg_x0 + 26.0, ly_wire, desc, color=color, layer="LEGEND")
        ly_wire -= 8.5

    ly_sym = leg_y1 - 23.0
    for block_name, desc in legend_symbols:
        sx = col_mid_x + 8.0
        if block_name == "SYM_GROUND":
            _draw_wire(msp, [(sx + 5.0, ly_sym + 3.0), (sx + 5.0, ly_sym)],
                       color=COL_EARTH, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(sx + 5.0, ly_sym), dxfattribs={"layer": "LEGEND"})
        elif block_name == "SYM_JUNCTION":
            _draw_wire(msp, [(sx, ly_sym), (sx + 10.0, ly_sym)],
                       color=colors.WHITE, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(sx + 5.0, ly_sym), dxfattribs={"layer": "LEGEND"})
        else:
            wcolor = COL_PHASE if block_name != "SYM_TERMINAL_ROW_2" else colors.WHITE
            _draw_wire(msp, [(sx, ly_sym), (sx + 10.0, ly_sym)],
                       color=wcolor, layer="LEGEND", linetype="CONTINUOUS", lineweight=13)
            msp.add_blockref(block_name, insert=(sx + 5.0, ly_sym), dxfattribs={"layer": "LEGEND"})
            
        _draw_label(msp, sx + 15.0, ly_sym, desc, color=colors.WHITE, layer="LEGEND")
        ly_sym -= 8.5

    # ── Load Schedule Table (bottom-right below main diagram) ─────────────────
    sched_h = 95.0
    sched_x0 = leg_x1 + box_gap
    sched_x1 = sched_x0 + sched_w
    sched_y1 = bottom_boxes_top_y
    sched_y0 = sched_y1 - sched_h
    
    msp.add_line((sched_x0, sched_y0), (sched_x1, sched_y0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    msp.add_line((sched_x1, sched_y0), (sched_x1, sched_y1), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    msp.add_line((sched_x1, sched_y1), (sched_x0, sched_y1), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    msp.add_line((sched_x0, sched_y1), (sched_x0, sched_y0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    
    title_text = "負荷表" if language == "ja" else "LOAD SCHEDULE"
    t_ent = msp.add_text(
        text_overrides.get("schedule.title", title_text),
        dxfattribs={"height": FONT_H_SMALL + 0.8, "layer": "LOAD_SCHEDULE", "color": COL_TITLE}
    )
    t_ent.set_placement(((sched_x0 + sched_x1) / 2.0, sched_y1 - 5.0), align=TextEntityAlignment.MIDDLE_CENTER)
    t_ent.label_id = "schedule.title"
    
    msp.add_line((sched_x0, sched_y1 - 9.0), (sched_x1, sched_y1 - 9.0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    
    col_outcb_w = 40.0
    col_desc_w = 105.0
    col_rating_w = 40.0
    
    col_x1 = sched_x0 + col_outcb_w
    col_x2 = col_x1 + col_desc_w
    
    msp.add_line((col_x1, sched_y1 - 9.0), (col_x1, sched_y0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    msp.add_line((col_x2, sched_y1 - 9.0), (col_x2, sched_y0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    
    h_outcb = "回路番号" if language == "ja" else "OUTCB"
    h_desc = "説明" if language == "ja" else "DESCRIPTION"
    h_rating = "定格" if language == "ja" else "RATING"
    
    t_ent = msp.add_text(h_outcb, dxfattribs={"height": FONT_H_SMALL, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    t_ent.set_placement(((sched_x0 + col_x1) / 2.0, sched_y1 - 13.5), align=TextEntityAlignment.MIDDLE_CENTER)
    
    t_ent = msp.add_text(h_desc, dxfattribs={"height": FONT_H_SMALL, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    t_ent.set_placement((col_x1 + 4.0, sched_y1 - 13.5), align=TextEntityAlignment.MIDDLE_LEFT)
    
    t_ent = msp.add_text(h_rating, dxfattribs={"height": FONT_H_SMALL, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    t_ent.set_placement(((col_x2 + sched_x1) / 2.0, sched_y1 - 13.5), align=TextEntityAlignment.MIDDLE_CENTER)
    
    msp.add_line((sched_x0, sched_y1 - 17.0), (sched_x1, sched_y1 - 17.0), dxfattribs={"layer": "LOAD_SCHEDULE", "color": colors.WHITE})
    
    load_items = []
    if outcb_ids:
        for cb_id in outcb_ids:
            match = re.search(r'\d+', cb_id)
            suffix = match.group() if match else ""
            load_id = f"load_{suffix}"
            
            lbl = comp_map.get(cb_id) or comp_map.get(load_id)
            if not lbl:
                loads_lbl = comp_map.get("loads", "負荷" if language == "ja" else "LOAD")
                parts = loads_lbl.split(" | ")
                idx = int(suffix) - 1 if suffix.isdigit() else 0
                if idx < len(parts):
                    lbl = parts[idx]
                else:
                    lbl = f"回路 {suffix}" if language == "ja" else f"Load {suffix}"
            
            desc_text, rating_text = extract_circuit_info(cb_id, lbl)
            if language == "ja":
                if desc_text.lower().startswith("load"):
                    desc_text = re.sub(r'load', '回路', desc_text, flags=re.IGNORECASE)
                tag_str = f"分岐遮断器_{suffix}"
            else:
                tag_str = cb_id.upper()
                
            load_items.append((cb_id, tag_str, desc_text, rating_text))
    else:
        lbl = comp_map.get("loads", "負荷" if language == "ja" else "LOAD")
        desc_text, rating_text = extract_circuit_info("loads", lbl)
        tag_str = "負荷" if language == "ja" else "LOAD"
        load_items.append(("loads", tag_str, desc_text, rating_text))

    num_rows = max(1, len(load_items))
    avail_h = 71.0
    row_h = min(7.5, avail_h / float(num_rows))
    font_h = FONT_H_SMALL if num_rows <= 6 else max(2.2, min(FONT_H_SMALL, row_h * 0.65))

    curr_row_y = sched_y1 - 17.0
    for i, (cb_id, tag, desc, rating) in enumerate(load_items):
        cell_y = curr_row_y - (row_h / 2.0)
        
        # 1. OUTCB cell
        label_id_tag = f"schedule.tag_{cb_id.lower()}"
        display_tag = text_overrides.get(label_id_tag, tag)
        t_ent = msp.add_text(display_tag, dxfattribs={"height": font_h, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
        t_ent.set_placement(((sched_x0 + col_x1) / 2.0, cell_y), align=TextEntityAlignment.MIDDLE_CENTER)
        t_ent.label_id = label_id_tag
        
        # 2. DESCRIPTION cell
        if len(desc) > 38:
            desc = desc[:35] + "…"
        label_id_desc = f"schedule.item_{cb_id.lower()}"
        display_desc = text_overrides.get(label_id_desc, desc)
        t_ent = msp.add_text(display_desc, dxfattribs={"height": font_h, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
        t_ent.set_placement((col_x1 + 4.0, cell_y), align=TextEntityAlignment.MIDDLE_LEFT)
        t_ent.label_id = label_id_desc
        
        # 3. RATING cell
        label_id_rating = f"schedule.rating_{cb_id.lower()}"
        display_rating = text_overrides.get(label_id_rating, rating)
        t_ent = msp.add_text(display_rating, dxfattribs={"height": font_h, "layer": "LOAD_SCHEDULE", "color": colors.WHITE})
        t_ent.set_placement(((col_x2 + sched_x1) / 2.0, cell_y), align=TextEntityAlignment.MIDDLE_CENTER)
        t_ent.label_id = label_id_rating
        
        curr_row_y -= row_h

    # ── Bounding box corner lines (defines the margin extents cleanly around content) ───────
    final_min_y = min(leg_y0, sched_y0) - 15.0
    final_max_y = max_main_y + 35.0  # Includes Title Block top line + 15mm margin

    msp.add_line((min_x, final_min_y), (min_x + 0.1, final_min_y), dxfattribs={"layer": "PAGE_MARGIN", "color": 250})
    msp.add_line((max_x, final_max_y), (max_x - 0.1, final_max_y), dxfattribs={"layer": "PAGE_MARGIN", "color": 250})
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

    # Use fixed page bounds for viewport — encompass all content cleanly
    viewport_h = final_max_y - final_min_y
    viewport_cy = (final_max_y + final_min_y) / 2.0

    # Zoom the default viewport to the full diagram content size
    doc.set_modelspace_vport(
        height=viewport_h,
        center=(content_cx, viewport_cy),
    )

    # ── Apply layout_overrides (group transformations) ────────────────────────
    layout_overrides = parsed_data.get("layout_overrides", {})
    if layout_overrides:
        try:
            from ezdxf.math import Matrix44
            groups = ["main_diagram", "title_block", "legend", "load_schedule"]
            for gname in groups:
                override = layout_overrides.get(gname)
                if override:
                    pos = override.get("position")  # [pos_x, pos_y]
                    scale = override.get("scale", 1.0)
                    px = pos[0] if pos else 0.0
                    py = pos[1] if pos else 0.0
                    if px != 0.0 or py != 0.0 or scale != 1.0:
                        m = Matrix44.chain(
                            Matrix44.scale(scale, scale, 1.0),
                            Matrix44.translate(px, -py, 0.0)
                        )
                        group_entities = get_group_entities(doc, gname)
                        for ent in group_entities:
                            try:
                                ent.transform(m)
                            except Exception as te:
                                print(f"Warning: could not transform entity in group {gname}: {te}")
        except Exception as le:
            print(f"Warning: failed to apply layout_overrides to DXF: {le}")

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

def _get_cjk_font_face():
    """Find system Japanese CJK font face for ezdxf rendering context."""
    import os
    from pathlib import Path
    from ezdxf.fonts import font_manager
    cjk_candidates = [
        "msgothic.ttc", "yugothm.ttc", "meiryo.ttc", "YuGothM.ttc",
        "msmincho.ttc", "NotoSansCJK-Regular.ttc", "TakaoPGothic.ttf"
    ]
    for f in cjk_candidates:
        path = os.path.join("C:/Windows/Fonts", f)
        if os.path.exists(path):
            try:
                return font_manager.get_ttf_font_face(Path(path))
            except Exception:
                pass
    return None

def render_doc_to_svg(doc: ezdxf.document.Drawing) -> str:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing.layout import Page
    
    msp = doc.modelspace()
    backend = SVGBackend()
    ctx = RenderContext(doc)
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
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
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
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
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    fig.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close(fig)

from ezdxf.addons.drawing.svg import SVGBackend, SVGRenderBackend

class TransparentSVGRenderBackend(SVGRenderBackend):
    def __init__(self, page, settings):
        super().__init__(page, settings)
        self.background.set("fill", "none")
        self.background.set("fill-opacity", "0")

    def set_background(self, color):
        pass

class TransparentSVGBackend(SVGBackend):
    def make_backend(self, page, settings):
        return TransparentSVGRenderBackend(page, settings)

def render_entities_to_svg(doc: ezdxf.document.Drawing, entities: list) -> str:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.layout import Page
    from ezdxf.bbox import extents
    from ezdxf.math import BoundingBox2d
    
    if not entities:
        return ""
    backend = TransparentSVGBackend()
    ctx = RenderContext(doc)
    frontend = Frontend(ctx, backend)
    frontend.draw_entities(entities)
    
    try:
        bb = extents(entities)
        x_min, y_min = bb.extmin.x, bb.extmin.y
        x_max, y_max = bb.extmax.x, bb.extmax.y
        width = x_max - x_min
        height = y_max - y_min
        if width > 0 and height > 0:
            page = Page(width=width, height=height)
            bbox2d = BoundingBox2d([(x_min, y_min), (x_max, y_max)])
            return backend.get_string(page=page, render_box=bbox2d)
    except Exception as e:
        print("Failed to render with custom page box:", e)
        
    page = Page(width=0, height=0)
    return backend.get_string(page=page)

def get_group_entities(doc: ezdxf.document.Drawing, group_name: str) -> list:
    """Classify modelspace entities into four groups: title_block, legend, load_schedule, main_diagram."""
    msp = doc.modelspace()
    entities = []
    for entity in msp:
        layer = entity.dxf.layer
        if layer == "PAGE_MARGIN":
            continue
            
        ent_group = "main_diagram"
        if layer == "TITLE":
            ent_group = "title_block"
        elif layer == "LEGEND":
            ent_group = "legend"
        elif layer == "LOAD_SCHEDULE":
            ent_group = "load_schedule"
        else:
            ent_group = "main_diagram"
            
        if ent_group == group_name:
            entities.append(entity)
            
    return entities

def get_group_graphics_and_text(doc: ezdxf.document.Drawing, group_name: str) -> tuple[list, list]:
    entities = get_group_entities(doc, group_name)
    graphics = []
    text_entities = []
    for ent in entities:
        if ent.dxftype() in ("TEXT", "MTEXT"):
            text_entities.append(ent)
        else:
            graphics.append(ent)
    return graphics, text_entities