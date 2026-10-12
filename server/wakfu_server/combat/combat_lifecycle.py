"""Own fight finish/reward/return orchestration; no dispatcher or GUI effects."""
import os
import struct
from . import combat_rewards, combat_results, health_store, health, wire


def policy_from_env(env=None):
    """Explicit local policy; both optional values default to zero."""
    env = os.environ if env is None else env
    values = []
    for key in ("WAKFU_LOCAL_FIGHT_XP", "WAKFU_LOCAL_FIGHT_KAMAS"):
        value = env.get(key, "0")
        if (
            not isinstance(value, str)
            or not value
            or not value.isascii()
            or not value.isdigit()
        ):
            raise ValueError("Invalid local reward setting " + key)
        values.append(int(value))
    return combat_rewards.Policy(*values)


def prepare_finish(
    store,
    account_id,
    generation,
    character,
    runtime,
    metadata,
    *,
    duration_ms,
    fight_instance_id,
    policy=None,
    policy_resolver=None,
    loot_resolver=None,
    fight_model=2,
    groups=None,
    group_lease=None,
    group_settlement=None,
    progression_resolver=None,
):
    """Commit fight, victory reward and group outcome before returning a report.

    Defeat earns no rewards. This does not restore health or exploration until
    the matching12925 callback. The returned character keeps exterior position.
    """
    if (groups is None) != (group_lease is None):
        raise ValueError("Group registry and fight lease must be provided together")
    if policy is not None and policy_resolver is not None:
        raise ValueError("Explicit reward policy and resolver are mutually exclusive")
    if policy_resolver is not None and not callable(policy_resolver):
        raise ValueError("Reward policy resolver must be callable")
    if loot_resolver is not None and not callable(loot_resolver):
        raise ValueError("Loot resolver must be callable")
    if progression_resolver is not None and not callable(progression_resolver):
        raise ValueError("Progression resolver must be callable")
    fight = runtime.fight
    # Validate required report identity before committing a reward transaction.
    combat_results.fight_report(
        fight,
        metadata,
        duration_ms=duration_ms,
        fight_instance_id=fight_instance_id,
        initiator_id=character["id"],
        fight_model=fight_model,
    )
    previous_ack, previous_pending = runtime.awaiting_ack, runtime.pending
    try:
        with store.connection() as db:
            from .fight_store import finish

            finish(store, db, account_id, generation, character["id"], fight.id)
            if getattr(fight, "boss_score_profile", None) is not None:
                from wakfu_server.maps.boss_score_runtime import finalize

                finalize(db, fight)
            from .combat_captured_roster_checkpoint import (
                persist_captured_roster_updates,
            )

            persist_captured_roster_updates(db, fight)
            actor = fight.actors[character["id"]]
            if actor.team == fight.winner:
                selected_policy = (
                    policy_resolver(db)
                    if policy_resolver is not None
                    else policy_from_env()
                    if policy is None
                    else policy
                )
                reward = combat_rewards.award(
                    store,
                    account_id,
                    generation,
                    character["id"],
                    fight,
                    selected_policy,
                    db=db,
                )
                metadata = combat_rewards.report_metadata(
                    metadata, character["id"], reward
                )
                saved = reward["character"]
                loot_packets = []
                if loot_resolver is not None:
                    delivery = loot_resolver(db, reward)
                    if not isinstance(delivery, dict) or set(delivery) != {
                        "loots",
                        "packets",
                    }:
                        raise ValueError("Invalid committed loot delivery")
                    # Validate the report before committing inventory mutations.
                    combat_results._loots(delivery["loots"])
                    loot_packets = delivery["packets"]
                    if not isinstance(loot_packets, list) or any(
                        not isinstance(packet, tuple)
                        or len(packet) != 2
                        or type(packet[0]) is not int
                        or not isinstance(packet[1], bytes)
                        for packet in loot_packets
                    ):
                        raise ValueError("Invalid committed loot packets")
                    metadata = {
                        **metadata,
                        character["id"]: {
                            **metadata[character["id"]],
                            "loots": delivery["loots"],
                        },
                    }
                    saved = store.character(account_id, character["id"], db)
            else:
                saved = store.character(account_id, character["id"], db)
                reward = None
                loot_packets = []
            ecology = None
            if groups is not None:
                if group_lease is None:
                    raise ValueError("Missing group fight lease")
                if group_settlement is None:
                    applied = groups.finish(
                        group_lease, defeated=actor.team == fight.winner, db=db
                    )
                else:
                    ecology = group_settlement(
                        db, group_lease, actor.team == fight.winner
                    )
                    applied = ecology["applied"]
                    saved = store.character(account_id, character["id"], db)
                if not applied and reward is not None and reward["awarded"]:
                    raise ValueError("Group fight lease changed before settlement")
            progression_packets = {}
            if progression_resolver is not None:
                progression_packets = progression_resolver(
                    db,
                    [
                        {
                            "account_id": account_id,
                            "character_id": character["id"],
                            "session_generation": generation,
                        }
                    ],
                    fight,
                )
                _validate_progression_packets(progression_packets, {account_id})
                saved = store.character(account_id, character["id"], db)
            packets = combat_results.finish_messages(
                runtime,
                metadata,
                duration_ms=duration_ms,
                fight_instance_id=fight_instance_id,
                initiator_id=character["id"],
                fight_model=fight_model,
            )
            packets.extend(loot_packets)
            packets.extend(progression_packets.get(account_id, ()))
            if reward is not None:
                from .combat_xp_gain import notification

                notice = notification(character["id"], reward)
                if notice is not None:
                    packets.insert(0, notice)
            if ecology is not None:
                packets.extend(ecology["packets"])
            from .fight_store import _write_terminal_checkpoint

            _write_terminal_checkpoint(db, store, account_id, generation, fight)
            return dict(
                character=saved,
                reward=reward,
                metadata=metadata,
                packets=packets,
                ecology=ecology,
            )
    except Exception:
        runtime.awaiting_ack, runtime.pending = previous_ack, previous_pending
        raise


