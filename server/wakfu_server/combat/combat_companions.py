"""Owned companion projections using the original NPC breed characteristic model."""

# Original fpr.fc(eQS.dL(level)) equipment, exported directly from the client.
DEFAULT_EMBLEMS = (
    (20, 20696),
    (35, 20697),
    (50, 20698),
    (65, 20699),
    (80, 20700),
    (95, 20701),
    (110, 20702),
    (125, 20703),
    (140, 20704),
    (155, 20705),
    (170, 20706),
    (185, 20707),
    (200, 22126),
    (215, 29391),
    (230, 32312),
)


def default_equipment_bonuses(level):
    from wakfu_server.equipment_stats import CATALOG, _flat, passive_null_marker

    references = [reference for floor, reference in DEFAULT_EMBLEMS if level >= floor]
    if not references:
        return {}
    template = CATALOG.get(references[-1])
    if template is None:
        raise ValueError("Missing native companion default equipment")
    result = {}
    for effect in template["effects"]:
        if (
            effect["native_variant"] != 0
            or effect["native_active_effect"]
            or passive_null_marker(effect)
        ):
            continue
        flat = _flat(effect)
        if flat is None:
            raise ValueError("Unsupported native companion default equipment effect")
        identity, delta = flat
        result[identity] = result.get(identity, 0) + delta
    return result


COMPANION_BREEDS = frozenset(
    (
        2828,
        2829,
        2830,
        2831,
        2832,
        2833,
        2867,
        3065,
        3071,
        3075,
        3084,
        3081,
        3575,
        3577,
        3578,
        4453,
    )
)


def equipment_bonuses(
    level,
    entries=(),
    owner=None,
    *,
    native_baseline=None,
    native_resource_baseline=None,
):
    if not entries:
        return default_equipment_bonuses(level)
    if owner is None:
        raise ValueError("Real companion equipment requires its owned context")
    from wakfu_server.companion_equipment import stat_bonuses

    result = stat_bonuses(
        entries,
        owner,
        level,
        native_baseline=native_baseline,
        native_resource_baseline=native_resource_baseline,
    )
    from wakfu_server.companion_equipment import unsupported_are_runtime_operators

    if not unsupported_are_runtime_operators(entries, result["unsupported"]) or any(
        result.get("percentages", {}).values()
    ):
        raise ValueError("Companion equipment has unqualified native passive effects")
    return result["stats"]


def native_stats(
    breed_ref,
    level,
    *,
    equipment_entries=(),
    owner=None,
    record=None,
    equipment_rng=None,
):
    """Read ffC/ffx values; companion activation never invents resource constants."""
    from wakfu_server.monsters import reference, statistics
    from wakfu_server.combat_actor_snapshot import native_npc_creation_values

    if type(breed_ref) is not int or breed_ref not in COMPANION_BREEDS:
        raise ValueError("Unknown native companion breed")
    model = reference(breed_ref)
    if type(level) is not int or not model["min_level"] <= level <= model["max_level"]:
        raise ValueError("Companion level outside native breed")
    values = native_npc_creation_values(breed_ref, level)
    from wakfu_server.equipment_resource_bonuses import from_native_values

    resource_baseline = from_native_values(values)
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    bounds = native_actor_catalog()["characteristics"]
    gear = equipment_bonuses(
        level,
        equipment_entries,
        owner,
        native_baseline={identity: row["current"] for identity, row in values.items()},
        native_resource_baseline=resource_baseline,
    )
    for identity in (1, 2, 3, 4):
        delta = gear.get(identity, 0)
        if delta:
            row = bounds[str(identity)]
            for key in ("current", "maximum"):
                values[identity][key] = min(
                    row["hard_maximum"],
                    max(row["hard_minimum"], values[identity][key] + delta),
                )
    projection = None
    if equipment_entries or (record and record.get("equipment_hp_projection")):
        from wakfu_server.companion_equipment import stat_bonuses
        from wakfu_server.companion_hp_equipment import project

        effects = (
            stat_bonuses(
                equipment_entries,
                owner,
                level,
                native_baseline={
                    identity: row["current"]
                    for identity, row in native_npc_creation_values(
                        breed_ref, level
                    ).items()
                },
                native_resource_baseline=resource_baseline,
            )
            if equipment_entries
            else {"hp_operations": ()}
        )
        replay = project(
            record,
            dict(
                raw_current=values[1]["current"],
                raw_maximum=values[1]["maximum"],
                raw_minimum=values[1]["minimum"],
                percentage=0,
                frozen=False,
            ),
            effects["hp_operations"],
            equip_rng=equipment_rng,
        )
        if replay is not None:
            projection = replay.checkpoint()
            values[1]["current"], values[1]["maximum"] = (
                replay.actor.hp,
                replay.actor.max_hp,
            )
    result = dict(
        hp=values[1]["current"],
        max_hp=values[1]["maximum"],
        ap=values[2]["current"],
        mp=values[3]["current"],
        wp=values[4]["current"],
        max_ap=values[2]["maximum"],
        max_mp=values[3]["maximum"],
        max_wp=values[4]["maximum"],
        initiative=statistics(breed_ref, level)["INIT"] + gear.get(35, 0),
    )
    if projection is not None:
        result["equipment_hp_projection"] = projection
    return result


