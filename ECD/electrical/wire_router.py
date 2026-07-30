"""
ECD/electrical/wire_router.py — Canonical Shared Wire Routing Engine.

Provides unified Manhattan right-angle bend generation, daisy-chain wire routing,
interval subtraction, and junction dot positioning. Pure geometry module with
no Qt, QGraphics, or ezdxf drawing dependencies.
"""
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Any, Optional

# Wire colors matching canonical DXF layer definitions (numeric ACI values)
COL_PHASE   = 1    # Red / L1 (DXF ACI 1)
COL_L1      = 1    # Red / L1 (DXF ACI 1)
COL_L2      = 2    # Yellow / L2 (DXF ACI 2)
COL_L3      = 30   # Orange / L3 (DXF ACI 30)
COL_NEUTRAL = 3    # Green / Neutral (DXF ACI 3)
COL_EARTH   = 5    # Darker Blue / Earth (DXF ACI 5)


def subtract_intervals(val_min: float, val_max: float, covered: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
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


def route_wire_bend(p1: Tuple[float, float], p2: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Generate canonical Manhattan right-angle bend points between p1 and p2."""
    x1, y1 = p1
    x2, y2 = p2

    if abs(x1 - x2) < 0.1:
        return [(x1, y1), (x1, y2)]
    if abs(y1 - y2) < 0.1:
        return [(x1, y1), (x2, y1)]

    # Manhattan bend: vertical first, then horizontal
    return [(x1, y1), (x1, y2), (x2, y2)]


def build_daisy_chain_routes(
    conns: List[Dict[str, Any]],
    rail_x: float,
    y_bend: float,
    color: int,
    layer: str,
    linetype: str,
    lineweight: int,
    wtype: str
) -> Tuple[List[Dict[str, Any]], List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Build canonical sequential daisy-chain routes for Neutral or Earth load terminals.
    Returns (daisy_routes, covered_x_list, covered_y_list).
    """
    if not conns:
        return [], [], []

    # Split into left and right groups relative to rail_x
    left_conns = [c for c in conns if c["dst_pos"][0] < rail_x]
    right_conns = [c for c in conns if c["dst_pos"][0] >= rail_x]

    # Sort left group descending (closest to rail_x first)
    left_conns.sort(key=lambda c: c["dst_pos"][0], reverse=True)
    # Sort right group ascending (closest to rail_x first)
    right_conns.sort(key=lambda c: c["dst_pos"][0])

    routes = []
    cov_x = []
    cov_y = []

    # Left group daisy chain
    if left_conns:
        first = left_conns[0]
        src = first["src_pos"]
        dst = first["dst_pos"]
        pts = [src, (src[0], y_bend), (dst[0], y_bend), dst]
        routes.append({
            "wire_type": wtype,
            "pts": pts,
            "color": color,
            "layer": layer,
            "linetype": linetype,
            "lineweight": lineweight,
            "src_cid": first["src_component"],
            "dst_cid": first["dst_component"]
        })
        cov_x.append((min(src[0], dst[0]), max(src[0], dst[0])))
        cov_y.append((min(y_bend, dst[1]), max(y_bend, dst[1])))

        for i in range(1, len(left_conns)):
            prev_dst = left_conns[i - 1]["dst_pos"]
            curr_dst = left_conns[i]["dst_pos"]
            pts = [prev_dst, (prev_dst[0], y_bend), (curr_dst[0], y_bend), curr_dst]
            routes.append({
                "wire_type": wtype,
                "pts": pts,
                "color": color,
                "layer": layer,
                "linetype": linetype,
                "lineweight": lineweight,
                "src_cid": left_conns[i - 1]["dst_component"],
                "dst_cid": left_conns[i]["dst_component"]
            })
            cov_x.append((min(prev_dst[0], curr_dst[0]), max(prev_dst[0], curr_dst[0])))
            cov_y.append((min(y_bend, curr_dst[1]), max(y_bend, curr_dst[1])))

    # Right group daisy chain
    if right_conns:
        first = right_conns[0]
        src = first["src_pos"]
        dst = first["dst_pos"]
        pts = [src, (src[0], y_bend), (dst[0], y_bend), dst]
        routes.append({
            "wire_type": wtype,
            "pts": pts,
            "color": color,
            "layer": layer,
            "linetype": linetype,
            "lineweight": lineweight,
            "src_cid": first["src_component"],
            "dst_cid": first["dst_component"]
        })
        cov_x.append((min(src[0], dst[0]), max(src[0], dst[0])))
        cov_y.append((min(y_bend, dst[1]), max(y_bend, dst[1])))

        for i in range(1, len(right_conns)):
            prev_dst = right_conns[i - 1]["dst_pos"]
            curr_dst = right_conns[i]["dst_pos"]
            pts = [prev_dst, (prev_dst[0], y_bend), (curr_dst[0], y_bend), curr_dst]
            routes.append({
                "wire_type": wtype,
                "pts": pts,
                "color": color,
                "layer": layer,
                "linetype": linetype,
                "lineweight": lineweight,
                "src_cid": right_conns[i - 1]["dst_component"],
                "dst_cid": right_conns[i]["dst_component"]
            })
            cov_x.append((min(prev_dst[0], curr_dst[0]), max(prev_dst[0], curr_dst[0])))
            cov_y.append((min(y_bend, curr_dst[1]), max(y_bend, curr_dst[1])))

    return routes, cov_x, cov_y


def calculate_canonical_wire_graph(netlist: Dict[str, Any], box_positions: Dict[str, Tuple[float, float]], phase_mode: str = "single") -> Dict[str, Any]:
    """
    Calculate full canonical wire geometry, busbar rails, daisy chains,
    uncovered segments, and junction dots for a given netlist and component layout.

    Returns dict with keys:
      - 'rail_wires': List of persistent busbar/N-rail/E-rail wire entries
      - 'routed_wires': List of routed connection wire entries with uncovered points
      - 'daisy_chains': List of daisy-chained N & E wire entries to loads
      - 'junction_dots': Set of (x, y) tap coordinates for SYM_JUNCTION blocks
    """
    if not netlist or not netlist.get("connections"):
        return {
            "rail_wires": [],
            "routed_wires": [],
            "daisy_chains": [],
            "junction_dots": set()
        }

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

    covered_x_intervals = defaultdict(list)
    covered_y_intervals = defaultdict(list)
    rail_wires = []

    # 1. Persistent L-rail busbar
    if "bus" in box_positions:
        bus_y = box_positions["bus"][1]
        x_min, x_max = min(bus_x_coords), max(bus_x_coords)
        if phase_mode == "three":
            spacing = 3.0
            for offset_y, wt, col in [
                (spacing, "L1", COL_L1),
                (0.0, "L2", COL_L2),
                (-spacing, "L3", COL_L3)
            ]:
                pts = [(x_min, bus_y + offset_y), (x_max, bus_y + offset_y)]
                rail_wires.append({
                    "wire_type": wt,
                    "pts": pts,
                    "color": col,
                    "layer": "WIRES_PHASE",
                    "linetype": "CONTINUOUS",
                    "lineweight": 25
                })
                covered_x_intervals[(wt, bus_y + offset_y)].append((x_min, x_max))
        else:
            pts = [(x_min, bus_y), (x_max, bus_y)]
            rail_wires.append({
                "wire_type": "L",
                "pts": pts,
                "color": COL_PHASE,
                "layer": "WIRES_PHASE",
                "linetype": "CONTINUOUS",
                "lineweight": 25
            })
            covered_x_intervals[("L", bus_y)].append((x_min, x_max))

    # 2. Persistent N-rail
    if "nbar" in box_positions and nbar_y_coords:
        y_min, y_max = min(nbar_y_coords), max(nbar_y_coords)
        pts = [(nbar_x, y_min), (nbar_x, y_max)]
        rail_wires.append({
            "wire_type": "N",
            "pts": pts,
            "color": COL_NEUTRAL,
            "layer": "WIRES_NEUTRAL",
            "linetype": "DASHED",
            "lineweight": 18
        })
        covered_y_intervals[("N", nbar_x)].append((y_min, y_max))

    # 3. Persistent E-rail
    if "ebar" in box_positions and ebar_y_coords:
        y_min, y_max = min(ebar_y_coords), max(ebar_y_coords)
        pts = [(ebar_x, y_min), (ebar_x, y_max)]
        rail_wires.append({
            "wire_type": "E",
            "pts": pts,
            "color": COL_EARTH,
            "layer": "WIRES_EARTH",
            "linetype": "DASHDOT",
            "lineweight": 13
        })
        covered_y_intervals[("E", ebar_x)].append((y_min, y_max))

    # Compile junction dots set
    junction_dots = set()
    routed_wires = []

    # 4. Draw routed connections
    for conn in netlist["connections"]:
        src_pos = conn["src_pos"]
        dst_pos = conn["dst_pos"]
        wtype = conn["wire_type"]

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

        pts = route_wire_bend(src_pos, dst_pos)
        uncovered_segments = []

        for p_s, p_e in zip(pts, pts[1:]):
            is_horizontal = abs(p_s[1] - p_e[1]) < 0.1
            is_vertical = abs(p_s[0] - p_e[0]) < 0.1

            if is_horizontal:
                y_val = p_s[1]
                x_min, x_max = min(p_s[0], p_e[0]), max(p_s[0], p_e[0])
                parts = subtract_intervals(x_min, x_max, covered_x_intervals[(wtype, y_val)])
                for ux_min, ux_max in parts:
                    uncovered_segments.append([(ux_min, y_val), (ux_max, y_val)])
                    covered_x_intervals[(wtype, y_val)].append((ux_min, ux_max))
            elif is_vertical:
                x_val = p_s[0]
                y_min, y_max = min(p_s[1], p_e[1]), max(p_s[1], p_e[1])
                parts = subtract_intervals(y_min, y_max, covered_y_intervals[(wtype, x_val)])
                for uy_min, uy_max in parts:
                    uncovered_segments.append([(x_val, uy_min), (x_val, uy_max)])
                    covered_y_intervals[(wtype, x_val)].append((uy_min, uy_max))

        color = COL_PHASE
        layer = "WIRES_PHASE"
        linetype = "CONTINUOUS"
        lineweight = 25
        if wtype == "L1":
            color = COL_L1
        elif wtype == "L2":
            color = COL_L2
        elif wtype == "L3":
            color = COL_L3
        elif wtype == "N":
            color = COL_NEUTRAL
            layer = "WIRES_NEUTRAL"
            linetype = "DASHED"
            lineweight = 18
        elif wtype == "E":
            color = COL_EARTH
            layer = "WIRES_EARTH"
            linetype = "DASHDOT"
            lineweight = 13

        routed_wires.append({
            "connection": conn,
            "pts": pts,
            "uncovered_segments": uncovered_segments,
            "color": color,
            "layer": layer,
            "linetype": linetype,
            "lineweight": lineweight
        })

    # Daisy-chained Neutral and Earth wires to loads
    load_n_conns = []
    load_e_conns = []
    for conn in netlist["connections"]:
        dst = conn["dst_component"]
        wtype = conn["wire_type"]
        if dst.startswith("load") and wtype == "N":
            load_n_conns.append(conn)
        elif dst.startswith("load") and wtype == "E":
            load_e_conns.append(conn)

    daisy_chains = []
    if load_n_conns:
        y_bend_n = load_n_conns[0]["src_pos"][1] - 10.0
        n_routes, _, _ = build_daisy_chain_routes(load_n_conns, nbar_x, y_bend_n, COL_NEUTRAL, "WIRES_NEUTRAL", "DASHED", 18, "N")
        daisy_chains.extend(n_routes)

    if load_e_conns:
        y_bend_e = load_e_conns[0]["src_pos"][1] - 22.0
        e_routes, _, _ = build_daisy_chain_routes(load_e_conns, ebar_x, y_bend_e, COL_EARTH, "WIRES_EARTH", "DASHDOT", 13, "E")
        daisy_chains.extend(e_routes)

    return {
        "rail_wires": rail_wires,
        "routed_wires": routed_wires,
        "daisy_chains": daisy_chains,
        "junction_dots": junction_dots
    }
