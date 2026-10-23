"""Project owned world consumable states into a fresh combat Qf.

Children execute through the ordinary state runtime, rather than a second
flat-stat reducer. Realtime deadlines retain native eZV combat suppression;
returning to the world uses eZk.h's max(1, remaining) migration.
"""


def _positive(value, name):
    if type(value) is not int or not 0 < value < (1 << 63):
        raise ValueError(f"Invalid consumable {name}")
    return value


def _clock(value):
    if type(value) is not int or not 0 <= value < (1 << 63):
        raise ValueError("Invalid consumable clock")


def install(fight, character, runtime_factory, *, owner_id, now_ms):
    """Install hydrated, descriptor-qualified states on an owned preview.

    The caller owns rollback and publication. Empty input is also marked so a
    later reconnect cannot introduce states or execute their children twice.
    """
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_native_timing_context import native_time_payload
    from .combat_state_handler import StateCarrierContext

    _clock(now_ms)
    actor = fight.actors.get(character.get("id"))
    if (
        actor is None
        or actor.hp <= 0
        or fight.phase != "active"
        or not actor.controlled
        or actor.owner_id != owner_id
        or type(owner_id) is not int
        or owner_id <= 0
    ):
        raise ValueError("Consumable states require an owned active fighter")
    initializations = getattr(fight, "native_consumable_initializations", {})
    if actor.id in initializations:
        raise ValueError("Fighter consumable states are already initialized")
    sources = character.get("consumable_states", ())
    if not isinstance(sources, (tuple, list)):
        raise ValueError("Owned consumable state rows required")
    if not sources:
        initializations[actor.id] = ()
        fight.native_consumable_initializations = initializations
        return ()
    dispatcher, packets = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    handler = dispatcher.native_state_handler
    retention = dispatcher.native_retention
    if handler.fight is not fight or retention is None:
        raise ValueError("Missing consumable state runtime")
    prepared = []
    seen = set()
    for row in sources:
        if not isinstance(row, dict):
            raise ValueError("Owned consumable state row required")
        uid = _positive(row.get("uid"), "world UID")
        reference = _positive(row.get("state_id"), "state reference")
        level = _positive(row.get("level"), "state level")
        clock = row.get("clock")
        remaining, duration = row.get("remaining_ms"), row.get("duration_ms")
        if clock == "event":
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError("Consumable event metadata required")
            counter = metadata.get("counter", {})
            if not isinstance(counter, dict):
                raise ValueError("Consumable counter metadata required")
            if (
                type(remaining) is not int
                or remaining != 0
                or type(duration) is not int
                or duration != 0
                or not (
                    metadata.get("removal_event_ids")
                    or counter.get("decrement_event_ids")
                )
            ):
                raise ValueError("Unproven consumable event clock")
        else:
            _positive(remaining, "remaining duration")
            _positive(duration, "duration")
        if uid in seen or clock not in ("wall", "online", "event"):
            raise ValueError("Duplicate or unsupported consumable state clock")
        seen.add(uid)
        profile = state_profile(handler.catalog, reference, level)
        if (
            profile["level"] != level
            or profile["duration"] >= 0
            or (
                profile["realtime_duration"] > 0
                if clock == "event"
                else profile["realtime_duration"] != duration
            )
            or profile["skip_turn_timer"] is not True
            or remaining > duration
            or tuple(row.get("effect_ids", ())) != tuple(profile["effects"])
        ):
            raise ValueError("Consumable state disagrees with native definition")
        prepared.append((row, profile))
    bindings = []
    initial_maximum = actor.max_hp
    with fight.effect_resolution():
        for row, profile in prepared:
            previous = {entry.uid for entry in actor.state_ledger.entries}
            remaining = (
                profile["realtime_duration"]
                if row["clock"] == "event"
                else row["remaining_ms"]
            )
            context = StateCarrierContext(
                profile["duration"],
                remaining,
                False,
                None,
                None,
                False,
                False,
                False,
                0,
                native_time_payload(realtime_remaining=remaining),
            )
            invocation = EffectInvocation(
                2226, row["level"], actor.id, actor.id, actor.position
            )
            applied = retention.apply_state_reference(
                handler,
                invocation,
                row["state_id"],
                row["level"],
                carrier_context=context,
            )
            created = tuple(
                entry
                for entry in actor.state_ledger.entries
                if entry.uid not in previous and entry.reference == row["state_id"]
            )
            if not applied or len(created) != 1 or created[0].timer is not None:
                raise ValueError("Missing migrated consumable state carrier")
            entry = created[0]
            if row["clock"] != "event":
                entry = actor.state_ledger.install_realtime_clock(
                    entry.uid, deadline_ms=now_ms + remaining, in_combat=True
                )
            bindings.append(
                dict(
                    world_uid=row["uid"],
                    combat_uid=entry.uid,
                    state_id=entry.reference,
                    clock=row["clock"],
                    **(
                        {"handoff_target": row["metadata"]["native_handoff_target"]}
                        if row.get("metadata", {}).get("native_handoff_target")
                        else {}
                    ),
                    **(
                        {
                            "self_counter_effect_id": row["metadata"][
                                "native_self_counter_effect_id"
                            ]
                        }
                        if row.get("metadata", {}).get("native_self_counter_effect_id")
                        else {}
                    ),
                )
            )
    if actor.max_hp != initial_maximum:
        packets.extend(_entry_health(fight, character, actor))
    initializations[actor.id] = tuple(bindings)
    fight.native_consumable_initializations = initializations
    return tuple(packets)


