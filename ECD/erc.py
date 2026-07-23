"""
ECD/erc.py
==========
Electrical Rule Check (ERC) — three-tier deterministic validation engine.

Operates on the real netlist and parsed_data produced by the diagram pipeline,
completely independently of LLM semantic review and wire-continuity checks
(validate_netlist). All rules are pure Python: no LLM, no network, no side effects.

Rule Tiers
----------
Tier 1 — Presence Rules (ERC-001 to ERC-004)
    Ask: "Are all required components present?"
    ERC-001  : Exactly one supply component must exist.
    ERC-002  : A main breaker (maincb) or main-role device must head the column.
    ERC-003  : Earth bar (ebar) must be present in Standard / Detailed mode.
    ERC-003b : Neutral bar (nbar) must be present in Standard / Detailed mode.
    ERC-004  : Earth fault protection (RCD / RCBO) must be present in Standard /
              Detailed mode.

Tier 2 — Consistency Rules (ERC-005 to ERC-007)
    Ask: "Is the combination of what is present internally consistent?"
    ERC-005 : Surface any voltage-vs-phase conflict or silent inference so the user
              is never surprised by which mode was chosen.
    ERC-006 : Three-phase component types must not appear in a single-phase diagram.
    ERC-007 : Every load must be protected — no load may be reachable from supply
              without traversing at least one protective device (maincb / rcd /
              rcbo / outcb).

Tier 3 — Topology Sanity Rules (ERC-008 to ERC-010)
    Ask: "Is the graph structure itself sane, independent of what the components are?"
    ERC-008 : The wiring graph must be acyclic (no feedback loops).
    ERC-009 : Every declared component must appear in at least one netlist connection
              (no orphaned / unwired components).
    ERC-010 : Component IDs must be unique — both by exact string and by normalised
              base-type key for singleton component classes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import re

try:
    from ECD.pin_model import compute_component_positions, get_base_type
except ImportError:
    from pin_model import compute_component_positions, get_base_type


@dataclass
class ERCFinding:
    code: str              # e.g., 'ERC-001'
    severity: str          # 'ERROR' or 'WARNING'
    message: str           # Human-readable message
    components: List[str] = field(default_factory=list)  # Component IDs concerned

    def format_string(self) -> str:
        """Format finding for text display."""
        comp_str = f" ({', '.join(self.components)})" if self.components else ""
        return f"[{self.code}] [{self.severity}]{comp_str}: {self.message}"


def run_erc(netlist: dict, parsed_data: dict) -> List[ERCFinding]:
    """
    Execute all three ERC tiers against the supplied netlist and parsed_data.

    Parameters
    ----------
    netlist     : dict produced by generate_netlist() — contains 'components',
                  'connections', 'flags', etc.
    parsed_data : dict produced by parse_prompt() or _on_llm_finished() — contains
                  'components', 'flags', 'voltage', 'phase_hint', 'complexity', 'prompt'.

    Returns
    -------
    List[ERCFinding]
        Zero or more findings, each carrying a code (ERC-001 … ERC-010), a
        severity ('ERROR' or 'WARNING'), a human-readable message, and the list
        of component IDs involved.

    Notes
    -----
    Rules are evaluated in order ERC-001 → ERC-010.  A rule that fires does NOT
    short-circuit later rules — every rule is evaluated independently so that all
    issues in a single diagram are surfaced in one pass.
    """
    findings: List[ERCFinding] = []
    
    components = netlist.get("components", {})
    if not components and parsed_data:
        # Fallback to components in parsed_data if netlist components dict is empty
        components = {cid: {"type": get_base_type(cid)} for cid, _ in parsed_data.get("components", [])}
        
    comp_list = parsed_data.get("components", [])
    comp_ids = [cid.lower() for cid, _ in comp_list] if comp_list else [c.lower() for c in components.keys()]
    
    flags = netlist.get("flags", {})
    if not flags and parsed_data:
        flags = parsed_data.get("flags", {})
        
    complexity = parsed_data.get("complexity", "Standard") if parsed_data else "Standard"
    prompt_text = (parsed_data.get("prompt", "") if parsed_data else "").lower()

    # -------------------------------------------------------------------------
    # Rule ERC-001  |  Tier 1 — Presence  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # Every distribution diagram must originate from exactly one incoming supply.
    #
    # Fires when:
    #   • Zero supply components are found  →  nothing to distribute from.
    #   • More than one supply component is found  →  multiple-source topologies
    #     (ATS / changeover) are not yet modelled by the pin system and produce
    #     ambiguous wiring; the user must resolve this manually.
    #
    # Identification: get_base_type(cid) == "supply"  OR
    #                 netlist components dict carries type == "supply".
    # -------------------------------------------------------------------------
    supply_components = [
        cid for cid in comp_ids
        if get_base_type(cid) == "supply" or components.get(cid, {}).get("type") == "supply"
    ]
    if len(supply_components) == 0:
        findings.append(ERCFinding(
            code="ERC-001",
            severity="ERROR",
            message="No supply component found in diagram.",
            components=[]
        ))
    elif len(supply_components) > 1:
        findings.append(ERCFinding(
            code="ERC-001",
            severity="ERROR",
            message=f"Multiple supplies found ({len(supply_components)}) — only one supply per diagram is currently supported.",
            components=supply_components
        ))

    # -------------------------------------------------------------------------
    # Rule ERC-002  |  Tier 1 — Presence  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # A main circuit breaker (maincb) or a device acting in that role must be the
    # first protective component on the L-path below the supply.
    #
    # Fires when:
    #   • No component with base_type == "maincb" exists, AND
    #   • No rcbo sits immediately below the supply in the vertical column
    #     (position x ≈ 0, sorted by descending y — i.e. top of column).
    #
    # The position-based fallback allows a single RCBO to act as a combined
    # main-breaker + earth-fault device, which is permitted by IEC 60364.
    #
    # Japanese exclusion keywords (ブレーカーなし, 主遮断器は含めない, 直接接続)
    # handled upstream in parse_prompt / is_explicitly_excluded; those diagrams
    # are intentionally breaker-free and will correctly raise ERC-002.
    # -------------------------------------------------------------------------
    # Check if maincb exists
    has_maincb = any(
        get_base_type(cid) == "maincb" or cid == "maincb"
        for cid in comp_ids
    )
    
    if not has_maincb:
        # Check if an rcbo is acting as the main protection device at top of main column
        acting_as_main = False
        try:
            positions = compute_component_positions(parsed_data)
            # Find vertical column (x == 0.0) sorted by Y descending
            main_col = sorted(
                [cid for cid, pos in positions.items() if abs(pos[0]) < 1e-3],
                key=lambda cid: positions[cid][1],
                reverse=True
            )
            # First element is supply; check element directly below supply
            if len(main_col) >= 2:
                top_dev = main_col[1]
                bt = get_base_type(top_dev)
                if bt == "rcbo":
                    acting_as_main = True
        except Exception:
            pass

        if not acting_as_main:
            findings.append(ERCFinding(
                code="ERC-002",
                severity="ERROR",
                message="Main breaker (maincb) or main-role protection device missing at top of distribution column.",
                components=["maincb"]
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-003  |  Tier 1 — Presence  |  Severity: ERROR / WARNING
    # -------------------------------------------------------------------------
    # Protective earthing is mandatory in any Standard or Detailed installation.
    # An earth bar (ebar) provides the common earth reference for all equipment.
    #
    # Fires as ERROR when:
    #   • Earth is required (Standard/Detailed mode, or show_earth flag is True)
    #     AND no ebar component is present AND the user did not explicitly omit it.
    #
    # Fires as WARNING when:
    #   • Same conditions above BUT the prompt contains an explicit exclusion phrase
    #     ("no earth", "without ground", "接地なし", etc.) — the diagram is intentional
    #     but the user is reminded that protective earthing is still best practice.
    # -------------------------------------------------------------------------
    show_earth = flags.get("show_earth", False)
    ebar_in_parsed = "ebar" in comp_ids
    
    # Earth is required if show_earth flag is True, ebar is in parsed_data, or in Standard/Detailed complexity modes
    earth_required = show_earth or ebar_in_parsed or complexity in ("Standard", "Detailed")
    has_ebar = "ebar" in components or "ebar" in comp_ids
    explicit_no_earth = any(kw in prompt_text for kw in ["no earth", "no ground", "without earth", "without ground"]) or bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:earth|ground|ebar|e-bar|e\s+bar)\b', prompt_text))

    if earth_required and not has_ebar:
        if explicit_no_earth:
            findings.append(ERCFinding(
                code="ERC-003",
                severity="WARNING",
                message="Earth bar (ebar) is omitted per prompt request, but standard distribution panels require protective earthing.",
                components=["ebar"]
            ))
        else:
            findings.append(ERCFinding(
                code="ERC-003",
                severity="ERROR",
                message="Earth bar (ebar) is required but missing from netlist.",
                components=["ebar"]
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-003b |  Tier 1 — Presence  |  Severity: ERROR / WARNING
    # -------------------------------------------------------------------------
    # A neutral bar (nbar) provides the common neutral reference for single-phase
    # and 4-wire three-phase equipment in Standard or Detailed installations.
    #
    # Fires as ERROR when:
    #   • Neutral is required (Standard/Detailed mode, or show_neutral flag is True)
    #     AND no nbar component is present AND the user did not explicitly omit it.
    #
    # Fires as WARNING when:
    #   • Same conditions above BUT the prompt contains an explicit exclusion phrase
    #     ("no neutral", "without neutral", "中性線なし", etc.) — the diagram is intentional
    #     but the user is reminded that neutral distribution is required for single-phase loads.
    # -------------------------------------------------------------------------
    show_neutral = flags.get("show_neutral", False)
    nbar_in_parsed = "nbar" in comp_ids
    
    # Neutral is required if show_neutral flag is True, nbar is in parsed_data, or in Standard/Detailed complexity modes
    neutral_required = show_neutral or nbar_in_parsed or complexity in ("Standard", "Detailed")
    has_nbar = "nbar" in components or "nbar" in comp_ids
    explicit_no_neutral = any(kw in prompt_text for kw in ["no neutral", "without neutral", "中性線なし", "中性バーなし"]) or bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:neutral|nbar|n-bar|n\s+bar)\b', prompt_text))

    if neutral_required and not has_nbar:
        if explicit_no_neutral:
            findings.append(ERCFinding(
                code="ERC-003b",
                severity="WARNING",
                message="Neutral bar (nbar) is omitted per prompt request, but standard distribution panels require a neutral bar for return paths.",
                components=["nbar"]
            ))
        else:
            findings.append(ERCFinding(
                code="ERC-003b",
                severity="ERROR",
                message="Neutral bar (nbar) is required but missing from netlist.",
                components=["nbar"]
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-004  |  Tier 1 — Presence  |  Severity: ERROR / WARNING
    # -------------------------------------------------------------------------
    # Earth-fault protection (RCD or RCBO) is mandatory in Standard and Detailed
    # installations.  Absence of an RCD leaves socket-circuit users unprotected
    # against indirect contact.
    #
    # Fires as ERROR when:
    #   • Complexity is Standard or Detailed, OR the show_rcd flag is True, AND
    #   • No rcd / rcbo component is found in the diagram, AND
    #   • The user did not explicitly request omission.
    #
    # Fires as WARNING when:
    #   • Same conditions but prompt contains an explicit exclusion phrase
    #     ("no rcd", "without rcd", "漏電遮断器なし", etc.).
    #
    # Note: An RCBO that sits at the top of the column and acts as the main
    # breaker (detected by ERC-002 fallback) is NOT double-counted here.
    # RCD is required by Standard or Detailed complexity levels, or if show_rcd flag is set
    rcd_required_by_complexity = complexity in ("Standard", "Detailed") or flags.get("show_rcd", False)
    
    explicit_no_rcd = any(kw in prompt_text for kw in ["no rcd", "no residual", "no earth fault", "without rcd"]) or bool(re.search(r'\b(?:no|without|exclude|omit|(?:do|does|did)\s+not\s+include|don\'?t\s+include)\b.{0,60}?\b(?:rcd|rcbo|residual|earth\s+fault)\b', prompt_text))
    
    if rcd_required_by_complexity:
        has_rcd_or_rcbo = any(
            cid in ("rcd", "rcbo") or get_base_type(cid) in ("rcd", "rcbo")
            for cid in comp_ids
        )
        if not has_rcd_or_rcbo:
            if explicit_no_rcd:
                findings.append(ERCFinding(
                    code="ERC-004",
                    severity="WARNING",
                    message="Earth fault protection (RCD/RCBO) is omitted per prompt request, but standard residential installations with socket circuits require RCD/RCBO protection.",
                    components=["rcd"]
                ))
            else:
                findings.append(ERCFinding(
                    code="ERC-004",
                    severity="ERROR",
                    message=f"Earth fault protection (RCD/RCBO) is required by {complexity} mode but missing from netlist.",
                    components=["rcd"]
                ))

    # -------------------------------------------------------------------------
    # Rule ERC-005  |  Tier 2 — Consistency  |  Severity: WARNING
    # -------------------------------------------------------------------------
    # determine_phase_mode_detailed() already resolves conflicts between the
    # stated voltage and an explicit phase hint.  ERC-005 surfaces that decision
    # so it is never silent — the user sees exactly which mode was chosen and why.
    #
    # Fires as WARNING when:
    #   • reason_code == "OVERRIDE"  →  voltage and phase hint are in conflict
    #     (e.g. 230 V + explicit "three-phase") and the hint won.  The diagram
    #     is generated correctly, but the user should confirm the override.
    #   • reason_code == "INFERRED"  →  no phase hint was given and the mode was
    #     inferred from voltage alone (e.g. 415 V → three-phase).  The user is
    #     informed of the assumption.
    #
    # Does NOT fire when:
    #   • The voltage and hint are consistent (e.g. 230 V + "single-phase").
    #   • No voltage is present in parsed_data (Neutral / minimal panels).
    # -------------------------------------------------------------------------
    voltage = parsed_data.get("voltage") if parsed_data else None
    phase_hint = parsed_data.get("phase_hint") if parsed_data else None
    if not phase_hint and parsed_data:
        phase_hint = parsed_data.get("flags", {}).get("phase_hint")

    try:
        from ECD.pin_model import determine_phase_mode_detailed
    except ImportError:
        from pin_model import determine_phase_mode_detailed

    resolved_mode, reason_code, reason_msg = determine_phase_mode_detailed(voltage, phase_hint)
    if reason_code in ("OVERRIDE", "INFERRED") and reason_msg:
        findings.append(ERCFinding(
            code="ERC-005",
            severity="WARNING",
            message=reason_msg,
            components=[]
        ))

    # -------------------------------------------------------------------------
    # Rule ERC-006  |  Tier 2 — Consistency  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # A component whose type is inherently three-phase (e.g. motor_3ph, bus_3ph,
    # supply_3ph) cannot be correctly wired in a single-phase diagram.  The pin
    # model assigns L1/L2/L3 terminals to these components, which have no
    # counterpart in a single-phase netlist, making wiring physically invalid.
    #
    # Fires as ERROR when:
    #   • The resolved phase mode (from ERC-005) is "single", AND
    #   • A component whose ID or base_type matches a three-phase pattern is found.
    #
    # Recognised three-phase patterns:
    #   • Exact type membership: {sym_motor_3ph, sym_supply_3ph, motor_3ph,
    #                              supply_3ph, bus_3ph, contactor_3ph}
    #   • Regex suffix match: \b(3ph|3phase|3-phase|three_phase|three-phase)\b
    #
    # Does NOT fire when the resolved mode is "three" — three-phase components
    # are valid in a three-phase diagram.
    # -------------------------------------------------------------------------
    if resolved_mode == "single":
        three_phase_types = {"sym_motor_3ph", "sym_supply_3ph", "motor_3ph", "supply_3ph", "bus_3ph", "contactor_3ph"}
        for cid in comp_ids:
            base_t = get_base_type(cid)
            is_3ph = (
                cid in three_phase_types or
                base_t in three_phase_types or
                bool(re.search(r'\b(?:3ph|3phase|3-phase|three_phase|three-phase)\b', cid))
            )
            if is_3ph:
                findings.append(ERCFinding(
                    code="ERC-006",
                    severity="ERROR",
                    message=f"Three-phase component '{cid}' is incompatible with single-phase resolved diagram.",
                    components=[cid]
                ))

    # -------------------------------------------------------------------------
    # Rule ERC-007  |  Tier 2 — Consistency  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # Performs a directed graph walk on the L-net (phase conductor connections)
    # from every supply output pin to every load input pin.  A load is considered
    # "unprotected" if at least one traversable path exists from supply → load
    # without crossing any protective device.
    #
    # Protective device base types: maincb, rcd, rcbo, outcb.
    #
    # Walk algorithm:
    #   1. Start from each supply L_out / L1_out / L2_out / L3_out pin.
    #   2. Follow connections, passing through component internal pin-pairs
    #      (_in → _out) to model current flow direction.
    #   3. Record whether any protective base type was seen on the path.
    #   4. If the load is reached via a path with zero protective devices seen,
    #      flag the load as unprotected.
    #
    # Fallback (no netlist connections available):
    #   If no connections exist in the netlist and no protective device is present
    #   anywhere in comp_ids, all loads are flagged as unprotected.
    #
    # Note: This rule fires alongside ERC-002 when both the main breaker and
    # the RCD are absent — all three rules are independent.
    # -------------------------------------------------------------------------
    PROTECTIVE_BASE_TYPES = {"maincb", "rcd", "rcbo", "outcb"}
    connections = netlist.get("connections", [])
    if connections:
        pin_conns: dict[str, list[dict]] = {}
        for conn in connections:
            if conn.get("wire_type") in ("L", "L1", "L2", "L3", None):
                src_key = f"{conn['src_component']}.{conn['src_pin']}"
                dst_key = f"{conn['dst_component']}.{conn['dst_pin']}"
                pin_conns.setdefault(src_key, []).append(conn)
                pin_conns.setdefault(dst_key, []).append(conn)

        net_comps = netlist.get("components", {})
        net_load_ids = [cid for cid, c in net_comps.items() if c.get("type") == "loads" or get_base_type(cid) == "loads"]
        if not net_load_ids and comp_ids:
            net_load_ids = [cid for cid in comp_ids if get_base_type(cid) == "loads"]

        supply_keys = [
            f"{cid}.{p}" for cid in comp_ids if get_base_type(cid) == "supply"
            for p in ["L_out", "L1_out", "L2_out", "L3_out"]
        ]

        unprotected_loads = set()
        for load_id in net_load_ids:
            path_found = False
            protected_path_found = False

            for s_key in supply_keys:
                if s_key not in pin_conns:
                    continue
                stack = [(s_key, set())]
                visited_pins = set([s_key])

                while stack:
                    curr_key, prot_seen = stack.pop()
                    curr_comp, curr_pin = curr_key.split(".", 1)
                    curr_base = get_base_type(curr_comp)

                    new_prot = set(prot_seen)
                    if curr_base in PROTECTIVE_BASE_TYPES:
                        new_prot.add(curr_base)

                    if curr_comp == load_id or (get_base_type(curr_comp) == "loads" and load_id in (curr_comp, "loads")):
                        path_found = True
                        if len(new_prot) > 0:
                            protected_path_found = True
                            break

                    for conn in pin_conns.get(curr_key, []):
                        next_src = f"{conn['src_component']}.{conn['src_pin']}"
                        next_dst = f"{conn['dst_component']}.{conn['dst_pin']}"
                        next_key = next_dst if curr_key == next_src else next_src

                        if next_key not in visited_pins:
                            visited_pins.add(next_key)
                            next_comp, next_pin = next_key.split(".", 1)
                            next_base = get_base_type(next_comp)

                            if next_base in ["maincb", "rcd", "rcbo", "outcb", "bus", "nbar", "ebar"]:
                                peer_suffix = "_out" if next_pin.endswith("_in") else "_in"
                                peer_base = next_pin.split("_")[0]
                                peer_pin = f"{peer_base}{peer_suffix}"
                                peer_key = f"{next_comp}.{peer_pin}"
                                stack.append((peer_key, new_prot))
                            else:
                                stack.append((next_key, new_prot))

                if protected_path_found:
                    break

            if path_found and not protected_path_found:
                unprotected_loads.add(load_id)
            elif not has_maincb and not any(get_base_type(c) in PROTECTIVE_BASE_TYPES for c in comp_ids):
                unprotected_loads.add(load_id)

        for load_id in sorted(unprotected_loads):
            findings.append(ERCFinding(
                code="ERC-007",
                severity="ERROR",
                message=f"Load '{load_id}' bypasses all protective devices and is connected directly to supply.",
                components=[load_id]
            ))
    elif not has_maincb and not any(get_base_type(c) in PROTECTIVE_BASE_TYPES for c in comp_ids):
        load_cids = [cid for cid in comp_ids if get_base_type(cid) == "loads"]
        for load_id in load_cids:
            findings.append(ERCFinding(
                code="ERC-007",
                severity="ERROR",
                message=f"Load '{load_id}' bypasses all protective devices and is connected directly to supply.",
                components=[load_id]
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-008  |  Tier 3 — Topology Sanity  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # A radial distribution panel must have a strict tree topology — no feedback
    # loops.  A cycle means current has a path that returns to an upstream node,
    # which is physically impossible in a correctly drawn single-source panel and
    # indicates a wiring error (e.g. a branch breaker output feeding back into the
    # main breaker input).
    #
    # Algorithm: iterative DFS with a path-stack (not just a visited set).
    #   • Build a directed adjacency list from all netlist connections plus
    #     component-internal _in → _out pass-through edges for:
    #       maincb, rcd, rcbo, outcb, nbar, ebar, loads (single _out pin)
    #       bus  (L_in → L1_out, L2_out, L3_out)
    #   • For each unvisited starting pin, walk forward.
    #   • If a pin already on the current path stack is encountered again, a
    #     cycle exists.  All component IDs on the cycle path are collected.
    #
    # Only one ERC-008 finding is emitted per diagram (listing all cycling
    # components), because a single cycle may touch many pins.
    # -------------------------------------------------------------------------
    if connections:
        adj: dict[str, set[str]] = {}
        for conn in connections:
            src_key = f"{conn['src_component'].lower()}.{conn['src_pin']}"
            dst_key = f"{conn['dst_component'].lower()}.{conn['dst_pin']}"
            adj.setdefault(src_key, set()).add(dst_key)
            
            for c_key in (src_key, dst_key):
                c_comp, c_pin = c_key.split(".", 1)
                c_base = get_base_type(c_comp)
                if c_base in ["maincb", "rcd", "rcbo", "outcb", "bus", "nbar", "ebar", "loads"]:
                    if c_pin.endswith("_in"):
                        peer_base = c_pin.split("_")[0]
                        if c_base == "bus":
                            for suffix in ["", "1", "2", "3"]:
                                peer_key = f"{c_comp}.{peer_base}{suffix}_out"
                                adj.setdefault(c_key, set()).add(peer_key)
                        else:
                            peer_key = f"{c_comp}.{peer_base}_out"
                            adj.setdefault(c_key, set()).add(peer_key)

        cycle_detected = False
        cycle_comps = set()
        all_pin_keys = list(adj.keys())
        visited_global = set()

        for start_pin in all_pin_keys:
            if start_pin in visited_global:
                continue
            path_stack = []
            path_set = set()

            def dfs_cycle(curr_pin):
                nonlocal cycle_detected
                visited_global.add(curr_pin)
                path_stack.append(curr_pin)
                path_set.add(curr_pin)

                for nxt in adj.get(curr_pin, []):
                    if nxt in path_set:
                        cycle_detected = True
                        cycle_idx = path_stack.index(nxt)
                        for p in path_stack[cycle_idx:]:
                            cycle_comps.add(p.split(".", 1)[0])
                    elif nxt not in visited_global:
                        dfs_cycle(nxt)

                path_set.remove(curr_pin)
                path_stack.pop()

            dfs_cycle(start_pin)

        if cycle_detected:
            cycle_list = sorted(list(cycle_comps))
            findings.append(ERCFinding(
                code="ERC-008",
                severity="ERROR",
                message="Wiring graph contains a cyclic connection (loop detected in distribution path).",
                components=cycle_list
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-009  |  Tier 3 — Topology Sanity  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # Every component that is declared in parsed_data["components"] must appear
    # in at least one netlist connection (as src_component or dst_component).
    # A component with zero connections cannot carry current and represents either
    # an accidentally added component or a wiring omission.
    #
    # Special cases handled:
    #   • "loads" placeholder  →  mapped to its expanded child IDs (load_1, load_2
    #     …) before checking.  If ANY load_N child appears in connections, the
    #     parent "loads" is considered connected.  This prevents false positives
    #     when the netlist expands the placeholder.
    #   • "outcb" placeholder  →  same group-membership check using get_base_type.
    #
    # Typical trigger: a spare / unwired terminal block or a component added to
    # parsed_data by the prompt parser but never wired by ensure_connections()
    # (e.g. "spare_block" components detected by the spare keyword in the prompt).
    # -------------------------------------------------------------------------
    connected_cids = set()
    for conn in connections:
        connected_cids.add(conn["src_component"].lower())
        connected_cids.add(conn["dst_component"].lower())

    for cid, label in comp_list:
        cid_lower = cid.lower()
        base_t = get_base_type(cid_lower)
        
        is_connected = False
        if cid_lower in connected_cids:
            is_connected = True
        elif base_t == "loads":
            is_connected = any(
                get_base_type(cc) == "loads" or cc.startswith("load")
                for cc in connected_cids
            )
        elif base_t == "outcb":
            is_connected = any(
                get_base_type(cc) == "outcb" or cc.startswith("outcb")
                for cc in connected_cids
            )

        if not is_connected:
            findings.append(ERCFinding(
                code="ERC-009",
                severity="ERROR",
                message=f"Component '{cid}' ({label}) is declared but has zero connections in netlist (orphaned component).",
                components=[cid]
            ))

    # -------------------------------------------------------------------------
    # Rule ERC-010  |  Tier 3 — Topology Sanity  |  Severity: ERROR
    # -------------------------------------------------------------------------
    # Component IDs must be globally unique within a diagram at two levels:
    #
    # Level 1 — Exact string uniqueness:
    #   The same ID string (case-insensitive) must not appear more than once in
    #   parsed_data["components"].  Duplicate IDs produce ambiguous netlist entries.
    #
    # Level 2 — Normalised base-type singleton uniqueness:
    #   Certain component classes are singletons — only one instance is valid per
    #   diagram (supply, maincb, rcd, bus, nbar, ebar, loads).  A component whose
    #   get_base_type() resolves to one of these classes collides with any existing
    #   component already registered under the same base type, even if the raw ID
    #   strings differ (e.g. "loads_1" collides with "loads" because both resolve
    #   to base type "loads").
    #
    # SINGLETON_BASE_TYPES = {"supply", "maincb", "rcd", "bus", "nbar", "ebar", "loads"}
    #
    # Note: "outcb" is intentionally excluded from singletons — multiple branch
    # breakers (outcb_1, outcb_2, …) are expected and valid.
    # -------------------------------------------------------------------------
    seen_exact_ids = set()
    seen_singleton_base_types = {}

    for cid, label in comp_list:
        cid_lower = cid.lower()
        base_t = get_base_type(cid_lower)

        if cid_lower in seen_exact_ids:
            findings.append(ERCFinding(
                code="ERC-010",
                severity="ERROR",
                message=f"Duplicate component ID '{cid}' detected in diagram components.",
                components=[cid]
            ))
        else:
            seen_exact_ids.add(cid_lower)

        if base_t in {"supply", "maincb", "rcd", "bus", "nbar", "ebar", "loads"}:
            if base_t in seen_singleton_base_types and seen_singleton_base_types[base_t] != cid_lower:
                prev_id = seen_singleton_base_types[base_t]
                findings.append(ERCFinding(
                    code="ERC-010",
                    severity="ERROR",
                    message=f"Component ID '{cid}' collides with existing component '{prev_id}' under {base_t} normalization.",
                    components=[cid, prev_id]
                ))
            else:
                seen_singleton_base_types[base_t] = cid_lower

    return findings
