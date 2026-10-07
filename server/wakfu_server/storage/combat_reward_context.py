"""Build a terminal reward snapshot from owned Wakemu fight state.

Monster XP and kama values are deliberately not looked up here. The active
reward policy owns that catalog and resolves it transactionally. This adapter
only establishes which actors were players, trusted spawned monsters, or
registered summons and captures native player Wisdom.
"""

from wakfu_server.combat_actor_snapshot import native_actor_catalog
from wakfu_server.monsters import statistics as monster_statistics


WISDOM_STAT_ID = 36


def _integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid combat reward {name}")
    return value


def _summon(actor):
    marker = getattr(actor, "is_summon", False)
    if type(marker) is not bool:
        raise ValueError("Invalid summon authority marker")
    source = getattr(actor, "native_summon_source", None)
    if source is not None and not isinstance(source, dict):
        raise ValueError("Invalid native summon source")
    return marker or source is not None


def _wisdom(actor, catalog):
    characteristics = catalog.get("characteristics")
    row = (
        characteristics.get(str(WISDOM_STAT_ID))
        if isinstance(characteristics, dict)
        else None
    )
    if not isinstance(row, dict) or row.get("name") != "WISDOM":
        raise ValueError("Native Wisdom characteristic identity is unavailable")
    stats = getattr(actor, "effect_stats", None)
    if not isinstance(stats, dict) or WISDOM_STAT_ID not in stats:
        raise ValueError("Winning player has no authoritative Wisdom snapshot")
    return _integer(
        stats[WISDOM_STAT_ID],
        "Wisdom",
        row["hard_minimum"],
        row["hard_maximum"],
    )


def _monster_index(monsters):
    if not isinstance(monsters, (list, tuple)) or not monsters:
        raise ValueError("Trusted spawned monster roster is required")
    indexed = {}
    for member in monsters:
        if not isinstance(member, dict):
            raise ValueError("Invalid trusted spawned monster")
        identity = _integer(member.get("id"), "monster identity", -(1 << 63) + 1, -1)
        reference = _integer(member.get("ref"), "monster reference", 1, (1 << 31) - 1)
        level = _integer(member.get("level"), "monster level", 1, 200)
        if identity in indexed:
            raise ValueError("Duplicate trusted spawned monster identity")
        # This confirms the supplied reference/level is a native Wakfu actor.
        monster_statistics(reference, level)
        indexed[identity] = (reference, level)
    return indexed


def build_context(
    fight,
    character,
    monsters,
    *,
    challenge_percent=0,
    star_percent=0,
):
    """Return the strict `reward_policy.resolve` context for one victory.

    The current Wakemu fight state has no challenge or star subsystem, so its
    explicit local baseline is zero. A future authoritative source can supply
    those percentages as keyword values without changing actor attribution.
    """
    if getattr(fight, "phase", None) != "finished":
        raise ValueError("Combat rewards require a completed fight")
    winner_team = getattr(fight, "winner", None)
    if type(winner_team) is not int or winner_team not in (0, 1):
        raise ValueError("Combat rewards require a winning team")
    challenge_percent = _integer(challenge_percent, "challenge percent", 0, 1000000)
    star_percent = _integer(star_percent, "star percent", 0, 1000000)

    character_id = _integer(character.get("id"), "character identity", 1, (1 << 63) - 1)
    account_id = _integer(
        character.get("account_id"), "account identity", 1, (1 << 63) - 1
    )
    actors = getattr(fight, "actors", None)
    if not isinstance(actors, dict) or not actors:
        raise ValueError("Fight has no authoritative actor roster")
    monster_rows = _monster_index(monsters)
    catalog = native_actor_catalog()

    recipient = actors.get(character_id)
    if (
        recipient is None
        or not recipient.controlled
        or recipient.owner_id != account_id
        or _summon(recipient)
        or recipient.team != winner_team
    ):
        raise ValueError("Reward recipient is not the owned winning player")
    from wakfu_server.builds import effective_sheet_level

    effective_level = effective_sheet_level(
        character, character.get("active_build_index", 0)
    )
    if recipient.effective_level != effective_level:
        raise ValueError("Winning actor level disagrees with the owned character sheet")

    winners, losers = [], []
    seen_monsters = set()
    for key, actor in sorted(actors.items()):
        if type(key) is not int or actor.id != key:
            raise ValueError("Fight actor identity mismatch")
        level = _integer(actor.effective_level, "actor level", 1, 200)
        is_summon = _summon(actor)
        monster = monster_rows.get(actor.id)
        if monster is not None:
            reference, monster_level = monster
            if actor.controlled or is_summon or level != monster_level:
                raise ValueError("Fight monster differs from trusted spawn snapshot")
            seen_monsters.add(actor.id)
        elif not actor.controlled and not is_summon:
            raise ValueError("Unregistered NPC cannot enter reward context")

        if actor.team == winner_team:
            is_player = actor.controlled and not is_summon
            if actor.controlled and not is_summon:
                _integer(actor.owner_id, "player owner", 1, (1 << 63) - 1)
            winners.append(
                dict(
                    level=level,
                    player=is_player,
                    eligible=is_player,
                    character_id=actor.id if is_player else None,
                    wisdom=_wisdom(actor, catalog) if is_player else 0,
                )
            )
        else:
            losers.append(
                dict(
                    level=level,
                    monster_reference=monster[0] if monster is not None else None,
                )
            )

    if seen_monsters != set(monster_rows):
        raise ValueError("Trusted spawned monster roster differs from fight actors")
    if not winners or not losers:
        raise ValueError("Reward context requires actors on both teams")
    return dict(
        winner_team=winner_team,
        winners=winners,
        losers=losers,
        challenge_percent=challenge_percent,
        star_percent=star_percent,
    )


