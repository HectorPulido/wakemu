"""Native protector satisfaction states, derived from regional wishes."""

from __future__ import annotations
from wakfu_server import native_catalog as protocol_catalog

import json
from functools import lru_cache
from pathlib import Path


_CATALOG = (
    Path(__file__).resolve().parents[2]
    / "protocol"
    / "territory-protector-bonuses.json"
)


@lru_cache(maxsize=1)
def _catalog():
    return protocol_catalog.load(_CATALOG)


def state_id(satisfied: int, total: int) -> int | None:
    """Return native protector status for completed/eligible wishes."""
    if type(satisfied) is not int or type(total) is not int:
        raise ValueError("Wish counts must be integers")
    if total < 0 or satisfied < 0 or satisfied > total:
        raise ValueError("Wish counts are outside their valid range")
    if total == 0:
        return None
    if satisfied == 0:
        return 1917
    if satisfied == total:
        return 1916
    return 1915


def state_effects(satisfied: int, total: int) -> dict | None:
    """Return the native effect rows for the derived state, or None if empty."""
    selected = state_id(satisfied, total)
    if selected is None:
        return None
    return _catalog()["states"][str(selected)]


def _counts(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} counts must be a family-to-count mapping")
    normalized = {}
    for family_id, count in value.items():
        if type(family_id) is not int or family_id < 0:
            raise ValueError(f"Invalid {label} family id")
        if type(count) is not int or count < 0:
            raise ValueError(f"Invalid {label} family count")
        normalized[family_id] = count
    return normalized


def evaluate_population(
    territory_id: int, monster_counts: dict, plant_counts: dict
) -> dict:
    """Evaluate native aMD wish ranges against a complete regional snapshot.

    Missing family keys mean zero population. Callers must provide complete,
    instance-scoped counts; snapshot completeness is enforced by the caller.
    """
    if type(territory_id) is not int or territory_id <= 0:
        raise ValueError("Invalid native territory id")
    monsters = _counts(monster_counts, "monster")
    plants = _counts(plant_counts, "plant")
    territory = _catalog()["territories"].get(str(territory_id))
    if territory is None or territory["map_id"] is None:
        raise ValueError("Native territory has no verified map-region mapping")

    satisfied = 0
    total = 0
    for key, counts in (("monster_wishes", monsters), ("plant_wishes", plants)):
        for wish in territory[key]:
            total += 1
            population = counts.get(wish["family_id"], 0)
            if wish["minimum"] <= population <= wish["maximum"]:
                satisfied += 1

    selected = state_id(satisfied, total)
    return {
        "territory_id": territory_id,
        "map_id": territory["map_id"],
        "satisfied_wishes": satisfied,
        "total_wishes": total,
        "state_id": selected,
        "effects": None
        if selected is None
        else _catalog()["states"][str(selected)]["effects"],
    }


def current_region(db, character: dict) -> dict | None:
    """Derive the current region status from a complete map/instance snapshot.

    Population counts include all plants and living monster-group members in
    this character's map instance. Entities are assigned to regions by the
    native region grid, regardless of whether their cell is plantable.
    Unknown terrain or unresolved entities suppress the bonus rather than
    applying a partial population calculation.
    """
    if not isinstance(character, dict):
        raise ValueError("Invalid character context")
    map_id = character.get("map_id")
    instance_id = character.get("instance_id", 0)
    x, y = character.get("x"), character.get("y")
    if (
        type(map_id) is not int
        or not 0 < map_id < 2**31
        or type(instance_id) is not int
        or not 0 <= instance_id < 2**63
        or type(x) is not int
        or type(y) is not int
    ):
        return None
    from wakfu_server import ecology_context, ecology_population, territory_cells

    try:
        territory_id = territory_cells.region_at(map_id, x, y)
    except (KeyError, ValueError):
        return None

    try:
        population = ecology_population.snapshot(
            db,
            map_id,
            instance_id,
            locate=ecology_context.population_region,
            exclude_unassigned=True,
        )
        if not population["complete"]:
            return None
        counts = population["regions"].get(territory_id, {"plant": {}, "monster": {}})
        return evaluate_population(
            territory_id,
            dict(counts.get("monster", {})),
            dict(counts.get("plant", {})),
        )
    except (KeyError, ValueError):
        return None