def companion_projection(record, owner_character):
    """Project one durable owned record at its admitted level and owner location."""
    from wakfu_server.monsters import owned_instance, reference, native_abilities

    if (
        record["account_id"] != owner_character["account_id"]
        or record["owner_character_id"] != owner_character["id"]
        or type(record["id"]) is not int
        or record["id"] <= 0
    ):
        raise ValueError("Companion is not assigned to this owning character")
    breed = record["breed_ref"]
    level = record["level"]
    entries = record.get("equipment_entries", ())
    from wakfu_server.combat_actor_snapshot import native_npc_creation_values

    baseline = native_npc_creation_values(breed, level)
    from wakfu_server.equipment_resource_bonuses import from_native_values

    resource_baseline = from_native_values(baseline)
    gear = equipment_bonuses(
        level,
        entries,
        owner_character,
        native_baseline={
            identity: row["current"] for identity, row in baseline.items()
        },
        native_resource_baseline=resource_baseline,
    )
    stats = native_stats(
        breed, level, equipment_entries=entries, owner=owner_character, record=record
    )
    source = owned_instance(
        breed,
        level,
        record["id"],
        map_id=owner_character["map_id"],
        instance_id=owner_character.get("instance_id", 0),
        x=owner_character["x"],
        y=owner_character["y"],
        z=owner_character["z"],
        team=0,
    )
    # Preserve missing health when equipment/level changes the maximum.
    if not 0 <= record["hp"] <= record["max_hp"]:
        raise ValueError("Invalid durable companion health")
    missing = record["max_hp"] - record["hp"]
    source.update(
        stats,
        hp=(
            stats["hp"]
            if stats.get("equipment_hp_projection")
            else max(0, stats["max_hp"] - missing)
        ),
        account_id=record["account_id"],
        owner_character_id=record["owner_character_id"],
        name=record["name"] or reference(breed)["name"],
        native_actor_type=5,
        companion_id=record["id"],
        xp=record["xp"],
        equipment_entries=tuple(entries),
        equipment_stat_bonuses=gear,
        native_abilities=native_abilities(breed, level),
    )
    return source


def registered_source(fight, actor, source):
    """Return only an explicitly admitted sidekick, never infer one from its ID."""
    rows = getattr(fight, "native_companion_sources", {})
    registered = rows.get(str(actor.id))
    if registered is None:
        return None
    if (
        registered != source
        or source.get("native_actor_type") != 5
        or source.get("ref") not in COMPANION_BREEDS
        or source.get("id") != actor.id
        or not actor.controlled
        or source.get("account_id") != actor.owner_id
        or source.get("owner_character_id") not in fight.actors
    ):
        raise ValueError("Companion differs from its admitted native source")
    owner = fight.actors[source["owner_character_id"]]
    if not owner.controlled or owner.owner_id != actor.owner_id:
        raise ValueError("Companion controller is not its owned main fighter")
    return source


