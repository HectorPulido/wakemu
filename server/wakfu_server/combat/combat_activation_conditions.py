"""Native eNh/eNi activation and ePd/ePc triggering-runner predicates."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class NativeActivationSnapshot:
    """Explicit current fbX.bah PZ, distinct from the triggering effect."""

    present: bool
    spell_id: int | None = None  # PZ.ayn; may describe a non-spell activation.
    container_present: bool | None = None  # PZ.baR != null.
    element: int | None = None  # PZ.baP.
    is_spell_activation: bool | None = None  # Actual instanceof fcS.
    stasis: bool | None = None  # fcS.e(fyU.tyc), not a guessed element.

    def evaluate(self, name, argument=None):
        if type(self.present) is not bool:
            raise ValueError("Unknown native activation presence")
        if not self.present:
            return False
        if name == "IsActivatedBySpell":
            if argument == -1:
                if type(self.container_present) is not bool:
                    raise ValueError("Missing actual activation container presence")
                return self.container_present
            if type(self.spell_id) is not int:
                raise ValueError("Missing actual activation PZ.ayn")
            return self.spell_id == argument
        if name == "IsActivatedByElement":
            if self.is_spell_activation is not True:
                raise ValueError("Native element activation requires actual fcS")
            if type(self.stasis) is not bool:
                raise ValueError("Missing actual activation stasis flag")
            if self.stasis:
                # eVg.rpk.aKg is native STASIS; verified by the original enum.
                return argument == 6
            if type(self.element) is not int:
                raise ValueError("Missing actual activation PZ.baP")
            return self.element == argument
        raise ValueError("Unknown native activation predicate")


def evaluate_source_predicate(name, context):
    if context.triggering_effect_present is False:
        return False
    if context.triggering_effect_present is not True:
        raise ValueError("Missing actual native triggering effect presence")
    if name == "IsTriggeringEffectCritical":
        if context.triggering_effect_definition_present is False:
            return False
        if context.triggering_effect_definition_present is not True:
            raise ValueError("Missing actual triggering PK presence")
        variant = context.triggering_effect_variant
        if type(variant) is not int:
            raise ValueError("Missing actual triggering PK variant")
        return bool(variant & 1)
    status = context.triggering_effect_execution_status
    if status is None and type(context.triggering_effect_blocked) is bool:
        return context.triggering_effect_blocked
    if type(status) is not int or not -128 <= status <= 127:
        raise ValueError("Missing actual triggering runner execution status")
    return status == 7


def current_activation(fight, name, argument):
    from .combat_active_spell import active_spell_id, active_spell_container

    reference = active_spell_id(fight)
    if reference == -1:
        return NativeActivationSnapshot(False).evaluate(name, argument)
    if name == "IsActivatedBySpell" and argument != -1:
        return reference == argument
    container = active_spell_container(fight)
    if name == "IsActivatedBySpell":
        return NativeActivationSnapshot(
            True, container_present=container["present"]
        ).evaluate(name, argument)
    row = _activation_catalog().get(str(reference))
    if not isinstance(row, dict):
        raise ValueError("Missing actual native spell activation metadata")
    return NativeActivationSnapshot(
        True,
        spell_id=reference,
        container_present=True,
        element=row.get("native_element"),
        is_spell_activation=True,
        stasis=row.get("stasis"),
    ).evaluate(name, argument)


@lru_cache(maxsize=1)
def _activation_catalog():
    import json
    from wakfu_server.paths import DATA_ROOT

    return protocol_catalog.load(DATA_ROOT / "native-spell-activation.json")["spells"]