def prepare_finish_shared(
    store,
    account_id,
    generation,
    character_id,
    runtime,
    metadata,
    *,
    duration_ms,
    fight_instance_id,
    policy_resolver,
    loot_resolver=None,
    group_settlement=None,
    progression_resolver=None,
    expected_accounts=None,
    owner_character_ids=None,
    trace=None,
):
    """Settle a finished shared roster once and build private owner packets.

    The caller supplies a resolver for each durable participant. Rewards,
    drops, group outcome, and packet validation share ``fight_store``'s single
    transaction. ``metadata`` must already describe every report actor.
    """
    if (
        not callable(policy_resolver)
        or (loot_resolver is not None and not callable(loot_resolver))
        or (group_settlement is not None and not callable(group_settlement))
        or (progression_resolver is not None and not callable(progression_resolver))
    ):
        raise ValueError("Invalid shared fight settlement resolver")
    if expected_accounts is not None and (
        not isinstance(expected_accounts, (set, frozenset))
        or any(
            type(account) is not int or account <= 0 for account in expected_accounts
        )
    ):
        raise ValueError("Invalid expected shared fight owners")
    fight = runtime.fight
    if owner_character_ids is not None and (
        not isinstance(owner_character_ids, dict)
        or any(
            type(owner) is not int
            or owner <= 0
            or type(identity) is not int
            or identity <= 0
            for owner, identity in owner_character_ids.items()
        )
    ):
        raise ValueError("Invalid shared result owner character identities")
    if fight.phase != "finished" or fight.winner not in (0, 1):
        raise ValueError("Shared settlement requires a resolved fight")
    from .fight_store import settle_shared
    from .combat_rewards import award_shared_member, report_metadata
    from . import combat_results

    from .fight_checkpoint_store import _trace_stage
    import time

    def observe(stage, callback, *args, **kwargs):
        started = time.monotonic()
        _trace_stage(trace, stage + "_started", fight.id, operation="settle")
        try:
            return callback(*args, **kwargs)
        finally:
            _trace_stage(
                trace,
                stage + "_finished",
                fight.id,
                operation="settle",
                elapsed_ms=(time.monotonic() - started) * 1000,
            )

    base_metadata = {identity: dict(record) for identity, record in metadata.items()}
    if set(base_metadata) != set(fight.actors):
        raise ValueError("Shared fight report metadata does not match roster")

    def settle(db, members, candidate):
        from .combat_captured_roster_checkpoint import persist_captured_roster_updates

        # Capture and roster mutations share the reward/terminal transaction;
        # every character snapshot below observes the actual settled roster.
        if getattr(candidate, "boss_score_profile", None) is not None:
            from wakfu_server.maps.boss_score_runtime import finalize

            observe("boss_score", finalize, db, candidate)
        observe("captured_roster", persist_captured_roster_updates, db, candidate)
        participant_rewards = {}
        participant_loot = {}
        shared_report = {
            identity: dict(record) for identity, record in base_metadata.items()
        }
        for member in members:
            owner = member["account_id"]
            actor_id = member["character_id"]
            actor = candidate.actors[actor_id]
            character = observe("character", store.character, owner, actor_id, db)
            if member.get("withdrawn", False) or actor.team != candidate.winner:
                participant_rewards[actor_id] = None
                participant_loot[actor_id] = None
                continue
            policy = observe("policy", policy_resolver, db, member, character)
            reward = observe(
                "reward",
                award_shared_member,
                store,
                db,
                owner,
                member["session_generation"],
                actor_id,
                candidate,
                policy,
            )
            participant_rewards[actor_id] = reward
            shared_report = report_metadata(shared_report, actor_id, reward)
            delivery = None
            if loot_resolver is not None:
                delivery = observe("loot", loot_resolver, db, member, reward)
                if not isinstance(delivery, dict) or set(delivery) != {
                    "loots",
                    "packets",
                }:
                    raise ValueError("Invalid shared loot delivery")
                combat_results._loots(delivery["loots"])
                packets = delivery["packets"]
                if not isinstance(packets, list) or any(
                    not isinstance(packet, tuple)
                    or len(packet) != 2
                    or type(packet[0]) is not int
                    or not isinstance(packet[1], bytes)
                    for packet in packets
                ):
                    raise ValueError("Invalid shared loot packets")
            participant_loot[actor_id] = delivery

        ecology = None
        if group_settlement is not None:
            ecology = observe(
                "group",
                group_settlement,
                db,
                account_id,
                character_id,
                candidate.actors[character_id].team == candidate.winner,
            )
            if (
                not isinstance(ecology, dict)
                or type(ecology.get("applied")) is not bool
            ):
                raise ValueError("Invalid shared group settlement")
            if not ecology["applied"]:
                raise ValueError("Shared group lease changed before settlement")

        progression_packets = {}
        if progression_resolver is not None:
            progression_packets = observe(
                "progression", progression_resolver, db, members, candidate
            )
            _validate_progression_packets(
                progression_packets, {member["account_id"] for member in members}
            )
        packets_by_owner = {}
        original_ack, original_pending = runtime.awaiting_ack, runtime.pending
        try:
            by_owner = {}
            for member in members:
                by_owner.setdefault(member["account_id"], []).append(member)
            for owner, owned_members in by_owner.items():
                active_members = [
                    member
                    for member in owned_members
                    if not member.get("withdrawn", False)
                ]
                if not active_members:
                    packets_by_owner[owner] = ()
                    continue
                preferred = (owner_character_ids or {}).get(owner)
                if preferred is None:
                    preferred = (
                        character_id
                        if owner == account_id
                        else active_members[0]["character_id"]
                    )
                if preferred not in {
                    member["character_id"] for member in owned_members
                }:
                    raise ValueError(
                        "Result initiator is not an owned durable participant"
                    )
                actor_id = preferred
                rewards = [
                    (
                        member["character_id"],
                        participant_rewards[member["character_id"]],
                    )
                    for member in active_members
                    if participant_rewards[member["character_id"]] is not None
                ]
                reward = rewards[-1][1] if rewards else None
                report = {
                    identity: dict(value) for identity, value in shared_report.items()
                }
                deliveries = [
                    (member["character_id"], participant_loot[member["character_id"]])
                    for member in active_members
                    if participant_loot[member["character_id"]] is not None
                ]
                for recipient_id, delivery in deliveries:
                    report[recipient_id]["loots"] = delivery["loots"]
                packets = []
                if reward is not None:
                    from wakfu_server.wire import account_kamas_update

                    packets.append(
                        (12753, account_kamas_update(reward["character"]["kamas"]))
                    )
                packets.extend(
                    observe(
                        "result_packets",
                        combat_results.finish_messages,
                        runtime,
                        report,
                        duration_ms=duration_ms,
                        fight_instance_id=fight_instance_id,
                        initiator_id=actor_id,
                    )
                )
                packets.append((13420, struct.pack(">i", fight.id)))
                if rewards:
                    from .combat_xp_gain import notification

                    notices = [
                        notice
                        for recipient_id, owned_reward in rewards
                        if (notice := notification(recipient_id, owned_reward))
                        is not None
                    ]
                    packets[1:1] = notices
                for _, delivery in deliveries:
                    packets.extend(delivery["packets"])
                if ecology is not None and actor_id == character_id:
                    packets.extend(ecology.get("packets", ()))
                packets.extend(progression_packets.get(owner, ()))
                packets_by_owner[owner] = tuple(packets)
        finally:
            runtime.awaiting_ack, runtime.pending = original_ack, original_pending
        if expected_accounts is not None and set(packets_by_owner) != set(
            expected_accounts
        ):
            raise ValueError("Shared settlement packet owners differ from registry")
        if any(
            not isinstance(packet, tuple)
            or len(packet) != 2
            or type(packet[0]) is not int
            or not 0 <= packet[0] <= 0xFFFF
            or not isinstance(packet[1], bytes)
            or len(packet[1]) > 0xFFFFFFFF - 6
            for packets in packets_by_owner.values()
            for packet in packets
        ):
            raise ValueError("Shared settlement contains an invalid native packet")
        return packets_by_owner

    return settle_shared(
        store,
        account_id,
        generation,
        character_id,
        fight,
        settle,
        **({"trace": trace} if trace is not None else {}),
    )


