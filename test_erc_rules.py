import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ECD.erc import run_erc, ERCFinding
from ECD.pin_model import compute_component_positions, generate_netlist, validate_netlist

def test_erc_rules():
    print("==========================================================")
    print("RUNNING ERC TIER 1 PRESENCE RULE VERIFICATION")
    print("==========================================================")

    # -------------------------------------------------------------------------
    # TEST 1: ERC-001 (No Supply and Multiple Supplies)
    # -------------------------------------------------------------------------
    print("\n--- Test 1A: ERC-001 (No Supply) ---")
    data_no_supply = {
        "components": [("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple",
        "prompt": "panel with no supply"
    }
    netlist = generate_netlist(data_no_supply, compute_component_positions(data_no_supply))
    findings = run_erc(netlist, data_no_supply)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-001" in codes, "Failed: ERC-001 should catch missing supply"
    assert any("No supply component found" in f.message for f in findings), "Failed: Incorrect message for missing supply"
    print("PASS: ERC-001 caught missing supply.")

    print("\n--- Test 1B: ERC-001 (Multiple Supplies) ---")
    data_two_supplies = {
        "components": [("supply", "Grid Supply 1"), ("supply_2", "Grid Supply 2"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple",
        "prompt": "panel with two supplies"
    }
    netlist = generate_netlist(data_two_supplies, compute_component_positions(data_two_supplies))
    findings = run_erc(netlist, data_two_supplies)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-001" in codes, "Failed: ERC-001 should catch multiple supplies"
    assert any("Multiple supplies found" in f.message for f in findings), "Failed: Incorrect message for multiple supplies"
    print("PASS: ERC-001 caught multiple supplies.")

    # -------------------------------------------------------------------------
    # TEST 2: ERC-002 (Missing Main Breaker in supply -> loads)
    # -------------------------------------------------------------------------
    print("\n--- Test 2: ERC-002 (supply -> loads with no maincb) ---")
    data_no_maincb = {
        "components": [("supply", "Main Supply"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple",
        "prompt": "supply to loads directly"
    }
    netlist = generate_netlist(data_no_maincb, compute_component_positions(data_no_maincb))
    netlist_ok, netlist_errors = validate_netlist(netlist)
    print(f"validate_netlist() result: ok={netlist_ok}, errors={netlist_errors}")
    
    findings = run_erc(netlist, data_no_maincb)
    codes = [f.code for f in findings]
    print("ERC Findings:", [f.format_string() for f in findings])
    assert netlist_ok is True, "Expected validate_netlist() to return ok=True for supply -> loads (wire trace passes)"
    assert "ERC-002" in codes, "Failed: ERC-002 should catch missing maincb in supply -> loads"
    print("PASS: ERC-002 caught missing main breaker where validate_netlist() passed.")

    # -------------------------------------------------------------------------
    # TEST 3: ERC-003 (Earth Bar missing when required)
    # -------------------------------------------------------------------------
    print("\n--- Test 3: ERC-003 (No ebar when show_earth=True) ---")
    data_no_ebar = {
        "components": [("supply", "Main Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": True, "show_rcd": False},
        "complexity": "Simple",
        "prompt": "panel with earth but no ebar component"
    }
    netlist = generate_netlist(data_no_ebar, compute_component_positions(data_no_ebar))
    findings = run_erc(netlist, data_no_ebar)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-003" in codes, "Failed: ERC-003 should catch missing ebar when show_earth=True"
    print("PASS: ERC-003 caught missing ebar.")

    # -------------------------------------------------------------------------
    # TEST 3B: ERC-003b (Neutral Bar missing when required)
    # -------------------------------------------------------------------------
    print("\n--- Test 3B: ERC-003b (No nbar when show_neutral=True) ---")
    data_no_nbar = {
        "components": [("supply", "Main Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": True, "show_earth": False, "show_rcd": False},
        "complexity": "Simple",
        "prompt": "panel with neutral but no nbar component"
    }
    netlist = generate_netlist(data_no_nbar, compute_component_positions(data_no_nbar))
    netlist_ok, netlist_errors = validate_netlist(netlist)
    findings = run_erc(netlist, data_no_nbar)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-003b" in codes, "Failed: ERC-003b should catch missing nbar when show_neutral=True"
    assert "Validation Error: Neutral connections are enabled" not in str(netlist_errors), "Failed: validate_netlist should no longer emit duplicate nbar presence error"
    print("PASS: ERC-003b caught missing nbar and validate_netlist produced no duplicate.")

    # -------------------------------------------------------------------------
    # TEST 4: ERC-004 (RCD missing when required by complexity)
    # -------------------------------------------------------------------------
    print("\n--- Test 4: ERC-004 (No RCD on Standard mode) ---")
    data_no_rcd = {
        "components": [("supply", "Main Supply"), ("maincb", "Main Breaker"), ("bus", "Busbar"), ("nbar", "NBar"), ("ebar", "EBar"), ("loads", "Loads")],
        "flags": {"show_neutral": True, "show_earth": True, "show_rcd": True},
        "complexity": "Standard",
        "prompt": "standard panel"
    }
    netlist = generate_netlist(data_no_rcd, compute_component_positions(data_no_rcd))
    findings = run_erc(netlist, data_no_rcd)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-004" in codes, "Failed: ERC-004 should catch missing RCD on Standard complexity mode"
    print("PASS: ERC-004 caught missing RCD on Standard mode.")

    # -------------------------------------------------------------------------
    # TEST 5: Fully Valid Diagram (zero findings)
    # -------------------------------------------------------------------------
    print("\n--- Test 5: Fully Valid Diagram (full_panel) ---")
    valid_data = {
        "components": [
            ("supply", "Main Supply"),
            ("maincb", "Main Breaker"),
            ("rcd", "RCD"),
            ("bus", "Busbar"),
            ("nbar", "NBar"),
            ("ebar", "EBar"),
            ("outcb_1", "Branch Breaker 1"),
            ("loads", "Loads")
        ],
        "flags": {"show_neutral": True, "show_earth": True, "show_rcd": True},
        "complexity": "Standard",
        "prompt": "full standard panel with RCD and ebar"
    }
    netlist = generate_netlist(valid_data, compute_component_positions(valid_data))
    netlist_ok, netlist_errors = validate_netlist(netlist)
    findings = run_erc(netlist, valid_data)
    print(f"validate_netlist() errors: {netlist_errors}")
    print("ERC Findings:", [f.format_string() for f in findings])
    assert netlist_ok is True, "Valid diagram should pass validate_netlist()"
    assert len(findings) == 0, f"Expected 0 ERC findings on valid diagram, got {len(findings)}"
    print("PASS: Valid diagram produced 0 ERC findings.")

    # -------------------------------------------------------------------------
    # TEST 6: ERC-005 (Voltage / Phase Mode Override & Inference)
    # -------------------------------------------------------------------------
    print("\n--- Test 6A: ERC-005 (230V + explicit 'three-phase' override) ---")
    data_override = {
        "voltage": "230V",
        "phase_hint": "three-phase",
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_override, compute_component_positions(data_override))
    findings = run_erc(netlist, data_override)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-005" in codes, "Failed: ERC-005 should surface 230V + three-phase override"
    assert any("typically single-phase" in f.message for f in findings), "Failed: Incorrect message for override"
    print("PASS: ERC-005 caught voltage/phase override.")

    print("\n--- Test 6B: ERC-005 (415V + no phase hint inference) ---")
    data_infer = {
        "voltage": "415V",
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_infer, compute_component_positions(data_infer))
    findings = run_erc(netlist, data_infer)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-005" in codes, "Failed: ERC-005 should surface 415V inference"
    assert any("inferred three-phase" in f.message for f in findings), "Failed: Incorrect message for inference"
    print("PASS: ERC-005 caught 415V inference.")

    print("\n--- Test 6C: ERC-005 (Unambiguous case: 230V + single-phase) ---")
    data_unambig = {
        "voltage": "230V",
        "phase_hint": "single-phase",
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_unambig, compute_component_positions(data_unambig))
    findings = run_erc(netlist, data_unambig)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-005" not in codes, "Failed: ERC-005 should NOT fire on unambiguous inputs"
    print("PASS: ERC-005 produced 0 findings on unambiguous inputs.")

    # -------------------------------------------------------------------------
    # TEST 7: ERC-006 (Invalid component-type pairing for phase mode)
    # -------------------------------------------------------------------------
    print("\n--- Test 7A: ERC-006 (3-phase component in single-phase diagram) ---")
    data_incompat = {
        "voltage": "230V",
        "phase_hint": "single-phase",
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("motor_3ph", "3PH Motor"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_incompat, compute_component_positions(data_incompat))
    findings = run_erc(netlist, data_incompat)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-006" in codes, "Failed: ERC-006 should catch 3-phase component in single-phase diagram"
    print("PASS: ERC-006 caught 3-phase component in single-phase diagram.")

    print("\n--- Test 7B: ERC-006 (3-phase component in three-phase diagram - control) ---")
    data_compat = {
        "voltage": "415V",
        "phase_hint": "three-phase",
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("motor_3ph", "3PH Motor"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_compat, compute_component_positions(data_compat))
    findings = run_erc(netlist, data_compat)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-006" not in codes, "Failed: ERC-006 should NOT fire on valid 3-phase component in 3-phase diagram"
    print("PASS: ERC-006 produced 0 findings on 3-phase component in 3-phase diagram.")

    # -------------------------------------------------------------------------
    # TEST 8: ERC-007 (Load bypasses all protection)
    # -------------------------------------------------------------------------
    print("\n--- Test 8: ERC-007 (Load wired directly to supply without breaker) ---")
    data_unprotected = {
        "components": [("supply", "Supply"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist = generate_netlist(data_unprotected, compute_component_positions(data_unprotected))
    findings = run_erc(netlist, data_unprotected)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    # -------------------------------------------------------------------------
    # TEST 9: ERC-008 (Cycle Detection)
    # -------------------------------------------------------------------------
    print("\n--- Test 9A: ERC-008 (Cyclic Connection in Netlist) ---")
    data_cyclic = {
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist_cyclic = generate_netlist(data_cyclic, compute_component_positions(data_cyclic))
    # Inject deliberate cyclic connection: loads -> maincb
    netlist_cyclic["connections"].append({
        "src_component": "loads", "src_pin": "L_out",
        "dst_component": "maincb", "dst_pin": "L_in",
        "wire_type": "L"
    })
    findings = run_erc(netlist_cyclic, data_cyclic)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-008" in codes, "Failed: ERC-008 should catch cyclic connection"
    print("PASS: ERC-008 caught cyclic connection.")

    print("\n--- Test 9B: ERC-008 (Control - full_panel & minimal_panel) ---")
    min_data = {
        "components": [("supply", "Main Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple", "prompt": "minimal panel"
    }
    netlist_min = generate_netlist(min_data, compute_component_positions(min_data))
    findings_min = run_erc(netlist_min, min_data)
    assert "ERC-008" not in [f.code for f in findings_min], "Failed: ERC-008 false positive on minimal_panel"
    assert "ERC-008" not in [f.code for f in run_erc(generate_netlist(valid_data, compute_component_positions(valid_data)), valid_data)], "Failed: ERC-008 false positive on full_panel"
    print("PASS: ERC-008 produced 0 findings on full_panel and minimal_panel.")

    # -------------------------------------------------------------------------
    # TEST 10: ERC-009 (Orphaned Component Detection)
    # -------------------------------------------------------------------------
    print("\n--- Test 10A: ERC-009 (Unwired Spare Component) ---")
    data_orphan = {
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist_orphan = generate_netlist(data_orphan, compute_component_positions(data_orphan))
    # Declare spare_block in parsed_data without adding any netlist connections for it
    data_orphan["components"].append(("spare_block", "Spare Component"))
    findings = run_erc(netlist_orphan, data_orphan)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-009" in codes, "Failed: ERC-009 should catch orphaned spare_block component"
    assert any("spare_block" in f.components for f in findings if f.code == "ERC-009"), "Failed: ERC-009 should report spare_block ID"
    print("PASS: ERC-009 caught orphaned component 'spare_block'.")

    print("\n--- Test 10B: ERC-009 (Control - full_panel) ---")
    findings_full = run_erc(generate_netlist(valid_data, compute_component_positions(valid_data)), valid_data)
    assert "ERC-009" not in [f.code for f in findings_full], f"Failed: ERC-009 false-positive on full_panel: {[f.format_string() for f in findings_full]}"
    print("PASS: ERC-009 produced 0 findings on full_panel (loads expansion handled correctly).")

    print("\n--- Test 10C: ERC-009 (Control - minimal_panel) ---")
    assert "ERC-009" not in [f.code for f in findings_min], f"Failed: ERC-009 false-positive on minimal_panel: {[f.format_string() for f in findings_min]}"
    print("PASS: ERC-009 produced 0 findings on minimal_panel.")

    # -------------------------------------------------------------------------
    # TEST 11: ERC-010 (Duplicate & Colliding Component IDs)
    # -------------------------------------------------------------------------
    print("\n--- Test 11A: ERC-010 (Exact Duplicate ID String) ---")
    data_dup_exact = {
        "components": [("supply", "Supply"), ("maincb", "Breaker 1"), ("maincb", "Breaker 2"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist_dup = generate_netlist(data_dup_exact, compute_component_positions(data_dup_exact))
    findings = run_erc(netlist_dup, data_dup_exact)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-010" in codes, "Failed: ERC-010 should catch exact duplicate maincb IDs"
    print("PASS: ERC-010 caught exact duplicate component ID.")

    print("\n--- Test 11B: ERC-010 (Normalized Colliding IDs: loads vs loads_1) ---")
    data_collide_loads = {
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("loads", "Generic Loads"), ("loads_1", "Load 1")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist_collide = generate_netlist(data_collide_loads, compute_component_positions(data_collide_loads))
    findings = run_erc(netlist_collide, data_collide_loads)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-010" in codes, "Failed: ERC-010 should catch normalized collision between loads and loads_1"
    print("PASS: ERC-010 caught normalized ID collision (loads vs loads_1).")

    print("\n--- Test 11C: ERC-010 (Control - distinct outcb_1 and outcb_2) ---")
    data_distinct_outcb = {
        "components": [("supply", "Supply"), ("maincb", "Main Breaker"), ("bus", "Busbar"), ("outcb_1", "MCB 1"), ("outcb_2", "MCB 2"), ("loads", "Loads")],
        "flags": {"show_neutral": False, "show_earth": False, "show_rcd": False},
        "complexity": "Simple"
    }
    netlist_distinct = generate_netlist(data_distinct_outcb, compute_component_positions(data_distinct_outcb))
    findings = run_erc(netlist_distinct, data_distinct_outcb)
    codes = [f.code for f in findings]
    print("Findings:", [f.format_string() for f in findings])
    assert "ERC-010" not in codes, "Failed: ERC-010 false positive on distinct outcb_1 and outcb_2"
    print("PASS: ERC-010 produced 0 findings on distinct outcb_1 and outcb_2.")

    print("\n==========================================================")
    print("ALL ERC TIER 1, TIER 2 & TIER 3 TESTS PASSED SUCCESSFULLY!")
    print("==========================================================")

if __name__ == "__main__":
    test_erc_rules()
