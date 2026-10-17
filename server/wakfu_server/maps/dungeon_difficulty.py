"""Owned dungeon difficulty selection and immutable encounter reward authority.

Native Stasis selections range from the definition minimum through ten. The
competitive target is the installed eQS ceiling band for the native dungeon
level. Human labels and a player's numerical reduction do not select this mode.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import struct

from psycopg.types.json import Jsonb


BANDS = (20, 35, 50, 65, 80, 95, 110, 125, 140, 155, 170, 185, 200, 215, 230)


def decode_request(body):
    """Installed cou/ayq12223: actor int64, Stasis int32, instance int64."""
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Invalid dungeon difficulty request")
    character_id, stasis_level, instance_id = struct.unpack(">qiq", body)
    _integer(character_id, "actor", 1, (1 << 63) - 1)
    _integer(instance_id, "instance", 1, (1 << 63) - 1)
    _integer(stasis_level, "Stasis level", 1, 10)
    return dict(
        character_id=character_id, instance_id=instance_id, stasis_level=stasis_level
    )


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid dungeon " + name)
    return value


def ceiling_band(level):
    """eQS.dK exact supported ceiling; unknown configured fallback is rejected."""
    _integer(level, "native level", 1, BANDS[-1])
    return next(band for band in BANDS if band >= level)


def definition(db, definition_id):
    row = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_difficulty_catalog'"
    ).fetchone()
    catalog = None if row is None else row["value"]
    native = (
        None
        if not isinstance(catalog, dict)
        else catalog.get("definitions", {}).get(str(definition_id))
    )
    if native is None:
        raise ValueError("Dungeon has no verified native difficulty definition")
    _integer(native["minimum_stasis"], "minimum Stasis", 1, 10)
    _integer(native["native_level"], "native level", 1, BANDS[-1])
    return native


def selection(db, instance_id):
    """Serialize selection and encounter creation on the same durable run row."""
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None:
        raise ValueError("Dungeon run is absent")
    old = db.execute(
        "SELECT * FROM dungeon_difficulty_selections WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if old is not None:
        return old
    policy = db.execute(
        "SELECT difficulty_level,max_level FROM dungeon_context_policy_versions WHERE route_key=%s AND policy_version=%s",
        (run["context_route_key"], run["context_policy_version"]),
    ).fetchone()
    if policy is None:
        raise ValueError("Dungeon run lacks a pinned difficulty policy")
    level, cap = policy["difficulty_level"], policy["max_level"]
    try:
        native = definition(db, run["definition_id"])
    except ValueError:
        native = None
    if native is not None:
        level = max(level, native["minimum_stasis"])
        if native.get("forced_competitive", False):
            cap = ceiling_band(native["native_level"])
    return db.execute(
        "INSERT INTO dungeon_difficulty_selections(instance_id,stasis_level,competitive,competitive_max_level) VALUES(%s,%s,%s,%s) RETURNING *",
        (instance_id, level, cap > 0, cap),
    ).fetchone()


def select(
    store,
    account_id,
    generation,
    character_id,
    *,
    stasis_level,
    competitive=None,
    expected_instance_id=None
):
    """Owned leader selects freely before combat, or lowers between encounters.

    None preserves competitive mode for the native in-dungeon Stasis request.
    Earlier encounter profiles stay immutable; the next roster is prepared
    using the selected revision and rejects concurrent selection changes.
    """
    _integer(stasis_level, "Stasis level", 1, 10)
    if competitive is not None and type(competitive) is not bool:
        raise ValueError("Invalid dungeon competitive selection")
    if expected_instance_id is not None:
        _integer(expected_instance_id, "requested instance", 1, (1 << 63) - 1)
    from wakfu_server import player_parties

    with store.connection() as db:
        initial = db.execute(
            "SELECT m.party_id FROM player_party_members m WHERE m.character_id=%s",
            (character_id,),
        ).fetchone()
        if initial is None:
            raise ValueError("Dungeon selection requires an owned party")
        ids = [
            r["character_id"]
            for r in db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (initial["party_id"],),
            ).fetchall()
        ]
        player_parties._lock_members(db, ids)
        store.lock_character(db, account_id, generation, character_id)
        owned = store.character(account_id, character_id, db)
        party = db.execute(
            "SELECT * FROM player_parties WHERE id=%s FOR UPDATE",
            (initial["party_id"],),
        ).fetchone()
        if party is None or party["leader_id"] != character_id:
            raise ValueError("Only the current party leader selects dungeon difficulty")
        run = db.execute(
            "SELECT i.* FROM dungeon_instances i JOIN dungeon_instance_members m ON m.instance_id=i.instance_id "
            "WHERE i.party_id=%s AND i.status='active' AND m.character_id=%s AND m.status='active' FOR UPDATE OF i",
            (party["id"], character_id),
        ).fetchone()
        if run is None or owned["instance_id"] != run["instance_id"]:
            raise ValueError(
                "Dungeon difficulty selection requires the current owned instance"
            )
        if (
            expected_instance_id is not None
            and run["instance_id"] != expected_instance_id
        ):
            raise ValueError("Dungeon request targets another instance")
        native = definition(db, run["definition_id"])
        if not native.get("difficulty_available", False):
            raise ValueError("Native dungeon does not allow Stasis selection")
        if stasis_level < native["minimum_stasis"]:
            raise ValueError("Stasis is below the native dungeon minimum")
        old = selection(db, run["instance_id"])
        mode = native.get("forced_competitive", False) or (
            old["competitive"] if competitive is None else competitive
        )
        cap = ceiling_band(native["native_level"]) if mode else 0
        if (old["stasis_level"], old["competitive"], old["competitive_max_level"]) == (
            stasis_level,
            mode,
            cap,
        ):
            return old
        admitted = (
            db.execute(
                "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s LIMIT 1",
                (run["instance_id"],),
            ).fetchone()
            is not None
        )
        if admitted:
            if (
                mode != old["competitive"]
                or cap != old["competitive_max_level"]
                or stasis_level > old["stasis_level"]
            ):
                raise ValueError(
                    "Dungeon difficulty is frozen except for reductions between encounters"
                )
            if db.execute(
                "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s AND status='active' LIMIT 1",
                (run["instance_id"],),
            ).fetchone():
                raise ValueError(
                    "Dungeon Stasis cannot change during an active encounter"
                )
        return db.execute(
            "UPDATE dungeon_difficulty_selections SET stasis_level=%s,competitive=%s,competitive_max_level=%s,"
            "revision=revision+1,selected_by=%s,updated_at=CURRENT_TIMESTAMP WHERE instance_id=%s RETURNING *",
            (stasis_level, mode, cap, character_id, run["instance_id"]),
        ).fetchone()


def configure_entry(db, instance_id, character_id, *, stasis_level, competitive):
    """Configure an authenticated new entry before roster preparation/movement."""
    _integer(stasis_level, "Stasis level", 1, 10)
    if type(competitive) is not bool:
        raise ValueError("Invalid dungeon competitive selection")
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if run is None:
        raise ValueError("Difficulty entry run is absent")
    native = definition(db, run["definition_id"])
    if not native.get("difficulty_available", False):
        raise ValueError("Native dungeon does not allow Stasis selection")
    if stasis_level < native["minimum_stasis"]:
        raise ValueError("Stasis is below the native dungeon minimum")
    competitive = native.get("forced_competitive", False) or competitive
    chosen = selection(db, instance_id)
    cap = ceiling_band(native["native_level"]) if competitive else 0
    if (
        chosen["stasis_level"],
        chosen["competitive"],
        chosen["competitive_max_level"],
    ) == (stasis_level, competitive, cap):
        return chosen
    if run["created_by_character_id"] != character_id:
        raise ValueError("Difficulty entry does not belong to its authenticated leader")
    if db.execute(
        "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s LIMIT 1",
        (instance_id,),
    ).fetchone():
        raise ValueError("Dungeon difficulty is frozen after its first encounter")
    return db.execute(
        "UPDATE dungeon_difficulty_selections SET stasis_level=%s,competitive=%s,competitive_max_level=%s,"
        "revision=revision+1,selected_by=%s,updated_at=CURRENT_TIMESTAMP WHERE instance_id=%s RETURNING *",
        (stasis_level, competitive, cap, character_id, instance_id),
    ).fetchone()


def encounter_scaling(db, instance_id):
    """Lock run selection and return the profile used to create combat actors.

    Callers retain this transaction through actor creation and bind_encounter,
    passing selection_revision to reject a stale roster admission.
    """
    chosen = selection(db, instance_id)
    run = db.execute(
        "SELECT definition_id FROM dungeon_instances WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    try:
        native = definition(db, run["definition_id"])
    except ValueError:
        # Legacy configured runs remain playable without invented Stasis rewards.
        return None
    if not native.get("difficulty_available", False):
        return None
    catalog = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_difficulty_catalog'"
    ).fetchone()["value"]
    profile = catalog["profiles"][native["profile_key"]]
    index = chosen["stasis_level"] - 1
    reward_key = (
        "competitive_reward_percent"
        if chosen["competitive"]
        else "normal_reward_percent"
    )
    snapshot = dict(
        schema_version=1,
        instance_id=instance_id,
        selection_revision=chosen["revision"],
        stasis_level=chosen["stasis_level"],
        competitive=chosen["competitive"],
        competitive_max_level=chosen["competitive_max_level"],
        hp_percent=profile["hp_percent"][index],
        damage_percent=profile["damage_percent"][index],
        reward_rate_bp=profile[reward_key][index] * 100,
        profile_key=native["profile_key"],
    )
    return snapshot


def freeze_encounter(db, instance_id, fight_id, *, expected_selection_revision=None):
    """Freeze a run selection once; later selection cannot change loot authority."""
    prior = db.execute(
        "SELECT snapshot FROM dungeon_encounter_difficulties WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if prior is not None:
        if prior["snapshot"]["instance_id"] != instance_id:
            raise ValueError("Dungeon difficulty replay changed its instance")
        return prior["snapshot"]
    snapshot = encounter_scaling(db, instance_id)
    if snapshot is None:
        return None
    if (
        expected_selection_revision is not None
        and snapshot["selection_revision"] != expected_selection_revision
    ):
        raise ValueError("Dungeon actor scaling selection revision changed")
    db.execute(
        "INSERT INTO dungeon_encounter_difficulties(fight_id,instance_id,selection_revision,snapshot) VALUES(%s,%s,%s,%s)",
        (fight_id, instance_id, snapshot["selection_revision"], Jsonb(snapshot)),
    )
    return snapshot


def encounter_context(db, fight_id, *, effective_level):
    """Return only durable native criteria authority for this winning actor."""
    _integer(effective_level, "winning actor level", 1, MAX_CHARACTER_LEVEL)
    row = db.execute(
        "SELECT snapshot FROM dungeon_encounter_difficulties WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if row is None:
        return None
    snapshot = row["snapshot"]
    cap = snapshot["competitive_max_level"]
    eligible = snapshot["competitive"] and 0 < effective_level <= cap
    return dict(
        in_dungeon=True,
        in_infinite_waves=False,
        stasis_level=snapshot["stasis_level"],
        downscaled=bool(eligible),
        dungeon_drop_rate_bp=snapshot["reward_rate_bp"],
    )
