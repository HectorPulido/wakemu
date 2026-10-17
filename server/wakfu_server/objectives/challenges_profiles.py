"""Reviewed finite encounter profiles using real enabled native monsters."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from psycopg.types.json import Jsonb


def validate_profile(value):
    from wakfu_server.monsters import reference, statistics
    from wakfu_server.monster_minigame_policy import require_ordinary_spawn
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_terrain import map_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    required = {
        "key",
        "title",
        "enabled",
        "min_level",
        "max_level",
        "map_id",
        "anchor",
        "roster",
        "source_route_key",
    }
    if type(value) is not dict or set(value) != required:
        raise ValueError("Invalid challenge profile fields")
    if any(
        type(value[k]) is not str or not 1 <= len(value[k]) <= 160
        for k in ("key", "title", "source_route_key")
    ):
        raise ValueError("Invalid challenge profile identity")
    if type(value["enabled"]) is not bool or any(
        type(value[k]) is not int for k in ("min_level", "max_level", "map_id")
    ):
        raise ValueError("Invalid challenge profile bounds")
    if (
        not 1 <= value["min_level"] <= value["max_level"] <= MAX_CHARACTER_LEVEL
        or value["map_id"] <= 0
    ):
        raise ValueError("Invalid challenge level range")
    if (
        type(value["anchor"]) is not list
        or len(value["anchor"]) != 3
        or any(type(x) is not int for x in value["anchor"])
    ):
        raise ValueError("Invalid native challenge anchor")
    if type(value["roster"]) is not list or not value["roster"]:
        raise ValueError("Missing challenge roster")
    # Read only the indexed admission policy. Decoding the full executable
    # effect document would allocate hundreds of MB in the objectives service.
    enabled = native_catalog.record(
        DATA_ROOT / "native-npc-spell-effect-trees.json",
        "activation_policy",
        "enabled_monsters",
    )
    if not isinstance(enabled, dict):
        raise ValueError("Missing indexed native NPC activation authority")
    count = 0
    for row in value["roster"]:
        if (
            type(row) is not dict
            or set(row) != {"ref_id", "level", "count"}
            or any(type(v) is not int for v in row.values())
        ):
            raise ValueError("Invalid challenge roster entry")
        native = reference(row["ref_id"])
        require_ordinary_spawn(row["ref_id"])
        statistics(row["ref_id"], row["level"])
        policy = enabled.get(str(row["ref_id"]))
        if (
            policy is None
            or not policy["min_level"] <= row["level"] <= policy["max_level"]
        ):
            raise ValueError("Challenge monster is not enabled at its native level")
        if (
            not 1 <= row["count"] <= 12
            or not native["min_level"] <= row["level"] <= native["max_level"]
        ):
            raise ValueError("Invalid challenge monster quantity or level")
        count += row["count"]
    if not 1 <= count <= 12:
        raise ValueError("Challenge exceeds native team capacity")
    enemy_formation(
        map_geometry(value["map_id"]), value["anchor"], count, player_slots=12
    )
    return value


def list_profiles(db):
    return db.execute(
        "SELECT * FROM objectives_challenge_profiles ORDER BY key"
    ).fetchall()


def put_profile(db, definition, expected_revision):
    from .repository import ConflictError

    value = validate_profile(definition)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Invalid challenge profile revision")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("challenge-profile:" + value["key"],),
    )
    old = db.execute(
        "SELECT * FROM objectives_challenge_profiles WHERE key=%s FOR UPDATE",
        (value["key"],),
    ).fetchone()
    if (old["revision"] if old else 0) != expected_revision:
        raise ConflictError("Challenge profile revision changed")
    from .rankings import week_key

    # A scored weekly competition must keep the same content for every entrant.
    if (
        old
        and old["definition"] != value
        and db.execute(
            "SELECT 1 FROM objectives_challenge_runs WHERE profile_key=%s AND week_key=%s LIMIT 1",
            (value["key"], week_key()),
        ).fetchone()
    ):
        raise ConflictError(
            "Current weekly challenge content is frozen after the first attempt"
        )
    return db.execute(
        "INSERT INTO objectives_challenge_profiles(key,definition) VALUES(%s,%s) ON CONFLICT(key) DO UPDATE SET definition=EXCLUDED.definition,revision=objectives_challenge_profiles.revision+1,updated_at=CURRENT_TIMESTAMP RETURNING *",
        (value["key"], Jsonb(value)),
    ).fetchone()
