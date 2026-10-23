"""Faithful shared rift producer reconstruction, on accepted combat previews.

Native Current Wave owns original scaling and death-orb subscriptions. The
missing server caller is reconstructed; no damage, probability or area effect
is replaced with a local formula.
"""
from .combat_definitions import state_profile
from .combat_effect_dispatch import EffectInvocation
from .combat_state_handler import StateCarrierContext
from .combat_native_timing_context import native_time_payload
from .rift_native_gameplay_policy import POLICY


def policy(fight):
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return None
    document = state.get("policy", {}).get("native_gameplay")
    if document is None or document.get("enabled") is not True:
        return None
    if document.get("policy") != POLICY:
        raise ValueError("Unreviewed native rift producer policy")
    return document


def install_wave_state(dispatcher, *, actor_ids, wave):
    """Install the native wave carrier once on each newly admitted original NPC.

    The owner discards the entire preview/outbox on failure. Existing actors'
    states are never reinitialized when admitting later waves.
    """
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None:
        return False
    state = fight.rift_wave_state
    ids = tuple(actor_ids)
    receipts = state.setdefault("native_wave_entries", {})
    if wave == state["wave"]:
        expected = set(state["wave_actor_ids"])
    elif (
        isinstance(state.get("pending_wave"), dict)
        and wave == state["wave"] + 1
        and state["pending_wave"]["completed_wave"] == state["wave"]
    ):
        # The ordinary birth path registered the complete next roster before
        # acknowledgement updates wave_actor_ids. Every older original already
        # has an immutable entry receipt; summons never enter rift_monsters.
        expected = set(getattr(fight, "rift_monsters", {})) - {
            int(uid) for uid in receipts
        }
    else:
        expected = set()
    if (
        type(wave) is not int
        or wave < 1
        or not ids
        or len(set(ids)) != len(ids)
        or set(ids) != expected
        or any(
            uid not in fight.actors
            or fight.actors[uid].controlled
            or fight.actors[uid].team != 1
            for uid in ids
        )
    ):
        raise ValueError("Native rift wave entry differs from its accepted roster")
    reference = document["wave_state"]
    handler = dispatcher.native_state_handler
    definition = handler.catalog["states"].get(str(reference))
    if definition is None:
        raise ValueError("Missing original native rift wave state")
    grade = min(wave, definition["maximum_level"])
    profile = state_profile(handler.catalog, reference, grade)
    if profile["duration"] != -1 or profile["realtime_duration"] != 0:
        raise ValueError("Native wave carrier requires its original indefinite clock")
    changed = False
    for uid in ids:
        receipt = dict(reference=reference, level=grade, wave=wave, policy=POLICY)
        previous = receipts.get(str(uid))
        if previous is not None:
            if previous != receipt:
                raise ValueError(
                    "Native rift wave entry replay changed its original grade"
                )
            continue
        actor = fight.actors[uid]
        if any(entry.reference == reference for entry in actor.state_ledger.entries):
            raise ValueError("Unattested native rift wave carrier already exists")
        invocation = EffectInvocation(
            2226,
            grade,
            uid,
            uid,
            actor.position,
            native_retained_container={"present": False},
        )
        context = StateCarrierContext(
            -1,
            0,
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=0),
        )
        if not dispatcher.native_retention.apply_state_reference(
            handler,
            invocation,
            reference,
            grade,
            carrier_context=context,
        ):
            raise ValueError("Native rift wave carrier was not installed")
        receipts[str(uid)] = receipt
        changed = True
    return changed


def register_artifact_group(fight, *, wave, area_uids):
    """Freeze an actually created native choice group before public delivery.

    This does not choose rarity, invent a spawn cadence, or construct areas.
    Those producers require a separately recovered or declared source policy.
    """
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        raise ValueError("Rift artifact production is not enabled")
    state = fight.rift_wave_state
    settings = document["artifacts"]
    count = settings[
        "ultimate_count"
        if state["catalog"]["type"] == "ULTIMATE_INFINITE_WAVE"
        else "classic_count"
    ]
    ids = tuple(area_uids)
    areas = getattr(fight, "native_effect_areas", {})
    allowed = {ref for pool in settings["pools"].values() for ref in pool}
    if (
        type(wave) is not int
        or wave < 1
        or len(ids) != count
        or len(set(ids)) != count
        or any(
            uid not in areas
            or areas[uid].get("native_area_contract") != "faM"
            or areas[uid]["reference"] not in allowed
            for uid in ids
        )
    ):
        raise ValueError("Missing actual native rift artifact choice group")
    groups = state.setdefault("native_artifact_groups", {})
    key = str(wave)
    original = {str(uid): areas[uid]["reference"] for uid in ids}
    existing = groups.get(key)
    if existing is not None:
        if existing["original"] != original:
            raise ValueError("Rift artifact group replay changed native identities")
        return existing
    if any(str(uid) in group["original"] for uid in ids for group in groups.values()):
        raise ValueError("Native rift artifact belongs to another choice group")
    group = dict(original=original, remaining=list(ids), assignments=[])
    groups[key] = group
    return group


def apply_artifact_collection(dispatcher, *, area_row, actor_id):
    """Pair a real collected artifact with one random remaining enemy artifact.

    Invoked only after the original native contact children succeed. Both this
    receipt and the original native children belong to the same preview/RNG.
    Automatic enemy assignment executes native 2243 without another contact
    callback, avoiding recursive double pairing.
    """
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return False
    uid = area_row["uid"]
    groups = [
        group
        for group in fight.rift_wave_state.get("native_artifact_groups", {}).values()
        if str(uid) in group["original"]
    ]
    if not groups:
        return False  # Another native artifact producer owns this area.
    if len(groups) != 1:
        raise ValueError("Ambiguous native rift artifact choice group")
    group = groups[0]
    if uid not in group["remaining"]:
        return False  # A committed contact must not distribute another pair.
    collector = fight.actors.get(actor_id)
    if (
        collector is None
        or not fight._in_play(collector)
        or collector.team != 0
        or group["original"][str(uid)] != area_row["reference"]
        or area_row.get("native_area_contract") != "faM"
    ):
        raise ValueError("Rift artifact contact has no actual living player")
    remaining = [value for value in group["remaining"] if value != uid]
    enemies = sorted(
        (
            actor
            for actor in fight.actors.values()
            if actor.team == 1 and fight._in_play(actor)
        ),
        key=lambda actor: actor.id,
    )
    if not remaining or not enemies:
        raise ValueError(
            "Rift artifact pair requires a remaining artifact and living enemy"
        )
    rng = dispatcher.group_random
    if not callable(getattr(rng, "randrange", None)):
        raise ValueError(
            "Rift artifact assignment requires the accepted transaction RNG"
        )
    paired = remaining[rng.randrange(len(remaining))]
    group["remaining"] = [value for value in remaining if value != paired]
    group["assignments"].append(
        dict(
            collected=uid, collector=actor_id, opponent=paired, recipient=enemies[0].id
        )
    )
    if not dispatcher.native_area_events.assign_artifact(paired, enemies[0].id):
        raise ValueError("Paired native rift artifact was not assigned")
    return True
