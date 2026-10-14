"""Observe real eYZ execution separately from ordinary cast eligibility.

Observations become delivery receipts only when their exact application packet
appears in an explicitly supplied committed outbox. This changes no gameplay.
"""
from contextlib import contextmanager
from hashlib import sha256
import struct


def packet_identity(packet):
    from wakfu_server.combat_effect_removal import _identity_fields

    message, payload = packet
    if message != 12613 or len(payload) < 19:
        return None
    fight, action, ignored, status, family, size = struct.unpack(
        ">iiiBih", payload[:19]
    )
    if family != 426 or len(payload[19:]) != size:
        return None
    fields = _identity_fields(payload[19:])
    return fight, action, fields[1], fields[3]


def hp_state_snapshot(fight):
    """Read actual actor values; incomplete authority cannot prove an effect."""
    result = {}
    for identity, actor in fight.actors.items():
        hp = getattr(actor, "hp", None)
        ledger = getattr(actor, "state_ledger", None)
        entries = None if ledger is None else getattr(ledger, "entries", None)
        states = None
        if entries is not None:
            states = sorted((entry.reference, entry.level) for entry in entries)
            if any(type(v) is not int for row in states for v in row):
                raise ValueError("Invalid observed native state identity")
        result[identity] = dict(hp=hp if type(hp) is int else None, states=states)
    return result


def hp_state_delta(before, after):
    changed = []
    complete = True
    for identity in sorted(set(before) | set(after)):
        left, right = before.get(identity), after.get(identity)
        if (
            left is None
            or right is None
            or any(
                row[key] is None for row in (left, right) for key in ("hp", "states")
            )
        ):
            complete = False
            continue
        if left != right:
            changed.append(
                dict(
                    actor_id=identity,
                    hp_before=left["hp"],
                    hp_after=right["hp"],
                    hp_delta=right["hp"] - left["hp"],
                    states_before=left["states"],
                    states_after=right["states"],
                )
            )
    return dict(
        actor_changes=changed,
        hp_state_authority_complete=complete,
        effectful_state_or_hp=bool(changed),
    )


def gameplay_snapshot(fight):
    """Only gameplay populations/values; exclude UIDs, timers and diagnostics."""
    from copy import deepcopy

    actors = {}
    for identity, actor in fight.actors.items():
        stats = getattr(actor, "effect_stats", None)
        book = getattr(actor, "native_summon_action_book", None)
        actions = None if not isinstance(book, dict) else book.get("actions")
        actors[identity] = dict(
            position=deepcopy(getattr(actor, "position", None)),
            statistics=deepcopy(stats) if isinstance(stats, dict) else None,
            copied_actions=None
            if actions is None
            else sorted((row["reference"], row["level"]) for row in actions),
        )
    areas = {}
    for identity, row in getattr(fight, "native_effect_areas", {}).items():
        fields = (
            "reference",
            "level",
            "cell",
            "owner_id",
            "native_cells_xy",
            "direction",
        )
        if not isinstance(row, dict) or any(key not in row for key in fields):
            continue
        areas[identity] = {key: deepcopy(row[key]) for key in fields}
    from wakfu_server.combat_spell_grant import granted_spells

    return dict(
        actors=actors,
        areas=areas,
        granted={
            identity: sorted(granted_spells(fight, identity)) for identity in actors
        },
    )