def companion_actor(source, team):
    """Build an NPC-shaped controlled sidekick with its original characteristic bounds."""
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_actor_snapshot import build_npc_snapshot

    if (
        source.get("native_actor_type") != 5
        or source.get("ref") not in COMPANION_BREEDS
        or type(source.get("account_id")) is not int
        or source["account_id"] <= 0
    ):
        raise ValueError("Missing owned companion creation projection")
    actor = Actor(
        source["id"],
        team,
        tuple(source[k] for k in ("x", "y", "z")),
        source["hp"],
        source["ap"],
        source["mp"],
        source["initiative"],
        source["level"],
        source["account_id"],
        False,
        max_hp=source["max_hp"],
        direction=3,
    )
    # Snapshot construction is the native NPC path. Control becomes active only
    # after this exact source has supplied the original NPC characteristic rows.
    from dataclasses import replace

    snapshot = build_npc_snapshot(
        source,
        actor,
        wp_current=source["wp"],
        wp_maximum=source["max_wp"],
        running_effects=(),
    )
    stats = dict(snapshot.stats)
    for raw_identity, delta in source.get(
        "equipment_stat_bonuses", default_equipment_bonuses(source["level"])
    ).items():
        identity = int(raw_identity)
        if identity not in (1, 2, 3, 4, 35):
            value = ((stats[identity] + delta + (1 << 31)) % (1 << 32)) - (1 << 31)
            stats[identity] = min(
                snapshot.maxima[identity], max(snapshot.minima[identity], value)
            )
    snapshot = replace(
        snapshot,
        stats=stats,
        provenance=snapshot.provenance + " + native fpr companion emblem",
    )
    hp_projection = source.get("equipment_hp_projection")
    if hp_projection is not None:
        from wakfu_server.equipment_hp_lifecycle import OwnedEwoHPReplay

        projected = OwnedEwoHPReplay.restore(hp_projection).actor
        if (projected.hp, projected.max_hp) != (actor.hp, actor.max_hp):
            raise ValueError("Companion HP checkpoint differs from admitted actor")
        base_maxima, base_minima = dict(snapshot.base_maxima), dict(snapshot.minima)
        percentages, minima = dict(snapshot.percentages), dict(snapshot.minima)
        base_maxima[1] = projected.effect_base_maxima[1]
        base_minima[1] = projected.effect_base_minima[1]
        percentages[1] = projected.effect_percentages[1]
        minima[1] = projected.effect_minima[1]
        snapshot = replace(
            snapshot,
            base_maxima=base_maxima,
            base_minima=base_minima,
            minima=minima,
            percentages=percentages,
            native_hp_on_operand=dict(
                producer="fresh_initial_tB_HP.on_resource_override",
                actor_id=actor.id,
                raw_current=projected.effect_hp_raw_current,
            ),
        )
    snapshot.install(actor)
    actor.controlled = True
    actor.native_controlled_by_ai = False
    actor.native_companion_source = dict(source)
    return actor


def register_companion(fight, actor, source, position):
    """Admit a fresh owned sidekick into placement and the native controller table."""
    from wakfu_server.combat_join_registration import register_joined_fighter
    from wakfu_server.combat_controller_registry import register_native_controller

    rows = getattr(fight, "native_companion_sources", {})
    if str(actor.id) in rows or actor.id in fight.actors:
        raise ValueError("Companion already admitted")
    owner = fight.actors.get(source["owner_character_id"])
    if (
        owner is None
        or owner.owner_id != source["account_id"]
        or owner.team != actor.team
    ):
        raise ValueError("Companion admission requires its actual owning fighter")
    register_joined_fighter(fight, actor, position, controller_id=owner.id)
    fight.native_companion_sources = {**rows, str(actor.id): dict(source)}
    registered_source(fight, actor, source)
    if not hasattr(fight, "native_global_pv_collections"):
        register_native_controller(
            fight, actor.id, team=actor.team, controller_id=owner.id
        )


def world_spawn(source, *, direction=3):
    """Original ctE NPC actor creation with identity kind5 and sL ownership."""
    import struct
    from wakfu_server.monsters import owned_instance
    from wakfu_server.combat_monster_world import world_actor

    base = owned_instance(
        source["ref"],
        source["level"],
        source["id"],
        map_id=source["map_id"],
        instance_id=source["instance_id"],
        x=source["x"],
        y=source["y"],
        z=source["z"],
        team=source["team"],
    )
    blob = world_actor(
        base,
        name=source["name"],
        group_id=source["owner_character_id"],
        direction=direction,
        companion_source=source,
    )
    if len(blob) > 65535:
        raise ValueError("Companion world appearance too large")
    return b"\x00\x01" + struct.pack(">BqH", 5, source["id"], len(blob)) + blob