def outside_progression(character, *, wp=None, ap=None, mp=None):
    """Own fmt3 XP/level/HP refresh after client cleanup; fightID=-1.

    The existing native PC codec includes XP, PUBLIC_CHARACTERISTICS and
    identity. Format3 FIGHT starts after byte format+i64XP+20bytePOSITION.
    """
    from .combat_actor import actor_stats
    from wakfu_server.equipment_stats import effective_character, combat_resources

    owned = effective_character(character)
    resources = combat_resources(owned, wp=wp, base_ap=ap, base_mp=mp)
    blob = actor_stats(
        owned,
        1,
        wp=resources["wp"],
        ap=resources["ap"],
        mp=resources["mp"],
        initiative=resources["initiative"],
    )
    from wakfu_server.wire import complete_public_characteristics

    characteristics_offset = 1 + 8 + 20 + struct.calcsize(">iBBBBbB")
    count = struct.unpack_from(">H", blob, characteristics_offset)[0]
    end = characteristics_offset + 2 + count * struct.calcsize(">Biiii")
    blob = (
        blob[:characteristics_offset]
        + complete_public_characteristics(blob[characteristics_offset:end])
        + blob[end:]
    )
    offset = 1 + 8 + 20
    if struct.unpack_from(">i", blob, offset)[0] != 1:
        raise ValueError("Unexpected native fighter progression layout")
    blob = blob[:offset] + struct.pack(">i", -1) + blob[offset + 4 :]
    from .combat_world_refresh import actor_refresh

    return actor_refresh(character["id"], blob)


