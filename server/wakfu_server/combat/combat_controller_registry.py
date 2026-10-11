"""Actual fdt registration/controller state, separate from original ownership.

Only registration producers may initialize this table. Controller transfer does
not rewrite summon ownership, original-controller authority or original team.
"""

SOURCE = "fdt.a.fdy.saH_saJ_saF_ebh.v1"


def _actor(fight, identity):
    from .combat_native_actor_lookup import native_actor

    if type(identity) is not int or not -(1 << 63) <= identity < (1 << 63):
        raise ValueError("Invalid actual fdt fighter identity")
    actor = native_actor(fight, identity)
    if actor is None or fight.actors.get(identity) is not actor:
        raise ValueError("Missing actual registered fdt fighter")
    return actor


def _team(value):
    if type(value) is not int or not -128 <= value < 128:
        raise ValueError("Invalid native fdy signed team")
    return value


def initialize_controller_registry(fight):
    if hasattr(fight, "native_controller_registry"):
        raise ValueError("Native fdt controller registry already initialized")
    fight.native_controller_registry = dict(source=SOURCE, fighters={})


def _state(fight):
    state = getattr(fight, "native_controller_registry", None)
    if (
        not isinstance(state, dict)
        or set(state) != {"source", "fighters"}
        or state["source"] != SOURCE
        or not isinstance(state["fighters"], dict)
    ):
        raise ValueError("Missing actual fdt controller registration producer")
    return state["fighters"]


def register_native_controller(fight, identity, *, team, controller_id):
    """fdt.a creates fdy with explicit serialized team/controller operands."""
    _actor(fight, identity)
    _actor(fight, controller_id)
    team = _team(team)
    rows = _state(fight)
    if str(identity) in rows:
        raise ValueError("Duplicate actual fdt controller registration")
    rows[str(identity)] = dict(
        original_controller=controller_id,
        current_controller=controller_id,
        original_team=team,
        current_team=team,
    )


def _row(fight, identity):
    _actor(fight, identity)
    row = _state(fight).get(str(identity))
    if not isinstance(row, dict) or set(row) != {
        "original_controller",
        "current_controller",
        "original_team",
        "current_team",
    }:
        raise ValueError("Missing actual fdy controller row")
    for key in ("original_controller", "current_controller"):
        value = row[key]
        if value is None and key == "current_controller":
            continue
        if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
            raise ValueError("Invalid native fdy controller")
    _team(row["original_team"])
    _team(row["current_team"])
    return row


def current_native_team(fight, identity):
    return _row(fight, identity)["current_team"]


def current_native_controller(fight, identity):
    return _row(fight, identity)["current_controller"]


def set_native_current_team(fight, identity, team):
    """fdy.au changes ebh only; original saF remains immutable."""
    _row(fight, identity)["current_team"] = _team(team)
    _actor(fight, identity).native_fight_affiliation = team


def transfer_native_controller(fight, identity, controller_id):
    """fdt.e samples the controller's CURRENT bcM at transfer time."""
    controller_team = current_native_team(fight, controller_id)
    row = _row(fight, identity)
    row["current_controller"], row["current_team"] = controller_id, controller_team
    _actor(fight, identity).native_fight_affiliation = controller_team


def restore_native_controller(fight, identity):
    """fdt.aX restores constructor originals, not the preceding transfer."""
    row = _row(fight, identity)
    row["current_controller"] = row["original_controller"]
    row["current_team"] = row["original_team"]
    _actor(fight, identity).native_fight_affiliation = row["original_team"]


def clear_native_controller(fight, identity):
    """fdt.aW clears the current relation and uses native team sentinel -1."""
    row = _row(fight, identity)
    row["current_controller"], row["current_team"] = None, -1
    _actor(fight, identity).native_fight_affiliation = -1


def unregister_native_controller(fight, identity):
    _row(fight, identity)
    del _state(fight)[str(identity)]


def current_controller_authority(fight, actor, metadata):
    """big.dpu/dnG resolves fdt.fXZ through registered saq, not ownership."""
    if not hasattr(fight, "native_controller_registry"):
        return metadata
    from dataclasses import replace

    identity = current_native_controller(fight, actor.id)
    if identity is not None and str(identity) not in _state(fight):
        identity = None  # fdt.P has no registered actor for the stored identity.
    return replace(metadata, targeting={**metadata.targeting, "dpu_id": identity})


def apply_native_controller_transfer(
    fight, caster_id, target_id, *, use_current_controller
):
    """eWD.c control transfer followed by preceding fqL snapshot/AI propagation."""
    if type(use_current_controller) is not bool:
        raise ValueError("Missing native eWD controller selection")
    caster, target = _actor(fight, caster_id), _actor(fight, target_id)
    previous_ai = getattr(target, "native_controlled_by_ai", None)
    caster_ai = getattr(caster, "native_controlled_by_ai", None)
    if type(previous_ai) is not bool or type(caster_ai) is not bool:
        raise ValueError("Missing actual eWD source/target fqL authority")
    controller_id = caster_id
    if use_current_controller:
        current = current_native_controller(fight, caster_id)
        if current is not None and str(current) in _state(fight):
            controller_id = current
    transfer_native_controller(fight, target_id, controller_id)
    if caster_ai:
        from .combat_ai_control import set_native_ai_control

        set_native_ai_control(target, True)
    return previous_ai


def remove_native_controller_transfer(fight, target_id, *, previous_ai):
    """eWD.bbR restores fdt originals and the captured preceding AI boolean."""
    target = _actor(fight, target_id)
    if type(previous_ai) is not bool:
        raise ValueError("Missing retained eWD preceding AI snapshot")
    from .combat_ai_control import set_native_ai_control

    if type(getattr(target, "native_controlled_by_ai", None)) is not bool:
        raise ValueError("Missing actual eWD target fqL authority")
    restore_native_controller(fight, target_id)
    set_native_ai_control(target, previous_ai)