def registered_companion_ids(fight):
    rows = getattr(fight, "native_companion_sources", {})
    if not isinstance(rows, dict):
        raise ValueError("Malformed native companion registration")
    result = set()
    for key, source in rows.items():
        if not isinstance(source, dict) or str(source.get("id")) != key:
            raise ValueError("Invalid companion registration identity")
        actor = fight.actors.get(source["id"])
        if actor is None or registered_source(fight, actor, source) is None:
            raise ValueError("Missing admitted companion actor")
        result.add(actor.id)
    return frozenset(result)


def validate_durable_roster(db, fight):
    identities = registered_companion_ids(fight)
    if not identities:
        return
    rows = db.execute(
        "SELECT companion_id,account_id,owner_character_id,team FROM combat_fight_companions "
        "WHERE fight_id=%s ORDER BY companion_id",
        (fight.id,),
    ).fetchall()
    if {row["companion_id"] for row in rows} != identities:
        raise ValueError("Companion checkpoint differs from durable fight roster")
    for row in rows:
        source = fight.native_companion_sources[str(row["companion_id"])]
        if (
            source["account_id"] != row["account_id"]
            or source["owner_character_id"] != row["owner_character_id"]
            or fight.actors[row["companion_id"]].team != row["team"]
        ):
            raise ValueError("Companion durable ownership or team changed")


def admit_owned_companions(db, store, session, fight, *, owner_character=None):
    """Admit the complete selected sidekick roster in the caller's placement transaction."""
    from copy import deepcopy
    from wakfu_server.characters import companions
    from wakfu_server.combat_npc_initialization import (
        initial_property_counts,
        install_initial_properties,
        initial_plans,
        initialize_ordinary_npcs,
    )

    if fight.phase != "placement":
        raise ValueError("Companions may join only placement")
    store.lock_character(
        db, session.account_id, session.generation, session.character_id
    )
    owner = owner_character or store.character(
        session.account_id, session.character_id, db
    )
    sources = companions.combat_sources(
        db, session.account_id, session.character_id, owner_character=owner, store=store
    )
    sources = list(sources.values()) if isinstance(sources, dict) else list(sources)
    if not sources:
        return dict(fight=fight, companions=(), sources={}, actors=(), packets=())
    leader = fight.actors.get(session.character_id)
    if leader is None or not leader.controlled or leader.owner_id != session.account_id:
        raise ValueError("Companion admission requires the selected main fighter")
    occupied = {actor.position for actor in fight.actors.values()}
    cells = sorted(set(fight.placement[leader.team]) - occupied)
    if sum(actor.team == leader.team for actor in fight.actors.values()) + len(
        sources
    ) > 6 or len(cells) < len(sources):
        raise ValueError("Insufficient team capacity for selected companions")
    candidate = deepcopy(fight)
    projected, actors = {}, []
    for source, position in zip(sources, cells):
        source = dict(
            source, team=leader.team, x=position[0], y=position[1], z=position[2]
        )
        actor = companion_actor(source, leader.team)
        if actor.hp <= 0:
            raise ValueError("A defeated companion cannot enter combat")
        properties = initial_property_counts({actor.id: source})
        install_initial_properties(actor, properties[actor.id])
        # Native bje constructors execute innate states before their QK enters
        # QI. Detached initialization temporarily removes this fresh actor from
        # the roster, so registering its physical slot first leaves a stale
        # QI population while constructor children query obstacles.
        candidate.actors[actor.id] = actor
        candidate.native_companion_sources = {
            **getattr(candidate, "native_companion_sources", {}),
            str(actor.id): dict(source),
        }
        from .combat_instance_publication import refresh_owned_encounter

        refresh_owned_encounter(candidate)
        initialize_ordinary_npcs(
            candidate, {actor.id: source}, initial_plans(candidate, {actor.id: source})
        )
        del candidate.actors[actor.id]
        del candidate.native_companion_sources[str(actor.id)]
        register_companion(candidate, actor, source, position)
        companions.enroll(
            db,
            fight.id,
            actor.id,
            session.account_id,
            session.character_id,
            session.generation,
            leader.team,
        )
        projected[actor.id] = source
        actors.append(actor)
    candidate._check_positions()
    validate_durable_roster(db, candidate)
    return dict(
        fight=candidate,
        companions=tuple(sources),
        sources=projected,
        actors=tuple(actors),
        packets=tuple((12608, world_spawn(row)) for row in projected.values()),
    )