def _entry_health(fight, character, actor):
    """Preserve canonical wounds across the outside-food configuration change.

    This is Wakemu's configuration policy, not an extra native heal/damage
    effect. Run before class innates so their real resource effects survive.
    """
    from wakfu_server.health_policy import visible
    from .combat_hp_raw import set_hp_raw_current

    expected = visible(
        actor.max_hp,
        character["hp_damage"],
        character["health_dead"],
        character.get("hp_zero_valid", False),
    )
    if actor.hp == expected or 1 in actor.effect_frozen:
        return ()
    set_hp_raw_current(actor, expected)
    if actor.hp != expected:
        raise ValueError("Consumable entry health violates native HP bounds")
    from .combat_actor import actual_actor_stats
    from .combat_characteristic_snapshot import characteristics_only_snapshot
    from .combat_wire import actor_state

    stats = actual_actor_stats(
        character,
        actor,
        fight.id,
        wp_current=actor.effect_stats[4],
        wp_maximum=actor.effect_maxima[4],
        fight=fight,
    )
    return (
        (
            12873,
            actor_state(
                12873, fight.id, actor.id, characteristics_only_snapshot(stats)
            ),
        ),
    )


def returning_states(fight, character_id, *, now_ms):
    """Return only this projection's surviving carriers or explicit removals.

    A combat-created state with the same reference cannot impersonate a removed
    world carrier. Persistence/transaction and ownership checks belong to the
    world return caller; this helper never writes the database.
    """
    _clock(now_ms)
    bindings = getattr(fight, "native_consumable_initializations", {})
    if character_id not in bindings:
        return ()
    actor = fight.actors.get(character_id)
    if actor is None:
        raise ValueError("Missing consumable return fighter")
    live = {entry.uid: entry for entry in actor.state_ledger.entries}
    result = []
    for binding in bindings[character_id]:
        entry = live.get(binding["combat_uid"])
        row = dict(uid=binding["world_uid"], state_id=binding["state_id"])
        if entry is None:
            result.append(dict(row, removed=True))
            continue
        if (
            entry.reference != binding["state_id"]
            or entry.target_id != character_id
            or entry.caster_id != character_id
            or entry.timer is not None
        ):
            raise ValueError("Consumable return carrier identity changed")
        if binding["clock"] == "event":
            if entry.realtime_duration > 0 or entry.realtime_deadline_ms is not None:
                raise ValueError("Consumable event carrier acquired a realtime clock")
            remaining = 0
        else:
            if (
                entry.realtime_in_combat is not True
                or type(entry.realtime_deadline_ms) is not int
                or entry.realtime_duration <= 0
            ):
                raise ValueError("Consumable realtime return clock changed")
            remaining = max(1, entry.realtime_deadline_ms - now_ms)
        result.append(
            dict(
                row,
                removed=False,
                level=entry.level,
                clock=binding["clock"],
                remaining_ms=remaining,
            )
        )
    return tuple(result)


