"""Original eWB.rBF definition binding and eXD.fOQ first-group execution."""
from dataclasses import replace
from .combat_carrying import _pairs, carrying_relations
from .combat_execution_context import constructed_execution_context


def execute_carry_release(fight, effects, execute, invocation, actor):
    if not carrying_relations(fight, actor)["is_carrying"]:
        return False
    pair = _pairs(fight)[actor.id]
    reference = pair.source_reference
    if type(reference) is not int or reference <= 0:
        raise ValueError("Missing actual eWB carry-definition binding")
    definition = effects.get(str(reference))
    if definition is None or definition.get("effect_class") != 334:
        raise ValueError("Missing original carry definition/group authority")
    children = definition.get("children")
    if not isinstance(children, (tuple, list)) or any(
        type(child) is not int or child <= 0 for child in children
    ):
        raise ValueError("Missing native ordered carry-release effect group")
    # Native missing/empty fyD returns without severing the relation.
    if not children:
        return False
    if str(children[0]) not in effects:
        raise ValueError("Missing original first carry-release effect")
    context = replace(constructed_execution_context(), bypass_probability=True)
    return execute(
        replace(
            invocation,
            reference=children[0],
            caster_id=actor.id,
            target_id=None,
            cell=tuple(actor.position),
            base_uid=None,
            native_running_uid=None,
            native_context_hex=context.payload().hex(),
            native_trigger_context=None,
            native_cast_boundary_context=None,
            native_value_scope=None,
            native_explicit_target=False,
            wakemu_fresh_child_selection=True,
            native_target_cell_argument=False,
        )
    )