def return_to_world(
    store, account_id, generation, character, runtime, body, *, wp, ap=6, mp=3
):
    """Build12925 return packets atomically with HP and regeneration persistence.

    Root still supplies its13974 destination bootstrap and releases the fight.
    This function does not own the NPC respawn policy or map transition.
    """
    fight = runtime.fight
    if fight.phase != "finished":
        raise ValueError("Fight has not finished")
    combat_results.continuation(fight.id, body)
    actor = fight.actors.get(character["id"])
    if actor is None or not actor.controlled or actor.owner_id != account_id:
        raise ValueError("Foreign fight return participant")
    from .combat_health import persist_owned

    with store.connection() as db:
        health_exit = persist_owned(
            store, account_id, generation, character, fight, db=db
        )
        saved = health_exit["character"]
        if not health_exit["applied"]:
            return dict(character=saved, packets=[], applied=False)
        packets = combat_results.outside_fight_updates(fight)
        packets.extend(
            [
                outside_progression(saved, wp=wp, ap=ap, mp=mp),
                (
                    12436,
                    health.packet(saved["id"], saved["hp"], health_exit["coefficient"]),
                ),
                (13021, struct.pack(">q", saved["kamas"])),
                (13873, wire.account_kamas(saved["kamas"])),
            ]
        )
        return dict(character=saved, packets=packets, applied=True)


