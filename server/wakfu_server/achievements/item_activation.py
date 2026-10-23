"""Activate an explicitly qualified item mission without granting objectives."""
from copy import deepcopy

from . import storage, wire
from .service import _owner


def activate(db, store, character, plan, *, source_uid):
    """Caller owns the item/lease transaction and validated native descriptor.

    These original missions are nonrecurring. Existing active/completed state
    is preserved; no implicit reset, tracking change, objective, or XP occurs.
    """
    _owner(db, character)
    identity = plan["definition_id"]
    if (
        plan["native_use_criterion"] != ""
        or plan["native_use_has_criteria"] is not False
        or plan["native_definition_availability"] != ""
        or plan["native_action_criterion"]
        not in ("", f"!IsAchievementActive({identity})")
        or plan["native_definition_criterion"].replace(" ", "")
        != f"GetRealLevel()>={plan['minimum_real_level']}"
    ):
        raise ValueError("Unqualified native item mission activation criteria")
    if character["level"] < plan["minimum_real_level"]:
        raise ValueError("The native mission requires a higher real level")
    if (
        plan["scope"] != "initial_activation_only"
        or plan["repeatable"] is not False
        or plan["duration"] != 0
        or plan["period"] != 0
    ):
        raise ValueError("Unsupported item mission lifecycle")
    before = storage.load_locked(db, character["id"])
    if identity in before["running"] or identity in before["completed"]:
        return dict(
            applied=False,
            packets=[],
            definition_id=identity,
            completed=[],
            new_objectives=[],
            xp_changed=False,
        )
    event_key = f"native-item-activation:{identity}"
    fact = dict(
        kind="native_item_mission_activation",
        definition_id=identity,
        action_id=plan["action_id"],
        item_ref=plan["item_ref"],
        source_uid=source_uid,
        real_level=character["level"],
    )
    if not storage.record_event(db, character["id"], event_key, fact):
        raise ValueError("Mission activation receipt exists without its retained state")
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {identity})
    storage.store(db, character["id"], after)
    packets = wire.changes(
        character["id"], before, after, [], [], int(store.now().timestamp() * 1000)
    )
    return dict(
        applied=True,
        packets=packets,
        definition_id=identity,
        completed=[],
        new_objectives=[],
        xp_changed=False,
    )