def build_drop_context(fight, character, monsters, *, encounter_kind=None):
    """Return the drop-condition context that this runtime can prove.

    `build_context` validates the completed fight, owned winning player,
    selected sheet level, actor roster and trusted monster snapshot. The
    native drop condition ONLY_WHEN_DOWNSCALED is supported by comparing that
    winning actor's effective level with the persisted character level.
    Dungeon/wave negatives are emitted only when the trusted encounter creator
    explicitly tags this route as an ordinary world-group fight. Map IDs and
    combat terrain IDs are not classifiers. Stasis and Stele remain absent.
    """
    if not isinstance(character, dict):
        raise ValueError("Invalid combat drop character")
    real_level = _integer(character.get("level"), "real character level", 1, 200)
    build_context(fight, character, monsters)
    actor = fight.actors[character["id"]]
    context = {"downscaled": actor.effective_level < real_level}
    if encounter_kind is not None:
        if encounter_kind != "ordinary_world":
            raise ValueError("Unsupported authoritative encounter kind")
        context.update(in_dungeon=False, in_infinite_waves=False)
    return context


def settlement_contexts(db, fight, character, monsters, *, encounter_kind=None):
    """Return reward/drop inputs frozen before a shared award mutates the character.

    The shared settlement writes XP before it resolves drops. A level-up in
    that transaction must not change the actor-level comparison used for loot
    eligibility. Successful settlement writes both receipts atomically, so a
    retry can recover the exact contexts from those receipts instead of
    rebuilding them from the already-updated character.
    """
    if not isinstance(character, dict):
        raise ValueError("Invalid combat settlement character")
    character_id = _integer(character.get("id"), "character identity", 1, (1 << 63) - 1)
    reward_row = db.execute(
        "SELECT snapshot FROM fight_reward_policy_receipts "
        "WHERE fight_id=%s AND character_id=%s",
        (fight.id, character_id),
    ).fetchone()
    drop_row = db.execute(
        "SELECT snapshot FROM fight_drop_awards "
        "WHERE fight_id=%s AND character_id=%s",
        (fight.id, character_id),
    ).fetchone()

    if reward_row is None:
        reward_context = build_context(fight, character, monsters)
    else:
        snapshot = reward_row["snapshot"]
        reward_context = snapshot.get("context") if isinstance(snapshot, dict) else None
        if not isinstance(reward_context, dict):
            raise ValueError("Stored reward receipt has no frozen combat context")

    if drop_row is None:
        if reward_row is not None:
            raise ValueError(
                "Shared reward receipt is missing its atomic drop snapshot"
            )
        drop_context = build_drop_context(
            fight, character, monsters, encounter_kind=encounter_kind
        )
    else:
        snapshot = drop_row["snapshot"]
        drop_context = (
            snapshot.get("fight_context") if isinstance(snapshot, dict) else None
        )
        if not isinstance(drop_context, dict):
            raise ValueError("Stored drop receipt has no frozen fight context")
    return reward_context, drop_context


def resolve_policy(
    store,
    db,
    *,
    account_id,
    generation,
    character,
    fight,
    monsters,
    challenge_percent=0,
    star_percent=0,
    kamas_roll_index=None,
):
    """Resolve one reward in the caller's finish transaction; return its Policy."""
    from wakfu_server.reward_policy import resolve

    context = build_context(
        fight,
        character,
        monsters,
        challenge_percent=challenge_percent,
        star_percent=star_percent,
    )
    decision = resolve(
        store,
        db,
        account_id=account_id,
        generation=generation,
        character_id=character["id"],
        fight_id=fight.id,
        context=context,
        kamas_roll_index=kamas_roll_index,
    )
    return decision.policy