def recover_settled_world(
    store,
    account_id,
    generation,
    character,
    fight,
    *,
    previous_generation,
    fight_id=None,
    wp,
    ap=6,
    mp=3,
):
    """Finish a settled PvE return for a fresh login already in the world.

    This is not a synthetic12925 or a fight bootstrap. The new connection has
    loaded its world actor, so replaying combat terminal packets would target a
    client with no native fight model. Rewards are never resolved here; the
    durable finish and return-health receipt are the idempotency boundary.
    """
    fight_id = getattr(fight, "id", None) if fight_id is None else fight_id
    if type(fight_id) is not int or fight_id <= 0:
        raise ValueError("Settled world recovery requires a fight identity")
    if fight is not None and fight.phase != "finished":
        raise ValueError("Settled world recovery requires a finished fight")
    from .fight_store import recover_finished_return

    health_exit = recover_finished_return(
        store,
        account_id,
        generation,
        character["id"],
        fight,
        character,
        previous_generation=previous_generation,
        fight_id=fight_id,
    )
    saved = health_exit["character"]
    fight = health_exit["fight"]
    coefficient = health_exit.get("coefficient", 0 if saved["hp"] == 0 else 1)
    from wakfu_server.inventory_items import equipment_inventory
    from wakfu_server.inventory_move import synchronization

    packets = [synchronization(saved), equipment_inventory(saved)]
    if not health_exit["recovered_from_checkpoint"]:
        packets.extend(combat_results.outside_fight_updates(fight))
    packets.extend(
        [
            outside_progression(saved, wp=wp, ap=ap, mp=mp),
            (12436, health.packet(saved["id"], saved["hp"], coefficient)),
            (13021, struct.pack(">q", saved["kamas"])),
            (13873, wire.account_kamas(saved["kamas"])),
        ]
    )
    return dict(
        fight_id=fight_id,
        character=saved,
        packets=packets,
        applied=health_exit["applied"],
        recovered=True,
    )


def _validate_progression_packets(packets_by_owner, owners):
    """Reject malformed private progression output before settlement commits."""
    if not isinstance(packets_by_owner, dict) or any(
        type(owner) is not int
        or owner not in owners
        or not isinstance(packets, (list, tuple))
        or any(
            not isinstance(packet, tuple)
            or len(packet) != 2
            or type(packet[0]) is not int
            or not 0 <= packet[0] <= 0xFFFF
            or not isinstance(packet[1], bytes)
            or len(packet[1]) > 0xFFFFFFFF - 6
            for packet in packets
        )
        for owner, packets in packets_by_owner.items()
    ):
        raise ValueError("Invalid private progression packets")
