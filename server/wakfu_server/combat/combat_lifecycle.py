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
    fight_model=2,
    groups=None,
    group_lease=None
):
    """Commit fight, victory reward and group outcome before returning a report.

    Defeat earns no rewards. This does not restore health or exploration until
    the matching12925 callback. The returned character keeps exterior position.
    """
    if (groups is None) != (group_lease is None):
        raise ValueError("Group registry and fight lease must be provided together")
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
                reward = combat_rewards.award(
                    store,
                    account_id,
                    generation,
                    character["id"],
                    fight,
                    policy_from_env() if policy is None else policy,
                    db=db,
                )
                metadata = combat_rewards.report_metadata(
                    metadata, character["id"], reward
                )
                saved = reward["character"]
            else:
                saved = store.character(account_id, character["id"], db)
                reward = None
            if groups is not None:
                if group_lease is None:
                    raise ValueError("Missing group fight lease")
                applied = groups.finish(
                    group_lease, defeated=actor.team == fight.winner, db=db
                )
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
            if reward is not None:
                from .combat_xp_gain import notification

                notice = notification(character["id"], reward)
                if notice is not None:
                    packets.insert(0, notice)
            return dict(
                character=saved, reward=reward, metadata=metadata, packets=packets
            )
    except Exception:
        runtime.awaiting_ack, runtime.pending = previous_ack, previous_pending
        raise


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