def profession_xp_percent(region: dict | None, category: str) -> int:
    """Return the verified regional planting/harvest XP modifier percentage."""
    classes = {"planting": 2007, "harvest": 2008}
    if category not in classes:
        raise ValueError("Unsupported territorial profession category")
    if region is None or region.get("state_id") is None:
        return 0
    target = classes[category]
    matches = [
        effect
        for effect in region.get("effects", ())
        if effect.get("effect_class") == target
        and effect.get("variant") == 0
        and effect.get("criteria") == ""
        and len(effect.get("parameters", ())) == 1
    ]
    if len(matches) != 1:
        return 0
    value = matches[0]["parameters"][0]
    if type(value) not in (int, float) or not -100 <= value <= 100:
        return 0
    return int(value)


def control_health_policy(db=None):
    """Load the native tooltip health policy exclusively from PostgreSQL."""
    if db is None:
        with protocol_catalog._database().connection() as connection:
            return control_health_policy(connection)
    row = db.execute(
        "SELECT value FROM settings WHERE name='territory_control_health_policy'"
    ).fetchone()
    policy = None if row is None else row["value"]
    if (
        not isinstance(policy, dict)
        or set(policy) != {"schema_version", "states"}
        or policy["schema_version"] != 1
        or not isinstance(policy["states"], dict)
        or set(policy["states"]) != {"1915", "1916", "1917"}
        or any(
            type(value) is not int or not -1000 <= value <= 1000
            for value in policy["states"].values()
        )
    ):
        raise ValueError("Missing or invalid territory control health policy")
    return policy["states"]


def stat_bonuses(region: dict | None, *, health_policy=None) -> dict[int, int]:
    """Return temporary health, Wisdom and Prospection contributions."""
    if region is None or region.get("state_id") is None:
        return {}
    mappings = {166: (36, 1), 167: (36, -1), 162: (33, 1), 163: (33, -1)}
    result = {}
    for effect in region.get("effects", ()):
        mapping = mappings.get(effect.get("effect_class"))
        if mapping is None:
            continue
        identity, sign = mapping
        values = effect.get("parameters", ())
        if (
            effect.get("variant") != 0
            or effect.get("criteria") != ""
            or len(values) != 1
            or type(values[0]) not in (int, float)
            or not 0 <= values[0] <= 1000
            or identity in result
        ):
            return {}
        result[identity] = sign * int(values[0])
    policy = control_health_policy() if health_policy is None else health_policy
    state = str(region["state_id"])
    if state not in policy:
        raise ValueError("Unknown territory control health state")
    result[1] = policy[state]
    return result


def reconcile_owned(
    store,
    account_id,
    generation,
    character,
    *,
    db=None,
    selected_character_id=None,
    region=None,
    bonuses=None,
):
    """Apply regional HP under the selected owner's lease before publication.

    Location comes from the live caller: a walking hero's stored position can
    lag behind its owner's position. Health and equipment always come from the
    locked durable character, never an asynchronous ecology proposal.
    """
    from contextlib import nullcontext
    from wakfu_server.territory_health_lifecycle import reconcile_in_transaction

    selected_id = (
        character["id"] if selected_character_id is None else selected_character_id
    )
    with store.connection() if db is None else nullcontext(db) as connection:
        store.lock_character(connection, account_id, generation, selected_id)
        if selected_id != character["id"]:
            store.lock_character(
                connection, account_id, generation, character["id"], selected=False
            )
        canonical = store.character(account_id, character["id"], connection)
        for key in ("hp", "max_hp", "hp_damage", "health_dead", "hp_zero_valid"):
            if key in character and canonical[key] != character[key]:
                raise ValueError("Stale owned territorial health observation")
        location = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        canonical.update(location)
        policy = control_health_policy(connection)
        if bonuses is None:
            region = current_region(connection, canonical)
            bonuses = stat_bonuses(region, health_policy=policy)
        else:
            # Worker proposals can outlive a policy change. Their native state
            # remains useful, but only the current policy owns the HP amount.
            bonuses = dict(bonuses)
            state = None if region is None else region.get("state_id")
            bonuses[1] = 0 if state is None else policy[str(state)]
        state = None if region is None else region.get("state_id")
        canonical = reconcile_in_transaction(
            connection,
            canonical,
            applied_flat=bonuses.get(1, 0),
            state_id=state,
            map_id=location["map_id"],
            instance_id=location["instance_id"],
            region_id=None if region is None else region.get("territory_id"),
            now_ms=int(store.clock() * 1000),
        )
        result = dict(character)
        result.update(canonical)
        result.update(location)
        result["territory_state_id"] = state
        result["territory_stat_bonuses"] = dict(bonuses)
        return result


