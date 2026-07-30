"""
Shim module forwarding all pin_model symbols to ECD.electrical.pin_model.
"""
from ECD.electrical.pin_model import *
from ECD.electrical.pin_model import (
    determine_phase_mode,
    get_base_type,
    get_pin_position,
    compute_component_positions,
    generate_netlist,
    validate_netlist,
)
