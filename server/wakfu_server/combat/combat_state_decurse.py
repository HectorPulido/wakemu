"""Native eZi321 decurse;315 is eYQ area creation and is not a removal.

Runs only inside the enclosing spell transaction preview. Reapplication is an
explicit audited callback, preserving the native decurse source rather than
silently reusing the original caster/UID or child magnitudes.
"""
import json
from .paths import DATA_ROOT
from .combat_effect_dispatch import UnsupportedEffectExecution
from .combat_effect_removal import running_effect_removal

RULES = json.loads((DATA_ROOT / "state-decurse-rules.json").read_text())


class NativeStateDecurseHandler:
    def __init__(
        self, fight, packets, catalog, *, action_id, state_handler, reapply_state=None
    ):
        self.fight, self.packets, self.catalog = fight, packets, catalog
        self.action_id, self.state_handler, self.reapply_state = (
            action_id,
            state_handler,
            reapply_state,
        )
        if state_handler.fight is not fight:
            raise ValueError("State handler belongs to another preview")

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 321:
            raise UnsupportedEffectExecution(
                "Only native state decurse321 is supported"
            )
        parameters = values["parameters"]
        if len(parameters) not in (1, 2) or any(type(v) is not int for v in parameters):
            raise UnsupportedEffectExecution("Unsupported native decurse parameters")
        reference = parameters[0]
        target = self.fight.actors.get(invocation.target_id)
        if target is None:
            return False
        eligible = tuple(
            entry
            for entry in target.state_ledger.entries
            if entry.reference == reference
            and (
                not (
                    self.catalog["states"][str(reference)]["protected"]
                    if entry.protected is None
                    else entry.protected
                )
                or reference in RULES["protected_whitelist"]
            )
        )
        if not eligible:
            return False
        remainder = eligible[-1].level - parameters[1] if len(parameters) == 2 else 0
        # Native casts resulting level to signed short when constructing fyW.
        remainder = ((remainder + 32768) % 65536) - 32768
        if remainder > 0 and reference in RULES["selective_child_states"]:
            raise UnsupportedEffectExecution(
                "Selective native state children require owned beneficial classification"
            )
        if remainder > 0 and not callable(self.reapply_state):
            raise UnsupportedEffectExecution(
                "Reduced state requires audited carrier reapplication"
            )
        for entry in eligible:
            if entry.uid not in self.fight.state_wire_payloads:
                raise UnsupportedEffectExecution(
                    "Missing owned state payload for decurse"
                )
        for entry in eligible:
            payload = bytes.fromhex(self.fight.state_wire_payloads[entry.uid])
            self.state_handler.remove_state_children(entry.uid)
            target.state_ledger.remove(entry.uid)
            del self.fight.state_wire_payloads[entry.uid]
            self.packets.append(
                (
                    13560,
                    running_effect_removal(
                        self.fight.id,
                        self.action_id,
                        effect_class=310,
                        target_id=entry.target_id,
                        uid=entry.uid,
                        running_effect_payload=payload,
                    ),
                )
            )
            self.fight._event(
                "state_removed",
                actor_id=entry.target_id,
                uid=entry.uid,
                reference=entry.reference,
                source="decurse321",
            )
        if remainder > 0:
            self.reapply_state(effect, reference, remainder, invocation)
        return True
