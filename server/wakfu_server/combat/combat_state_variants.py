"""eZk.c's fyW.guW gate, independent of the enclosing spell's branch.

ExportStateDecurseRules exhaustively exports states for which guW is true.
For the others eZk iterates every child, even during a critical spell. Selective
states use the carrier's actual rHA (Additional19), never the outer cast flag.
"""
from .combat_state_decurse import RULES
from .combat_native_container import resolve_state_container, resolve_state_wire_payload
from .combat_effect_removal import _identity_fields


def state_child_variant_mode(fight, state_uid):
    state = resolve_state_container(fight, state_uid)
    if state.reference not in RULES["selective_child_states"]:
        return "ALL"
    payload = resolve_state_wire_payload(fight, state_uid)
    if not isinstance(payload, str):
        raise ValueError("Missing selective state carrier critical authority")
    messages = {}
    _identity_fields(bytes.fromhex(payload), messages=messages)
    flags = _identity_fields(messages.get(8, b""), integer_fields=(19,))
    if flags.get(19) not in (0, 1):
        raise ValueError("Missing native state rHA critical flag")
    return "CRITICALS_ONLY" if flags[19] else "EFFECTS_ONLY"