def attach_character(db, character: dict) -> dict:
    """Return a detached actor input with fresh nonpersistent regional stats."""
    result = dict(character)
    region = current_region(db, character)
    result["territory_state_id"] = None if region is None else region.get("state_id")
    result["territory_stat_bonuses"] = stat_bonuses(
        region, health_policy=control_health_policy(db)
    )
    from wakfu_server.equipment_stats import effective_character

    # Actor construction and its native snapshot must share the same maximum.
    # Recompute from the owned build; do not increment an already derived HP.
    return effective_character(result)


def refresh_world(
    store, character: dict, *, generation=None
) -> list[tuple[int, bytes]]:
    """Publish authoritative regional characteristics on an exploration actor.

    Derived bonuses never enter persistent character storage. Recompute even
    inside one region because harvesting, planting and population changes can
    change protector satisfaction without a map transition. The publication
    marker is separate from the actor input: combat can attach fresh bonuses
    without having published an exploration refresh to the owning client.
    """
    if generation is not None:
        canonical = reconcile_owned(
            store, character["account_id"], generation, character
        )
        # Persistence precedes socket delivery. A failed send must not leave
        # the session's next regeneration CAS using its superseded maximum.
        character.update(canonical)
        # The owned reconciliation already observed the complete population.
        # World codecs reduce the full owned build themselves; do not scan the
        # same region a second time just to publish its characteristics.
        attached = canonical
    else:
        with store.connection() as db:
            attached = attach_character(db, character)
    bonuses = attached["territory_stat_bonuses"]
    previous = character.get("_published_territory_stat_bonuses")
    state = attached["territory_state_id"]
    previous_state = character.get("_published_territory_state_id")
    if (
        previous == bonuses
        and "_published_territory_state_id" in character
        and previous_state == state
    ):
        character["territory_stat_bonuses"] = bonuses
        character["territory_state_id"] = state
        return []
    # Serialize before changing live state so failed serialization is retried.
    # The native exploration codec uses fightID=-1 and preserves owned HP,
    # equipment, aptitudes and the selected build rather than template stats.
    from wakfu_server.territory_bonus_wire import delta

    packets = (*world_packets(attached), *delta(character["id"], previous_state, state))
    character["territory_state_id"] = state
    character["_published_territory_state_id"] = state
    character["territory_stat_bonuses"] = bonuses
    character["_published_territory_stat_bonuses"] = dict(bonuses)
    return list(packets)


def world_packets(character: dict) -> tuple[tuple[int, bytes], ...]:
    """Synchronize bounds, native HUD bindings and exploration resources."""
    from wakfu_server.characters.world_characteristic_publication import packets

    return packets(character, world_packet(character))


def world_packet(character: dict) -> tuple[int, bytes]:
    """Refresh exploration statistics without replacing movement or fight state.

    Native eHf.PUBLIC_CHARACTERISTICS (39) contains only eHe.pLO, the same
    owned ``pl`` public-characteristics section used by the full actor codec.
    eHd.ew reads only the sections selected by this format. In particular it
    does not deserialize POSITION, FIGHT_PROPERTIES or XP during a local walk.
    Explicit native defaults still clear removed regional contributions.
    """
    from wakfu_server import wire
    from wakfu_server.combat_world_refresh import actor_refresh

    blob = b"\x27" + wire.owned_public_characteristics(character)
    return actor_refresh(character["id"], blob)