def gameplay_delta(before, after, request):
    added = sorted(set(after["actors"]) - set(before["actors"]))
    removed = sorted(set(before["actors"]) - set(after["actors"]))
    changed = []
    ignored = []
    for identity in sorted(set(before["actors"]) & set(after["actors"])):
        left, right = before["actors"][identity], after["actors"][identity]
        row = dict(actor_id=identity)
        if (
            left["position"] is not None
            and right["position"] is not None
            and left["position"] != right["position"]
        ):
            row["position_before"], row["position_after"] = (
                left["position"],
                right["position"],
            )
        stats = []
        if left["statistics"] is not None and right["statistics"] is not None:
            for stat in sorted(set(left["statistics"]) & set(right["statistics"])):
                old, new = left["statistics"][stat], right["statistics"][stat]
                if (
                    stat == 1
                    or type(old) is not int
                    or type(new) is not int
                    or old == new
                ):
                    continue
                if identity == request.caster_id and request.native_rhe and new < old:
                    ignored.append(
                        dict(actor_id=identity, stat=stat, before=old, after=new)
                    )
                    continue
                stats.append(dict(stat=stat, before=old, after=new))
        if stats:
            row["statistics"] = stats
        if (
            left["copied_actions"] is not None
            and right["copied_actions"] is not None
            and left["copied_actions"] != right["copied_actions"]
        ):
            row["copied_book_before"], row["copied_book_after"] = (
                left["copied_actions"],
                right["copied_actions"],
            )
        if before["granted"][identity] != after["granted"][identity]:
            row["granted_before"], row["granted_after"] = (
                before["granted"][identity],
                after["granted"][identity],
            )
        if len(row) > 1:
            changed.append(row)
    area_changes = [
        dict(
            area_uid=identity,
            before=before["areas"].get(identity),
            after=after["areas"].get(identity),
        )
        for identity in sorted(set(before["areas"]) | set(after["areas"]))
        if before["areas"].get(identity) != after["areas"].get(identity)
    ]
    return dict(
        added_actor_ids=added,
        removed_actor_ids=removed,
        gameplay_actor_changes=changed,
        native_area_changes=area_changes,
        excluded_possible_caster_resource_payments=ignored,
        effectful_gameplay=bool(added or removed or changed or area_changes),
    )


class TriggeredSpellObservations:
    def __init__(self):
        self._observed = []

    @contextmanager
    def observe(self, handler):
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )

        if not isinstance(handler, NativeTriggeredSpellHandler):
            raise ValueError("Expected actual native triggered-spell handler")
        original = handler.executor
        pending = []
        start = len(handler.packets)

        def execute(request, effect, invocation):
            if effect["effect_class"] != 426 or invocation.native_running_uid is None:
                raise ValueError("Missing actual native eYZ runner identity")
            before = hp_state_snapshot(handler.fight)
            gameplay_before = gameplay_snapshot(handler.fight)
            result = original(request, effect, invocation)
            delta = hp_state_delta(before, hp_state_snapshot(handler.fight))
            delta.update(
                gameplay_delta(
                    gameplay_before, gameplay_snapshot(handler.fight), request
                )
            )
            delta["effectful_gameplay"] = (
                delta["effectful_gameplay"] or delta["effectful_state_or_hp"]
            )
            pending.append((request, invocation, delta))
            return result

        handler.executor = execute
        try:
            yield
        except BaseException:
            raise
        else:
            packets = handler.packets[start:]
            for request, invocation, delta in pending:
                expected = (
                    handler.fight.id,
                    handler.action_id,
                    invocation.native_running_uid,
                    invocation.reference,
                )
                matching = [
                    packet for packet in packets if packet_identity(packet) == expected
                ]
                if len(matching) != 1:
                    raise ValueError(
                        "Completed eYZ executor lacks unique application packet"
                    )
                self._observed.append(
                    (
                        matching[0],
                        dict(
                            **delta,
                            schema="wakemu.triggered426.delivery.v1",
                            effect_reference=invocation.reference,
                            running_uid=invocation.native_running_uid,
                            resolved_spell_id=request.spell_id,
                            caster_id=request.caster_id,
                            target_id=invocation.target_id,
                            cell=list(request.cell),
                            executor_completed=True,
                            ordinary_cast_eligibility_claim=False,
                            execution_policy="wakemu.eYZ.owned-ability-v1",
                        ),
                    )
                )
        finally:
            handler.executor = original

    def delivery_receipts(self, committed_packets):
        packets = list(committed_packets)
        result = []
        for packet, row in self._observed:
            count = packets.count(packet)
            if count > 1:
                raise ValueError("Ambiguous committed eYZ application packet")
            if count == 1:
                result.append(
                    dict(
                        row,
                        application_packet_sha256=sha256(packet[1]).hexdigest(),
                        committed_application_observed=True,
                    )
                )
        return result
