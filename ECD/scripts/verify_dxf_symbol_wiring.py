"""
verify_dxf_symbol_wiring.py
===========================

Structural self-test for Phase 3B (rails, junction dots, Manhattan bends).
Runs the real export_dxf() against 3 required test cases plus the 4th (with fault paths),
then reads the DXF back and checks it against the real netlist and structural rules.

Run this from your project root (D:\\ecd, the parent of ECD\\), using:
    python -m ECD.scripts.verify_dxf_symbol_wiring
"""

from __future__ import annotations
import sys
import os
import ezdxf

from ECD import dxf_generator, pin_model

TEST_CASES = {
    "minimal": {
        "components": [("supply", "Supply"), ("maincb", "Main CB"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False},
    },
    "full": {
        "components": [
            ("supply", "Supply"), ("maincb", "Main CB"), ("rcd", "RCD"),
            ("bus", "Bus"), ("nbar", "N-Bar"), ("ebar", "E-Bar"),
            ("outcb_1", "CB1"), ("outcb_2", "CB2"), ("outcb_3", "CB3"),
            ("loads", "Loads"),
        ],
        "flags": {"show_neutral": True, "show_earth": True},
    },
    "multi_circuit": {
        "components": [
            ("supply", "Supply"), ("maincb", "Main CB"), ("bus", "Bus"),
            ("outcb_1", "CB1"), ("outcb_2", "CB2"), ("outcb_3", "CB3"),
            ("outcb_4", "CB4"), ("outcb_5", "CB5"), ("outcb_6", "CB6"),
            ("loads", "Loads"),
        ],
        "flags": {"show_neutral": False, "show_earth": False},
    },
    "fault_path": {
        "components": [
            ("supply", "Supply"), ("maincb", "Main CB"), ("rcd", "RCD"),
            ("bus", "Bus"), ("nbar", "N-Bar"), ("ebar", "E-Bar"),
            ("outcb_1", "CB1"), ("loads", "Loads"),
        ],
        "flags": {"show_neutral": True, "show_earth": True, "show_fault_paths": True},
    },
    "three_phase_full": {
        "components": [
            ("supply", "Three-Phase Supply"), ("maincb", "Main CB"), ("rcd", "RCD"),
            ("bus", "Bus"), ("nbar", "N-Bar"), ("ebar", "E-Bar"),
            ("outcb_1", "CB1"), ("outcb_2", "CB2"), ("outcb_3", "CB3"),
            ("loads", "Loads"),
        ],
        "flags": {"show_neutral": True, "show_earth": True},
        "voltage": "400V AC",
        "phase_hint": "three-phase"
    }
}


def check_case(name, parsed_data, tol=0.05):
    print(f"\n{'='*70}\nCASE: {name}\n{'='*70}")
    dxf_path = os.path.join("renders", f"test_{name}.dxf")
    os.makedirs("renders", exist_ok=True)

    parsed_data["connections"] = dxf_generator.ensure_connections(parsed_data)
    dxf_generator.export_dxf(parsed_data, dxf_path)

    # Recompute positions and netlist
    positions = pin_model.compute_component_positions(parsed_data)
    netlist = pin_model.generate_netlist(parsed_data, positions)

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    problems = []

    # 1. No leftover _draw_box rectangles on COMPONENTS layer.
    box_rects = [
        e for e in msp
        if e.dxftype() == "LWPOLYLINE"
        and e.dxf.layer == "COMPONENTS"
        and e.closed
        and len(e) == 4
    ]
    if box_rects:
        problems.append(f"Found {len(box_rects)} leftover box-style rectangles on COMPONENTS layer")

    # 2. Every symbol INSERT uses a real SYM_ block
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    non_symbol = [e for e in inserts if not e.dxf.name.startswith("SYM_")]
    if non_symbol:
        problems.append(f"{len(non_symbol)} INSERT(s) using non-SYM_ blocks: "
                         f"{[e.dxf.name for e in non_symbol]}")
    print(f"  Symbol inserts: {len(inserts)} ({[e.dxf.name for e in inserts]})")

    # From here on, "real diagram" checks should ignore anything on the
    # LEGEND/TITLE layers -- those are illustrative/static content, not
    # part of the actual electrical diagram, and must never be checked
    # as if they were real netlist geometry (or "fixed" to satisfy these
    # checks -- if legend content can't pass a real-diagram check, that's
    # a sign it's on the wrong layer, not a reason to reshape it).
    non_diagram_layers = {"LEGEND", "TITLE", "NOTES", "WIRE_LABELS"}
    diagram_inserts = [e for e in inserts if e.dxf.layer not in non_diagram_layers]

    # 3. Every wire endpoint matches a real netlist pin position or lies on a rail
    pin_coords = set()
    for conn in netlist["connections"]:
        pin_coords.add((round(conn["src_pos"][0], 2), round(conn["src_pos"][1], 2)))
        pin_coords.add((round(conn["dst_pos"][0], 2), round(conn["dst_pos"][1], 2)))

    wire_layers = {"WIRES_PHASE", "WIRES_NEUTRAL", "WIRES_EARTH"}
    wires = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer in wire_layers]
    
    # Determine phase mode
    phase_mode = pin_model.determine_phase_mode(parsed_data.get("voltage"), parsed_data.get("phase_hint"))

    bus_y = positions.get("bus", (0, 0))[1] if "bus" in positions else None
    bad_endpoints = 0
    for w in wires:
        pts = [(round(p[0], 2), round(p[1], 2)) for p in w.get_points("xy")]
        if not pts:
            continue
        for pt in (pts[0], pts[-1]):
            nbar_x = positions.get("nbar", (-45.0, 0.0))[0]
            ebar_x = positions.get("ebar", (-60.0, 0.0))[0]
            match_pin = any(abs(pt[0]-p[0]) < tol and abs(pt[1]-p[1]) < tol for p in pin_coords)
            on_nrail = abs(pt[0] - nbar_x) < tol
            on_erail = abs(pt[0] - ebar_x) < tol
            if phase_mode == "three" and bus_y is not None:
                on_bus = abs(pt[1] - bus_y) < tol or abs(abs(pt[1] - bus_y) - 3.0) < tol
            else:
                on_bus = bus_y is not None and abs(pt[1] - bus_y) < tol
            
            if not (match_pin or on_nrail or on_erail or on_bus):
                bad_endpoints += 1
                problems.append(f"Wire endpoint {pt} does not match any pin or rail")
                
    print(f"  Wires checked: {len(wires)}, bad endpoints: {bad_endpoints}")

    # 4. Rough overlap check between symbol inserts -- diagram content only,
    # legend/title are checked separately below.
    overlap_radius = 8.0
    coords = [(e.dxf.insert.x, e.dxf.insert.y, e.dxf.name) for e in diagram_inserts]
    overlaps = []
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            x1, y1, n1 = coords[i]
            x2, y2, n2 = coords[j]
            # Junction dots and terminal rows can overlap insertion points (functioning as designed)
            if "SYM_JUNCTION" in (n1, n2):
                continue
            if abs(x1 - x2) < overlap_radius and abs(y1 - y2) < overlap_radius:
                overlaps.append(((n1, x1, y1), (n2, x2, y2)))
    if overlaps:
        problems.append(f"{len(overlaps)} possible symbol overlap(s): {overlaps}")

    # 8. [Phase 4] Legend and title block must not overlap the actual diagram,
    # or each other. Bounding-box check using the real layer geometry.
    def layer_bbox(layer_names):
        xs, ys = [], []
        for e in msp:
            if e.dxf.layer not in layer_names:
                continue
            if e.dxftype() == "INSERT" or e.dxftype() == "TEXT":
                xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
            elif e.dxftype() == "LWPOLYLINE":
                for p in e.get_points("xy"):
                    xs.append(p[0]); ys.append(p[1])
        if not xs:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def boxes_overlap(b1, b2):
        if b1 is None or b2 is None:
            return False
        return not (b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1])

    diagram_layers = {"COMPONENTS", "WIRES_PHASE", "WIRES_NEUTRAL", "WIRES_EARTH", "WIRES_FAULT"}
    diagram_bbox = layer_bbox(diagram_layers)
    legend_bbox = layer_bbox({"LEGEND"})

    # Title layer typically also holds a full-page decorative border
    # rectangle, which is SUPPOSED to enclose everything -- only the
    # actual title/subtitle TEXT should be checked for overlap, not the
    # border frame around it.
    title_text_ents = [e for e in msp if e.dxf.layer == "TITLE" and e.dxftype() == "TEXT"]
    title_bbox = None
    if title_text_ents:
        xs = [e.dxf.insert.x for e in title_text_ents]
        ys = [e.dxf.insert.y for e in title_text_ents]
        title_bbox = (min(xs), min(ys), max(xs), max(ys))

    if boxes_overlap(diagram_bbox, legend_bbox):
        problems.append(f"Legend bbox {legend_bbox} overlaps diagram bbox {diagram_bbox}")
    if boxes_overlap(diagram_bbox, title_bbox):
        problems.append(f"Title text bbox {title_bbox} overlaps diagram bbox {diagram_bbox}")
    if boxes_overlap(legend_bbox, title_bbox):
        problems.append(f"Legend bbox {legend_bbox} overlaps title text bbox {title_bbox}")

    # 5/6/7. [Phase 3B, netlist-grounded] Instead of assuming junctions sit on
    # a fixed rail x-coordinate (which is only true for SOME tap styles and
    # broke the moment taps moved to each load's own pin position), derive
    # the actual expected tap positions straight from the netlist and check
    # each one has a matching junction dot. This is robust to whatever
    # coordinate scheme the drawing code uses.
    junctions = [e for e in diagram_inserts if e.dxf.name == "SYM_JUNCTION"]
    junction_coords = [(round(j.dxf.insert.x, 2), round(j.dxf.insert.y, 2)) for j in junctions]

    def has_junction_near(pt, coords=junction_coords):
        return any(abs(pt[0] - c[0]) < tol and abs(pt[1] - c[1]) < tol for c in coords)

    load_ids = [cid for cid in netlist["components"] if pin_model.get_base_type(cid) == "loads"]
    show_neutral = "nbar" in netlist["components"]
    show_earth = "ebar" in netlist["components"]

    missing_n_taps = []
    missing_e_taps = []
    bond_conn = None
    for conn in netlist["connections"]:
        if conn["src_component"] == "nbar" and conn["dst_component"].startswith("load"):
            pt = (round(conn["dst_pos"][0], 2), round(conn["dst_pos"][1], 2))
            if not has_junction_near(pt):
                missing_n_taps.append((conn["dst_component"], pt))
        if conn["src_component"] == "ebar" and conn["dst_component"].startswith("load"):
            pt = (round(conn["dst_pos"][0], 2), round(conn["dst_pos"][1], 2))
            if not has_junction_near(pt):
                missing_e_taps.append((conn["dst_component"], pt))
        if conn["src_component"] == "nbar" and conn["dst_component"] == "ebar":
            bond_conn = conn

    if show_neutral and missing_n_taps:
        problems.append(
            f"{len(missing_n_taps)}/{len(load_ids)} Neutral tap(s) have no matching "
            f"junction dot at their real dst_pos: {missing_n_taps}"
        )
    if show_earth and missing_e_taps:
        problems.append(
            f"{len(missing_e_taps)}/{len(load_ids)} Earth tap(s) have no matching "
            f"junction dot at their real dst_pos: {missing_e_taps}"
        )
        # Known drawing convention: bond dot is placed at (nbar_x, dst_pos_y)
        nbar_x = positions.get("nbar", (-45.0, 0.0))[0]
        bond_pt = (nbar_x, round(bond_conn["dst_pos"][1], 2))
        if not has_junction_near(bond_pt):
            problems.append(
                f"N-E bond junction missing at expected {bond_pt} -- check the wire_type "
                f"used for the nbar->ebar connection matches the branch that draws it "
                f"(pin_model.py tags this connection as wire_type 'E', not 'N')."
            )

    # Every junction must actually touch a drawn wire (not floating)
    bad_junctions = 0
    for jx, jy in junction_coords:
        meets_wire = False
        for w in wires:
            w_pts = [(round(p[0], 2), round(p[1], 2)) for p in w.get_points("xy")]
            if any(abs(p[0] - jx) < tol and abs(p[1] - jy) < tol for p in w_pts):
                meets_wire = True
                break
        if not meets_wire:
            bad_junctions += 1
            problems.append(f"Junction at {jx, jy} does not connect to any drawn wire.")

    print(f"  Junctions checked: {len(junctions)}, bad junctions: {bad_junctions}")

    if problems:
        print("  RESULT: FAIL")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  RESULT: PASS")

    return len(problems) == 0


def verify_helpers_removed():
    print(f"\n{'='*70}\nHELPER FUNCTIONS REMOVAL CHECK\n{'='*70}")
    # Path is relative to project root
    dxf_gen_path = "ECD/dxf_generator.py"
    if not os.path.exists(dxf_gen_path):
        print(f"  Error: {dxf_gen_path} not found.")
        return False
        
    with open(dxf_gen_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    problems = []
    for helper in ["top_mid", "bot_mid", "left_mid", "right_mid"]:
        # Match function definition or call style
        if f"def {helper}" in code or f"{helper}(" in code:
            problems.append(f"Old box helper '{helper}' is still defined or referenced in dxf_generator.py")
            
    if problems:
        print("  RESULT: FAIL")
        for p in problems:
            print(f"    - {p}")
        return False
    else:
        print("  RESULT: PASS (All old box-edge helpers successfully removed)")
        return True


if __name__ == "__main__":
    results = {}
    for name, data in TEST_CASES.items():
        results[name] = check_case(name, data)

    helpers_ok = verify_helpers_removed()

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    all_ok = True
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
        
    print(f"  helpers_removal: {'PASS' if helpers_ok else 'FAIL'}")
    all_ok = all_ok and helpers_ok

    sys.exit(0 if all_ok else 1)