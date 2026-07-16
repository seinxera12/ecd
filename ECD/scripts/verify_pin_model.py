import sys
# Run this from your project root (D:\ecd, the parent of ECD\), using:
#   python -m ECD.scripts.verify_pin_model
# Do NOT run it from inside the ECD\ folder itself, and do NOT move this
# file to the root -- it needs to stay next to pin_model.py so the
# ECD.pin_model import below resolves correctly.

from ECD.pin_model import compute_component_positions, generate_netlist, validate_netlist

def run_case(name, parsed_data):
    print(f"\n{'='*60}\nCASE: {name}\n{'='*60}")
    positions = compute_component_positions(parsed_data)
    netlist = generate_netlist(parsed_data, positions)
    ok, errors = validate_netlist(netlist)
    print(f"Validation OK: {ok}")
    for e in errors:
        print(f"  - {e}")

    # Check: does neutral skip maincb/rcd (no N pins on them at all)?
    n_conns = [c for c in netlist["connections"] if c["wire_type"] == "N"]
    print(f"Neutral connections ({len(n_conns)}):")
    for c in n_conns:
        print(f"  {c['src_component']}.{c['src_pin']} -> {c['dst_component']}.{c['dst_pin']}  src_pos={c['src_pos']}")

    # Check: are bus taps at distinct x-positions (not all identical)?
    bus_taps = [c for c in netlist["connections"] if c["src_component"] == "bus"]
    if bus_taps:
        tap_xs = [c["src_pos"][0] for c in bus_taps]
        print(f"Bus tap x-positions: {tap_xs}  (distinct: {len(set(tap_xs)) == len(tap_xs)})")

    return ok, errors


# Case 1: full panel, 3 outgoing circuits, RCD present -- the exact
# combination that previously triggered the duplicate-wiring bug
full_panel = {
    "components": [
        ("supply", "Supply"), ("maincb", "Main CB"), ("rcd", "RCD"),
        ("bus", "Bus"), ("nbar", "N-Bar"), ("ebar", "E-Bar"),
        ("outcb_1", "CB1"), ("outcb_2", "CB2"), ("outcb_3", "CB3"),
        ("loads", "Loads"),
    ],
    "flags": {"show_neutral": True, "show_earth": True},
}
run_case("Full panel, 3 circuits, RCD + N-bar + E-bar", full_panel)

# Case 2: minimal panel, no bus/nbar/ebar at all
minimal_panel = {
    "components": [("supply", "Supply"), ("maincb", "Main CB"), ("loads", "Loads")],
    "flags": {"show_neutral": False, "show_earth": False},
}
run_case("Minimal panel, no rails", minimal_panel)

# Case 3: deliberately break it -- explicit connections list that omits
# supply->bus, to confirm validate_netlist still correctly catches broken
# continuity rather than silently passing
broken_panel = {
    "components": [
        ("supply", "Supply"), ("bus", "Bus"),
        ("outcb_1", "CB1"), ("loads", "Loads"),
    ],
    "connections": [("bus", "outcb_1"), ("outcb_1", "loads")],  # supply->bus missing on purpose
    "flags": {"show_neutral": False, "show_earth": False},
}
ok, errors = run_case("Broken panel (supply not connected to bus)", broken_panel)
assert not ok, "Expected validation to fail for a genuinely disconnected supply, but it passed!"
print("\nConfirmed: validate_netlist correctly detected the broken case.")

print("\n\nALL SCENARIOS RAN WITHOUT CRASHING OR ASSERTION ERRORS.")