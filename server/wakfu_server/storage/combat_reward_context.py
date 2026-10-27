"""Build a terminal reward snapshot from owned Wakemu fight state.

Monster XP and kama values are deliberately not looked up here. The active
reward policy owns that catalog and resolves it transactionally. This adapter
only establishes which actors were players, trusted spawned monsters, or
registered summons and captures native player Wisdom.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL

from wakfu_server.combat_actor_snapshot import native_actor_catalog
from wakfu_server.monsters import statistics as monster_statistics


WISDOM_STAT_ID = 36


def native_shop_consumable_factor(actor, identity):
    """ffw118/119 store absolute percentage factors, with native default100.

    Legacy fixture actors may omit these characteristics; the ordinary stat
    executor cannot apply a consumable to a missing stat, so those actors have
    no shop-factor mutation. Complete production snapshots contain both IDs.
    """
    if type(identity) is not int or identity not in (118, 119):
        raise ValueError("Unknown native shop consumable characteristic")
    stats = getattr(actor, "effect_stats", None)
    if not isinstance(stats, dict):
        raise ValueError("Missing native shop consumable actor characteristics")
    return _integer(stats.get(identity, 100), "shop consumable factor", 0, 1000)


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
    from wakfu_server.native_catalog_document import is_native_json_mapping

    characteristics = catalog.get("characteristics")
    if not is_native_json_mapping(characteristics):
        raise ValueError("Native Wisdom characteristic identity is unavailable")
    row = characteristics.get(str(WISDOM_STAT_ID))
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
        level = _integer(member.get("level"), "monster level", 1, 32767)
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
    from wakfu_server.combat_companions import registered_companion_ids

    companion_ids = registered_companion_ids(fight)

    recipient = actors.get(character_id)
    if (
        recipient is None
        or not recipient.controlled
        or recipient.owner_id != account_id
        or _summon(recipient)
        or recipient.id in companion_ids
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
        level = _integer(
            actor.effective_level,
            "actor level",
            1,
            MAX_CHARACTER_LEVEL if actor.controlled else 32767,
        )
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
            is_player = (
                actor.controlled and not is_summon and actor.id not in companion_ids
            )
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
            if is_player:
                factor = native_shop_consumable_factor(actor, 118)
                if factor != 100:
                    winners[-1]["shop_consumable_xp_factor"] = factor
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


def authoritative_encounter_kind(
    db, fight_id, group_key, *, dungeon_runtime_available=True
):
    """Classify only a durable dungeon binding or an owned public-world group.

    Dungeon encounter bindings are written when the fight is created and remain
    authoritative after room progression or a player's map changes. An ordinary
    world-group lease has a (map, instance, group) key with public instance zero.
    Private or absent leases are unknown, never guessed from geography. Rifts
    use their own settlement callback and do not enter this adapter.
    """
    _integer(fight_id, "fight identity", 1, (1 << 31) - 1)
    if type(dungeon_runtime_available) is not bool:
        raise ValueError("Invalid dungeon runtime availability")
    if dungeon_runtime_available:
        binding = db.execute(
            "SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s",
            (fight_id,),
        ).fetchone()
        if binding is not None:
            _integer(binding["instance_id"], "dungeon instance", 1, (1 << 63) - 1)
            return "dungeon"
    if (
        isinstance(group_key, (tuple, list))
        and len(group_key) == 3
        and all(type(value) is int for value in group_key)
        and group_key[1] == 0
    ):
        return "ordinary_world"
    return None


def build_drop_context(fight, character, monsters, *, encounter_kind=None):
    """Return the drop-condition context that this runtime can prove.

    `build_context` validates the completed fight, owned winning player,
    selected sheet level, actor roster and trusted monster snapshot. The
    native drop condition ONLY_WHEN_DOWNSCALED is supported by comparing that
    winning actor's effective level with the persisted character level.
    Dungeon/wave negatives are emitted only when the trusted encounter creator
    explicitly tags this route as a world-group, dungeon or rift fight. Map IDs
    and combat terrain IDs are not classifiers. Stasis and Stele remain absent.
    """
    if not isinstance(character, dict):
        raise ValueError("Invalid combat drop character")
    real_level = _integer(
        character.get("level"), "real character level", 1, MAX_CHARACTER_LEVEL
    )
    build_context(fight, character, monsters)
    actor = fight.actors[character["id"]]
    context = {"downscaled": actor.effective_level < real_level}
    if encounter_kind is not None:
        origins = {
            "ordinary_world": (False, False),
            "dungeon": (True, False),
            "infinite_waves": (False, True),
        }
        if encounter_kind not in origins:
            raise ValueError("Unsupported authoritative encounter kind")
        dungeon, infinite_waves = origins[encounter_kind]
        context.update(in_dungeon=dungeon, in_infinite_waves=infinite_waves)
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
        if encounter_kind == "dungeon":
            from wakfu_server import dungeon_difficulty

            durable = dungeon_difficulty.encounter_context(
                db, fight.id, effective_level=fight.actors[character_id].effective_level
            )
            if durable is not None:
                drop_context.update(durable)
                reward_context["dungeon_rate_bp"] = durable["dungeon_drop_rate_bp"]
            from wakfu_server.maps import dungeon_stele

            selected = dungeon_stele.encounter_snapshot(db, fight.id)
            if selected is not None and selected["player_team"] == fight.winner:
                drop_context["selected_stele_item_references"] = selected[
                    "selected_stele_item_references"
                ]
        from wakfu_server.maps import boss_score

        drop_context.update(boss_score.drop_context(db, fight.id))
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
