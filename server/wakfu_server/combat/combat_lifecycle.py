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
            packets = combat_results.finish_messages(
                runtime,
                metadata,
                duration_ms=duration_ms,
                fight_instance_id=fight_instance_id,
                initiator_id=character["id"],
                fight_model=fight_model,
            )
            packets.extend(loot_packets)
            if reward is not None:
                from .combat_xp_gain import notification

                notice = notification(character["id"], reward)
                if notice is not None:
                    packets.insert(0, notice)
            if ecology is not None:
                packets.extend(ecology["packets"])
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
    expected_accounts=None,
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
    if fight.phase != "finished" or fight.winner not in (0, 1):
        raise ValueError("Shared settlement requires a resolved fight")
    from .fight_store import settle_shared
    from .combat_rewards import award_shared_member, report_metadata
    from . import combat_results

    base_metadata = {identity: dict(record) for identity, record in metadata.items()}
    if set(base_metadata) != set(fight.actors):
        raise ValueError("Shared fight report metadata does not match roster")

    def settle(db, members, candidate):
        participant_rewards = {}
        participant_loot = {}
        shared_report = {
            identity: dict(record) for identity, record in base_metadata.items()
        }
        for member in members:
            owner = member["account_id"]
            actor_id = member["character_id"]
            actor = candidate.actors[actor_id]
            character = store.character(owner, actor_id, db)
            if member.get("withdrawn", False) or actor.team != candidate.winner:
                participant_rewards[owner] = None
                participant_loot[owner] = None
                continue
            policy = policy_resolver(db, member, character)
            reward = award_shared_member(
                store,
                db,
                owner,
                member["session_generation"],
                actor_id,
                candidate,
                policy,
            )
            participant_rewards[owner] = reward
            shared_report = report_metadata(shared_report, actor_id, reward)
            delivery = None
            if loot_resolver is not None:
                delivery = loot_resolver(db, member, reward)
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
            participant_loot[owner] = delivery

        ecology = None
        if group_settlement is not None:
            ecology = group_settlement(
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

        packets_by_owner = {}
        original_ack, original_pending = runtime.awaiting_ack, runtime.pending
        try:
            for member in members:
                owner = member["account_id"]
                actor_id = member["character_id"]
                if member.get("withdrawn", False):
                    packets_by_owner[owner] = ()
                    continue
                reward = participant_rewards[owner]
                report = {
                    identity: dict(value) for identity, value in shared_report.items()
                }
                delivery = participant_loot[owner]
                if delivery is not None:
                    report[actor_id]["loots"] = delivery["loots"]
                packets = []
                if reward is not None:
                    from wakfu_server.wire import account_kamas_update

                    packets.append(
                        (12753, account_kamas_update(reward["character"]["kamas"]))
                    )
                packets.extend(
                    combat_results.finish_messages(
                        runtime,
                        report,
                        duration_ms=duration_ms,
                        fight_instance_id=fight_instance_id,
                        initiator_id=actor_id,
                    )
                )
                packets.append((13420, struct.pack(">i", fight.id)))
                if reward is not None:
                    from .combat_xp_gain import notification

                    notice = notification(actor_id, reward)
                    if notice is not None:
                        packets.insert(1, notice)
                if delivery is not None:
                    packets.extend(delivery["packets"])
                if ecology is not None and actor_id == character_id:
                    packets.extend(ecology.get("packets", ()))
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
    )


def outside_progression(character, *, wp=None, ap=None, mp=None):
    """Own fmt3 XP/level/HP refresh after client cleanup; fightID=-1.

    The existing native PC codec includes XP, PUBLIC_CHARACTERISTICS and
    identity. Format3 FIGHT starts after byte format+i64XP+20bytePOSITION.
    """
    from .combat_actor import actor_stats
    from .equipment_stats import effective_character, combat_resources

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
    from .combat_health import persist

    with store.connection() as db:
        health_exit = persist(store, account_id, generation, character, fight, db=db)
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
