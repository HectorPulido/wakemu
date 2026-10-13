"""Wakemu finality barrier for actual owned, scheduled same-PV HP restoration.

Native source proves the retained runner, transmitted PV, KO0/final2 and eXO
operation. Waiting for that runner before choosing final2 is server policy.
"""
SOURCE = "wakemu.owned-pending-restoration.v1"


def annotate_scheduled_restoration(fight, effects, uid):
    from .combat_effect_groups import decode_group_mode
    from .combat_definitions import effect_profile
    from .combat_native_delay_queue import validate

    validate(fight.native_delay_queue)
    owned = fight.native_owned_group_effects[uid]
    handles = [row for row in fight.native_delay_queue["entries"] if row["uid"] == uid]
    if len(handles) != 1 or handles[0]["invocation"] != owned["invocation"]:
        raise ValueError("Restoration barrier requires actual scheduled owned Qe")
    invocation = owned["invocation"]
    target = invocation.get("target_id")
    if target not in fight.actors or owned.get("native_delayed") is not True:
        return False
    level = invocation["level"]
    found = []

    def visit(reference, ancestors):
        if reference in ancestors or len(ancestors) >= 128:
            raise ValueError("Invalid pending restoration effect graph")
        effect = effects.get(str(reference))
        if effect is None:
            raise ValueError("Missing pending restoration effect definition")
        if not effect["minimum_level"] <= level <= effect["maximum_level"]:
            return
        values = effect_profile(effect, level)
        if effect["effect_class"] == 196:
            # eXO positive current-HP restoration, not a catalogue capability.
            if values["parameters"] and values["parameters"][0] > 0:
                found.append(reference)
            return
        if effect["effect_class"] != 330:
            return
        mode = decode_group_mode(
            values["parameters"],
            raw_target_parameter=(
                effect["parameters"][4] if len(values["parameters"]) >= 3 else None
            ),
        )
        if not mode.on_target or not mode.transmit_target or mode.actor_rebind:
            return
        for child in effect["children"]:
            visit(child, (*ancestors, reference))

    visit(invocation["reference"], ())
    if not found:
        return False
    owned["wakemu_pending_restoration"] = dict(
        source=SOURCE, target_id=target, restore_refs=sorted(set(found))
    )
    return True


def pending_restoration_uids(fight, target_id):
    queue = getattr(fight, "native_delay_queue", None)
    if queue is None:
        return ()
    from .combat_native_delay_queue import validate

    validate(queue)
    result = []
    for handle in queue["entries"]:
        owned = fight.native_owned_group_effects.get(handle["uid"])
        if owned is None:
            continue  # Actual Qf cancellation will discard its stale handle.
        proof = owned.get("wakemu_pending_restoration")
        if proof is None:
            continue
        if (
            proof.get("source") != SOURCE
            or not isinstance(proof.get("restore_refs"), list)
            or not proof["restore_refs"]
            or any(type(ref) is not int for ref in proof["restore_refs"])
            or owned.get("native_delayed") is not True
            or owned["invocation"] != handle["invocation"]
            or proof.get("target_id") != owned["invocation"].get("target_id")
        ):
            raise ValueError("Invalid owned pending restoration authority")
        if proof["target_id"] == target_id:
            result.append(handle["uid"])
    return tuple(result)


def settle_pending_restoration_deaths(runtime):
    """Exhaustion/cancellation uses the ordinary explicit final-death publisher."""
    from .combat_death import death_messages

    packets = []
    for actor in tuple(runtime.fight.actors.values()):
        status = getattr(actor, "native_death_status", None)
        marker = status.get("pending_restoration") if isinstance(status, dict) else None
        if marker is None:
            continue
        if marker != SOURCE:
            raise ValueError("Unknown pending restoration finality policy")
        if actor.hp > 0:
            status.pop("pending_restoration")
        elif not pending_restoration_uids(runtime.fight, actor.id):
            # Remove only after normal publication succeeds. State2 is explicit:
            # the default barrier must never override this terminal decision.
            packets.extend(death_messages(runtime, actor.id, fighter_state=2))
            actor.native_death_status.pop("pending_restoration", None)
    return tuple(packets)