def resolve_action(fight, actor, character, owner_id, spell_uid):
    """Resolve original bPD spell-reference UIDs under actual fdy input ownership."""
    from wakfu_server.combat_effective_control import require_effective_owner
    from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook

    source = getattr(fight, "native_companion_sources", {}).get(str(actor.id))
    if source is None or registered_source(fight, actor, source) is None:
        raise ValueError("Missing admitted companion spell source")
    require_effective_owner(fight, actor, owner_id)
    if (
        character["account_id"] != owner_id
        or character["id"] != source["owner_character_id"]
    ):
        raise ValueError("Companion spell owner differs from its selected main")
    from wakfu_server.combat_spell_grant_book import merged_grant_book
    from wakfu_server.combat_morph_spellbook import active_morph_book

    book = merged_grant_book(
        fight,
        actor.id,
        active_morph_book(
            fight, actor.id, ordinary_npc_spellbook(fight, actor, source)
        ),
    )
    if type(spell_uid) is not int or spell_uid not in book.levels:
        raise ValueError("Companion spell is absent from its native book")
    return spell_uid, book.levels[spell_uid]


def settle_companion_health(db, store, fight):
    """Persist terminal sidekick health separately from human leases and rewards."""
    from wakfu_server.characters.companions import settle_health

    validate_durable_roster(db, fight)
    for identity in registered_companion_ids(fight):
        actor = fight.actors[identity]
        settle_health(db, store, fight.id, identity, actor.hp, actor.max_hp)


def fighter_stats(fight, actor):
    from wakfu_server.combat_actor import actual_monster_actor_stats
    from wakfu_server.breed_resources import live_wp

    source = getattr(fight, "native_companion_sources", {}).get(str(actor.id))
    if source is None or registered_source(fight, actor, source) is None:
        raise ValueError("Missing registered companion fighter")
    return actual_monster_actor_stats(
        source,
        actor,
        fight.id,
        fight=fight,
        wp_current=live_wp(fight, actor.id)[0],
        wp_maximum=live_wp(fight, actor.id)[1],
    )


def bootstrap_actor_type(fight, actor):
    """Keep companion kind5 independent of its human input controller."""
    source = getattr(fight, "native_companion_sources", {}).get(str(actor.id))
    if source is not None:
        registered_source(fight, actor, source)
        return 5
    return 0 if actor.controlled else 1


def report_metadata(db, fight, metadata):
    """Project committed sidekick receipts into native FightMonster fields2/5."""
    from wakfu_server.characters.companions import level_for_xp

    result = {identity: dict(row) for identity, row in metadata.items()}
    for identity in registered_companion_ids(fight):
        source = fight.native_companion_sources[str(identity)]
        row = db.execute(
            "SELECT c.xp,p.experience_award,p.experience_settled_at FROM combat_fight_companions p "
            "JOIN account_companions c ON c.id=p.companion_id AND c.account_id=p.account_id "
            "WHERE p.fight_id=%s AND p.companion_id=%s",
            (fight.id, identity),
        ).fetchone()
        if row is None or row["experience_settled_at"] is None:
            raise ValueError("Companion report requires its committed reward receipt")
        won = row["experience_award"]
        end = source["xp"] + won
        result[identity] = dict(
            kind="monster",
            ref=source["ref"],
            owner_account_id=source["account_id"],
            xp_info=dict(
                end_xp=end,
                won_xp=won,
                start_level=level_for_xp(end - won),
                end_level=level_for_xp(end),
            ),
        )
        from wakfu_server.combat_drops import _stored_batch, report_loots

        batch = _stored_batch(db, fight.id, source["owner_character_id"])
        if batch is not None and any(
            profile["actor_id"] == identity
            for profile in batch.snapshot.get("companion_rolls", ())
        ):
            result[identity]["loots"] = report_loots(batch, loot_actor_id=identity)
    return result


def loot_profiles(fight, owner_character_id):
    """Native extra loot lines use each sidekick's own frozen characteristics."""
    from wakfu_server.combat_drops import (
        native_prospection_bonus,
        native_shop_drop_factor,
    )

    return tuple(
        dict(
            actor_id=identity,
            prospecting_bonus=native_prospection_bonus(fight.actors[identity]),
            shop_consumable_factor=native_shop_drop_factor(fight.actors[identity]),
        )
        for identity in sorted(registered_companion_ids(fight))
        if fight.native_companion_sources[str(identity)]["owner_character_id"]
        == owner_character_id
    )