def restore_checkpoint_projection(fight, snapshot):
    """Keep food ownership during terminal HP recovery, without resuming a fight.

    The caller already authenticated its durable terminal checkpoint. Only food
    carrier records and their UID bindings are reconstructed; no child runner,
    timer callback, spell, native actor authority or timeline is re-executed.
    """
    from .combat_state_ledger import RunningState, StateLedger

    bindings = snapshot.get("native_consumable_initializations")
    external = snapshot.get("native_external_state_origins", {})
    if bindings is None and not external:
        return
    bindings = {} if bindings is None else bindings
    if not isinstance(bindings, dict):
        raise ValueError("Invalid checkpoint consumable bindings")
    if not isinstance(external, dict):
        raise ValueError("Invalid checkpoint external state origins")
    external_by_actor = {}
    for key, origin in external.items():
        uid = int(key)
        if (
            not isinstance(origin, dict)
            or origin.get("combat_uid") != uid
            or uid <= 0
            or origin.get("kind") != "native-state"
            or type(origin.get("character_id")) is not int
            or origin["character_id"] <= 0
            or origin.get("fight_id") != fight.id
            or origin.get("effect_id") != 45980
            or origin.get("parent_state_id") != 987
            or type(origin.get("parent_uid")) is not int
            or origin["parent_uid"] <= 0
            or type(origin.get("source_uid")) is not int
            or origin["source_uid"] <= 0
        ):
            raise ValueError("Invalid checkpoint native981 source")
        external_by_actor.setdefault(origin["character_id"], set()).add(uid)
    restored = {}
    owners = {int(key): rows for key, rows in bindings.items()}
    for identity in external_by_actor:
        owners.setdefault(identity, [])
    for key, rows in owners.items():
        identity = int(key)
        actor = fight.actors.get(identity)
        if actor is None or not actor.controlled or not isinstance(rows, list):
            raise ValueError("Checkpoint consumable owner is unavailable")
        source = snapshot.get("actors", {}).get(str(identity), {})
        ledger = source.get("state_ledger", {})
        if not isinstance(ledger, dict) or ledger.get("actor_id") != identity:
            raise ValueError("Checkpoint consumable ledger owner changed")
        wanted = {row["combat_uid"] for row in rows} | external_by_actor.get(
            identity, set()
        )
        entries = []
        for record in ledger.get("entries", ()):
            if record.get("uid") not in wanted:
                continue
            if record.get("target_id") != identity or record.get("timer") is not None:
                raise ValueError("Checkpoint consumable carrier identity changed")
            if record.get("uid") in external_by_actor.get(identity, set()) and (
                record.get("reference") != 981
                or record.get("caster_id") != identity
                or record.get("realtime_duration") != 240000
            ):
                raise ValueError("Checkpoint external981 carrier identity changed")
            entry = dict(record, effect_ids=tuple(record["effect_ids"]))
            entries.append(RunningState(**entry))
        actual = StateLedger(identity)
        actual._entries = tuple(entries)
        actor.state_ledger = actual
        restored[identity] = tuple(dict(row) for row in rows)
    fight.native_consumable_initializations = restored
    if external:
        fight.native_external_state_origins = {
            int(key): dict(value) for key, value in external.items()
        }
        payloads = snapshot.get("state_wire_payloads", {})
        for uids in external_by_actor.values():
            for uid in uids:
                if str(uid) in payloads:
                    fight.state_wire_payloads[uid] = payloads[str(uid)]
