"""Atomic due-clock removal of owned effects, including state-owned children."""
from copy import deepcopy
import json
from .combat_state_timing import StateTimer
from .combat_stat_handler import NativeStatHandler
from .combat_effect_removal import running_effect_removal
from .paths import DATA_ROOT
from .combat_retained_runtime import remove_owned_group, remove_owned_stat


def _due(timer, actor_id, round_number, phase, round_cleanup):
    return timer is not None and (
        timer.expires_at_round_cleanup(round_number)
        if round_cleanup
        else timer.expires_on(actor_id=actor_id, round_number=round_number, phase=phase)
    )


def prepare_timed_expiration(
    fight,
    *,
    actor_id,
    round_number,
    phase,
    action_id,
    round_cleanup=False,
    registry=None
):
    """Return successful preview/outbox; no mutation or emission on failure.

    Call round_cleanup once on a new round, then start/end for the actual actor.
    No timer is inferred from durations or from a missing owned metadata record.
    """
    if (
        phase not in ("start", "end")
        or type(round_number) is not int
        or not 1 <= round_number < 32768
    ):
        raise ValueError("Explicit native clock phase/round required")
    if actor_id not in fight.actors or fight.phase != "active":
        raise ValueError("Invalid native expiration actor/fight")
    preview = deepcopy(fight)
    packets = []
    if registry is None:
        registry = json.loads(
            (DATA_ROOT / "effect-characteristic-registry.json").read_text()
        )
    handler = NativeStatHandler(
        preview,
        packets,
        registry,
        action_id=action_id,
        allocate_uid=lambda: None,
        context=lambda *a: None,
    )
    due = []
    for actor in preview.actors.values():
        for entry in actor.state_ledger.entries:
            if _due(entry.timer, actor_id, round_number, phase, round_cleanup):
                due.append((entry.uid, "state", actor.id))
    for uid, entry in preview.owned_stat_effects.items():
        timer = entry.get("timer")
        if timer is not None:
            timer = StateTimer(**timer)
            if (
                type(timer.actor_id) is not int
                or timer.actor_id not in preview.actors
                or type(timer.expiration_round) is not int
                or not -32768 <= timer.expiration_round <= 32767
                or timer.phase not in ("start", "end")
            ):
                raise ValueError("Invalid owned native effect timer")
            if _due(timer, actor_id, round_number, phase, round_cleanup):
                due.append((uid, "stat", entry["target_id"]))
    for uid, entry in preview.native_owned_group_effects.items():
        timer = entry.get("timer")
        if timer is not None and _due(
            StateTimer(**timer), actor_id, round_number, phase, round_cleanup
        ):
            due.append((uid, "group", entry["target_id"]))
    # Native TC stores callbacks in application order. The local owned UID
    # sequence follows application order; state carriers precede their children.
    with preview.effect_resolution():
        order = {uid: index for index, uid in enumerate(preview.native_retained_order)}
        ordered = (
            sorted(due, key=lambda item: order.get(item[0], item[0]))
            if preview.native_retained_tracking and order
            else sorted(due)
        )
        for uid, kind, target_id in ordered:
            if kind == "group":
                if uid in preview.native_owned_group_effects:
                    remove_owned_group(preview, packets, action_id=action_id, uid=uid)
                continue
            if kind == "stat":
                if uid in preview.owned_stat_effects:
                    remove_owned_stat(handler, uid)
                continue
            actor = preview.actors[target_id]
            entries = [
                entry for entry in actor.state_ledger.entries if entry.uid == uid
            ]
            if not entries:
                continue
            payload = preview.state_wire_payloads.get(uid)
            if payload is None:
                raise ValueError("Missing owned expiring state carrier payload")
            for child_uid, child in tuple(preview.owned_stat_effects.items()):
                if child.get("state_uid") == uid:
                    remove_owned_stat(handler, child_uid)
            for child_uid, child in tuple(preview.native_owned_group_effects.items()):
                if child.get("state_uid") == uid:
                    remove_owned_group(
                        preview, packets, action_id=action_id, uid=child_uid
                    )
            packet = running_effect_removal(
                preview.id,
                action_id,
                effect_class=310,
                target_id=target_id,
                uid=uid,
                running_effect_payload=bytes.fromhex(payload),
            )
            actor.state_ledger.remove(uid)
            del preview.state_wire_payloads[uid]
            preview._event(
                "state_removed",
                actor_id=target_id,
                uid=uid,
                state_id=entries[0].reference,
                reason="expiration",
            )
            packets.append((13560, packet))
    live = (
        set(preview.owned_stat_effects)
        | set(preview.state_wire_payloads)
        | set(preview.native_owned_group_effects)
    )
    preview.native_retained_records = {
        uid: row for uid, row in preview.native_retained_records.items() if uid in live
    }
    preview.native_retained_order[:] = [
        uid for uid in preview.native_retained_order if uid in live
    ]
    return preview, packets


def expire_timed_effects(fight, **clock):
    preview, packets = prepare_timed_expiration(fight, **clock)
    if set(fight.actors) != set(preview.actors):
        raise ValueError("Expiration changed actor roster")
    for identity, actor in preview.actors.items():
        fight.actors[identity].__dict__.clear()
        fight.actors[identity].__dict__.update(actor.__dict__)
    for key, value in preview.__dict__.items():
        if key != "actors":
            setattr(fight, key, value)
    return packets
