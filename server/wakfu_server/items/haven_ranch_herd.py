"""Account-owned native creatures under an explicit Wakemu generation policy.

Candidate slots preserve original multiplicities. Native constructor defaults
define the initial instance; no personality amounts or lifecycle rewards are
inferred from presentation metadata. Source debit and ownership commit together.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import random
import secrets
import struct

from psycopg.types.json import Jsonb

POLICY = "wakemu_native_seeded_herd_v1"
CATALOG_SHA256 = "fe9f4ddb5e198b4851499b91020c3a261507ecc19960a3a99979f55c5ed7396d"
INVENTORY_LIMIT = 100  # Original configuration2853 default, fxS.gsB counts all owned.


@lru_cache(maxsize=1)
def catalog():
    raw = Path(__file__).with_name("native_ranch_creatures.json").read_bytes()
    if sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("Conflicting original Ranch creature catalog")
    data = json.loads(raw)
    definitions = {row["reference"]: row for row in data["definitions"]}
    actions = {row["action_id"]: row for row in data["actions"]}
    if len(definitions) != 125 or len(actions) != 36:
        raise ValueError("Incomplete original Ranch creature catalog")
    for action in actions.values():
        if (
            not action["candidate_refs"]
            or action["suffix_bytes"] != 0
            or action["action_criterion"] != ""
            or any(value not in definitions for value in action["candidate_refs"])
        ):
            raise ValueError("Invalid original Ranch acquisition candidates")
    return actions, definitions


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        return None
    return "bHz" if struct.unpack_from(">i", body)[0] in catalog()[0] else None


def generate(action_id, uid, birth_ms, seed):
    """Explicit seeded slot sampling and the original fBQ constructor baseline."""
    action = catalog()[0].get(action_id)
    if (
        action is None
        or type(uid) is not int
        or uid <= 0
        or type(birth_ms) is not int
        or not 0 <= birth_ms < 2**63
        or not isinstance(seed, str)
        or len(seed) != 32
        or any(c not in "0123456789abcdef" for c in seed)
    ):
        raise ValueError("Invalid seeded Ranch acquisition identity")
    slot = random.Random(int(seed, 16)).randrange(len(action["candidate_refs"]))
    record = dict(
        definition=action["candidate_refs"][slot],
        uid=uid,
        birth_ms=birth_ms,
        attributes={},
        name="",
        scale=1.0,
        native_tJT=True,
        native_eqf=-1,
        native_tJU=-1,
        x=0,
        y=0,
        z=0,
        native_tJR=0,
        native_tJV=True,
    )
    from wakfu_server.haven_ranch_herd_wire import encode_creature

    encode_creature(record)
    return record, slot


def _record(row):
    return dict(
        definition=row["definition"],
        uid=row["uid"],
        birth_ms=row["birth_ms"],
        attributes={int(k): v for k, v in row["attributes"].items()},
        name=row["name"],
        scale=row["scale"],
        native_tJT=row["inventory"],
        native_eqf=row["biome_id"],
        native_tJU=row["paddock_uid"] if row["paddock_uid"] is not None else -1,
        x=row["x"],
        y=row["y"],
        z=row["z"],
        native_tJR=row["native_tjr"],
        native_tJV=row["native_tjv"],
    )


def records(db, account_id, *, biome_id=None, sector_id=None, deployed=None):
    """All owned instances for component18; optional exact scene filters."""
    where, args = ["account_id=%s", "released_at IS NULL"], [account_id]
    for key, value in (("biome_id", biome_id), ("sector_id", sector_id)):
        if value is not None:
            if type(value) is not int:
                raise ValueError("Invalid Ranch creature scene selector")
            where.append(key + "=%s")
            args.append(value)
    if deployed is not None:
        if type(deployed) is not bool:
            raise ValueError("Invalid Ranch deployment selector")
        where.append("inventory=%s")
        args.append(not deployed)
    return [
        _record(row)
        for row in db.execute(
            "SELECT * FROM account_ranch_creatures WHERE "
            + " AND ".join(where)
            + " ORDER BY uid",
            args,
        )
    ]


def _plain_source(db, item):
    """Consume the native source only when no physical extensions are lost."""
    from wakfu_server.item_custody_metadata import snapshot
    from wakfu_server.item_binding import hydrate, state

    metadata = snapshot(db, item["uid"])
    if any(table != "inventory_item_bindings" for table in metadata):
        raise ValueError("Ranch source has unsupported physical item extensions")
    binding = metadata.get("inventory_item_bindings")
    if binding is not None and (
        binding["template_reference"] != item["reference"]
        or type(binding["bound"]) is not bool
    ):
        raise ValueError("Ranch source binding differs from its owned template")
    if db.execute(
        "SELECT 1 FROM portable_item_custody WHERE uid=%s", (item["uid"],)
    ).fetchone():
        raise ValueError("Ranch source retains portable item custody")
    native = state(hydrate(db, [dict(item)])[0])
    # Binding restricts physical transfer. Native bHz consumes its actual owned
    # source into fxS account ownership; no new tradable item erases the flag.
    return None if native is None else dict(binding_type=native[0], bound=native[1])


def sector_records(db, account_id, biome_id):
    """Group deployed fBQ records by durable sector, never by its paddock UID."""
    result = {}
    for row in db.execute(
        "SELECT * FROM account_ranch_creatures WHERE account_id=%s "
        "AND biome_id=%s AND inventory=FALSE AND released_at IS NULL ORDER BY uid",
        (account_id, biome_id),
    ):
        result.setdefault(row["sector_id"], []).append(_record(row))
    return result


def use(store, account_id, generation, character_id, body, *, in_fight=False):
    """Actual13220 bHz request, not an ordinary item reward substitute."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Native Ranch acquisition requires12 bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    action = catalog()[0].get(action_id)
    if action is None or source_uid <= 0 or in_fight:
        raise ValueError("Unavailable native Ranch creature acquisition")
    from wakfu_server.inventory_owner import lock_item_owner
    from wakfu_server.inventory_uids import allocate
    from wakfu_server.simple_item_actions import _idle, _equipped
    from wakfu_server.profession_store import stored_level
    from wakfu_server.haven_ranch_herd_wire import creature_delta

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        _idle(db, owner, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner),
        ).fetchone()
        if (
            item is None
            or item["reference"] != action["item_ref"]
            or item["quantity"] < 1
        ):
            raise ValueError("Ranch source unavailable or foreign")
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        rule = _rules().get(item["reference"])
        if (
            rule is None
            or rule.get("use_action_class") != "bHz"
            or rule.get("use_action_id") != action_id
            or rule.get("use_has_criteria") is not False
        ):
            raise ValueError("Ranch source differs from original use contract")
        character = store.character(account_id, owner, db)
        if _equipped(character, source_uid):
            raise ValueError("Unequip the Ranch source before use")
        profession, minimum = map(int, action["parameters"][:2])
        if (stored_level(db, account_id, profession) or 0) < minimum:
            raise ValueError("Ranch source profession requirement is not met")
        count = db.execute(
            "SELECT count(*) AS count FROM account_ranch_creatures WHERE account_id=%s "
            "AND released_at IS NULL",
            (account_id,),
        ).fetchone()["count"]
        if count >= INVENTORY_LIMIT:
            raise ValueError("Native Ranch creature inventory is full")
        source_binding = _plain_source(db, item)
        seed = secrets.token_hex(16)
        uid = allocate(db)
        generated, slot = generate(
            action_id, uid, int(store.now().timestamp() * 1000), seed
        )
        row = db.execute(
            "INSERT INTO account_ranch_creatures(uid,account_id,definition,birth_ms,attributes,name,scale,inventory) "
            "VALUES(%s,%s,%s,%s,%s,'',1,TRUE) RETURNING *",
            (
                uid,
                account_id,
                generated["definition"],
                generated["birth_ms"],
                Jsonb(generated["attributes"]),
            ),
        ).fetchone()
        from wakfu_server.ranch_cycle_rewards import settle_creature

        settle_creature(db, store, row, now_ms=int(store.now().timestamp() * 1000))
        record = _record(row)
        if record != generated:
            raise ValueError(
                "Stored Ranch instance differs from its native generation contract"
            )
        packet = creature_delta([record], added=True)
        db.execute(
            "INSERT INTO ranch_creature_acquisitions(account_id,character_id,source_uid,source_reference,"
            "action_id,creature_uid,seed,candidate_slot,policy,source_binding) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                owner,
                source_uid,
                item["reference"],
                action_id,
                uid,
                seed,
                slot,
                POLICY,
                Jsonb(source_binding) if source_binding is not None else None,
            ),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        return dict(
            character=store.character(account_id, owner, db),
            creature=record,
            packets=[(12470, struct.pack(">qh", source_uid, -1)), packet],
            consumed=1,
            native_class="bHz",
            applied=True,
        )


def _owned(db, account_id, uid):
    row = db.execute(
        "SELECT * FROM account_ranch_creatures WHERE uid=%s AND account_id=%s "
        "AND released_at IS NULL FOR UPDATE",
        (uid, account_id),
    ).fetchone()
    if row is None:
        raise ValueError("Ranch creature unavailable or foreign")
    return row


def rename(store, account_id, generation, character_id, body):
    """Native csw13017; update the same owned instance, not a new grant."""
    if not isinstance(body, bytes) or len(body) < 9:
        raise ValueError("Invalid native creature rename")
    uid, size = struct.unpack_from(">qB", body)
    if uid <= 0 or size > 127 or len(body) != 9 + size:
        raise ValueError("Invalid native creature name length")
    try:
        name = body[9:].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("Invalid native creature UTF8 name") from error
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("Native creature name contains control characters")
    from wakfu_server.simple_item_actions import _idle

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id)
        _idle(db, character_id, store.now())
        _owned(db, account_id, uid)
        row = db.execute(
            "UPDATE account_ranch_creatures SET name=%s,revision=revision+1 "
            "WHERE uid=%s AND account_id=%s RETURNING *",
            (name, uid, account_id),
        ).fetchone()
        scene_scope = None
        if not row["inventory"]:
            owner = db.execute(
                "SELECT character_id FROM account_haven_bags WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            if owner is None:
                raise ValueError("Deployed creature lacks its canonical Ranch owner")
            scene_scope = (1440, owner["character_id"])
        return dict(
            creature=_record(row),
            scene_scope=scene_scope,
            applied=True,
            packets=[(12085, struct.pack(">qB", uid, size) + body[9:])],
        )


def _regions(biome_id, sector_id, building_rows):
    from wakfu_server.ranch_native_paddocks import enclosed_regions

    return enclosed_regions(
        biome_id,
        sector_id,
        [row for row in building_rows if row["sector_id"] == sector_id],
    )


def _region_contains(region, x, y):
    return (x, y) in {
        tuple(cell) for key in ("interior", "boundary") for cell in region[key]
    }


def validate_building_change(db, account_id, biome_id, building_rows):
    """Never leave a durable deployed animal outside a real enclosure."""
    grouped = sector_records(db, account_id, biome_id)
    for sector_id, animals in grouped.items():
        regions = _regions(biome_id, sector_id, building_rows)
        if any(
            not any(
                _region_contains(region, animal["x"], animal["y"]) for region in regions
            )
            for animal in animals
        ):
            raise ValueError(
                "Repack the animals before changing their enclosing fences"
            )


def synchronize_paddocks(db, account_id, biome_id, building_rows):
    """Stable real physical UIDs for unchanged original enclosed regions."""
    from wakfu_server.inventory_uids import allocate

    sectors = [
        row["sector_id"]
        for row in db.execute(
            "SELECT sector_id FROM account_ranch_sectors WHERE account_id=%s AND biome_id=%s ORDER BY sector_id",
            (account_id, biome_id),
        )
    ]
    regions = [
        (sector, region)
        for sector in sectors
        for region in _regions(biome_id, sector, building_rows)
    ]
    validate_building_change(db, account_id, biome_id, building_rows)
    db.execute(
        "UPDATE account_ranch_paddocks SET active=FALSE WHERE account_id=%s AND biome_id=%s",
        (account_id, biome_id),
    )
    for sector, region in regions:
        interior = sorted([list(cell) for cell in region["interior"]])
        boundary = sorted([list(cell) for cell in region["boundary"]])
        canonical = dict(group=region["group"], interior=interior, boundary=boundary)
        key = sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        prior = db.execute(
            "SELECT uid FROM account_ranch_paddocks WHERE account_id=%s "
            "AND biome_id=%s AND sector_id=%s AND region_key=%s FOR UPDATE",
            (account_id, biome_id, sector, key),
        ).fetchone()
        if prior is None:
            db.execute(
                "INSERT INTO account_ranch_paddocks(uid,account_id,biome_id,sector_id,native_group,"
                "region_key,interior,boundary) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    allocate(db),
                    account_id,
                    biome_id,
                    sector,
                    region["group"],
                    key,
                    Jsonb(interior),
                    Jsonb(boundary),
                ),
            )
        else:
            db.execute(
                "UPDATE account_ranch_paddocks SET active=TRUE WHERE uid=%s",
                (prior["uid"],),
            )
    active = paddocks(db, account_id, biome_id)
    for sector, animals in sector_records(db, account_id, biome_id).items():
        for animal in animals:
            matches = [
                region
                for region in active
                if region["sector_id"] == sector
                and _region_contains(region, animal["x"], animal["y"])
            ]
            if not matches:
                raise ValueError("Deployed creature lost its actual native paddock")
            current = next(
                (region for region in matches if region["uid"] == animal["native_tJU"]),
                matches[0],
            )
            if current["uid"] != animal["native_tJU"]:
                db.execute(
                    "UPDATE account_ranch_creatures SET paddock_uid=%s,revision=revision+1 WHERE uid=%s",
                    (current["uid"], animal["uid"]),
                )
    return active


def paddocks(db, account_id, biome_id):
    """Read-only published actual enclosed regions, retaining retired identities."""
    return [
        dict(
            uid=row["uid"],
            sector_id=row["sector_id"],
            group=row["native_group"],
            interior=row["interior"],
            boundary=row["boundary"],
        )
        for row in db.execute(
            "SELECT * FROM account_ranch_paddocks WHERE account_id=%s "
            "AND biome_id=%s AND active=TRUE ORDER BY uid",
            (account_id, biome_id),
        )
    ]


def _authorize_scene(store, db, account_id, generation, character, session):
    from wakfu_server.haven_ranch_furniture import _authorize

    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    if session is None or character.get("map_id") != 1440 or session.biome_id != 1:
        raise ValueError("Native creatures require the installed owned Ranch scene")
    _authorize(store, db, account_id, generation, character, session)


def deploy(store, account_id, generation, character, body, *, session, geometry):
    """Actual csy13541: owned UID and cell; derive all private scope server-side."""
    if not isinstance(body, bytes) or len(body) != 16:
        raise ValueError("Native creature deployment requires16 bytes")
    uid, x, y = struct.unpack(">qii", body)
    if uid <= 0:
        raise ValueError("Invalid creature deployment identity")
    from wakfu_server.haven_ranch_buildings import rows as building_rows
    from wakfu_server.ranch_native_geometry import building_footprint_cells
    from wakfu_server.haven_ranch_herd_wire import encode_creature

    with store.connection() as db:
        _authorize_scene(store, db, account_id, generation, character, session)
        row = _owned(db, account_id, uid)
        if not row["inventory"]:
            if (row["biome_id"], row["x"], row["y"]) != (session.biome_id, x, y):
                raise ValueError(
                    "Repack the already deployed creature before moving it"
                )
            # Native ceK.h appends to its sector list; replaying the add delta
            # would duplicate the same animal in that list. Reconcile a snapshot.
            return dict(
                creature=_record(row), packets=[], refresh_scene=True, applied=False
            )
        if geometry.get("map_id") != character["map_id"]:
            raise ValueError("Wrong native creature placement geometry")
        heights = {
            cell[2]
            for cell in geometry["cells"]
            if cell[:2] == [x, y] or tuple(cell[:2]) == (x, y)
        }
        if len(heights) != 1:
            raise ValueError("Creature target requires one native walkable height")
        z = next(iter(heights))
        buildings = building_rows(db, account_id, session.biome_id)
        regions = synchronize_paddocks(db, account_id, session.biome_id, buildings)
        containing = [region for region in regions if _region_contains(region, x, y)]
        if len({region["sector_id"] for region in containing}) != 1:
            raise ValueError("Creature target is outside an actual enclosed paddock")
        sector = containing[0]["sector_id"]
        if (
            len(
                records(
                    db,
                    account_id,
                    biome_id=session.biome_id,
                    sector_id=sector,
                    deployed=True,
                )
            )
            >= 5
        ):
            raise ValueError("Native Ranch sector creature limit reached")
        if (x, y) in building_footprint_cells(session.biome_id, buildings):
            raise ValueError("Creature target overlaps a native building")
        if db.execute(
            "SELECT 1 FROM account_ranch_creatures WHERE account_id=%s AND biome_id=%s "
            "AND inventory=FALSE AND released_at IS NULL AND x=%s AND y=%s",
            (account_id, session.biome_id, x, y),
        ).fetchone():
            raise ValueError("Creature target is occupied by another animal")
        if db.execute(
            "SELECT 1 FROM haven_ranch_furniture WHERE owner_character_id=%s AND map_id=1440 "
            "AND x=%s AND y=%s UNION ALL SELECT 1 FROM planted_resources WHERE map_id=1440 "
            "AND instance_id=%s AND x=%s AND y=%s",
            (character["instance_id"], x, y, character["instance_id"], x, y),
        ).fetchone():
            raise ValueError("Creature target is occupied by furniture or a plant")
        from wakfu_server.ranch_cycle_rewards import settle_creature

        settle_creature(db, store, row, now_ms=int(store.now().timestamp() * 1000))
        row = db.execute(
            "UPDATE account_ranch_creatures SET inventory=FALSE,biome_id=%s,sector_id=%s,paddock_uid=%s,"
            "x=%s,y=%s,z=%s,revision=revision+1 WHERE uid=%s RETURNING *",
            (session.biome_id, sector, containing[0]["uid"], x, y, z, uid),
        ).fetchone()
        record = _record(row)
        return dict(
            creature=record,
            applied=True,
            packets=[
                (
                    12391,
                    struct.pack(">qB", character["map_id"], 1)
                    + encode_creature(record),
                )
            ],
        )


def repack(store, account_id, generation, character, body, *, session):
    """Actual csx12617; preserve the same physical UID and all native attributes."""
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Native creature repack requires8 bytes")
    uid = struct.unpack(">q", body)[0]
    if uid <= 0:
        raise ValueError("Invalid creature repack identity")
    from wakfu_server.haven_ranch_herd_wire import creature_delta

    with store.connection() as db:
        _authorize_scene(store, db, account_id, generation, character, session)
        row = _owned(db, account_id, uid)
        if not row["inventory"] and row["biome_id"] != session.biome_id:
            raise ValueError("Creature is deployed in another Ranch biome")
        if row["inventory"]:
            return dict(
                creature=_record(row),
                packets=[creature_delta([_record(row)], added=True)],
                refresh_scene=True,
                applied=False,
            )
        from wakfu_server.ranch_cycle_rewards import settle_creature

        settle_creature(db, store, row, now_ms=int(store.now().timestamp() * 1000))
        row = db.execute(
            "UPDATE account_ranch_creatures SET inventory=TRUE,revision=revision+1 "
            "WHERE uid=%s RETURNING *",
            (uid,),
        ).fetchone()
        record = _record(row)
        return dict(
            creature=record,
            applied=True,
            packets=[
                (12657, struct.pack(">qhq", character["map_id"], 1, uid)),
                creature_delta([record], added=True),
            ],
        )


def release(store, account_id, generation, character, body, *, session):
    """Native csv13961: retire ownership while retaining the acquired instance.

    cFh13754 needs the full pre-release fBQ: for deployed animals its inventory
    flag and paddock UID remove the scene actor before removing account ownership.
    Repeated removal reconciles the same identity without another mutation.
    """
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Native creature release requires8 bytes")
    uid = struct.unpack(">q", body)[0]
    if uid <= 0:
        raise ValueError("Invalid creature release identity")
    from wakfu_server.haven_ranch_herd_wire import creature_delta
    from wakfu_server.simple_item_actions import _idle

    with store.connection() as db:
        _authorize_scene(store, db, account_id, generation, character, session)
        _idle(db, character["id"], store.now())
        # Include this account's tombstone only for replay; ordinary mutations
        # use _owned and can never rename, repack or deploy a released instance.
        row = db.execute(
            "SELECT * FROM account_ranch_creatures WHERE uid=%s "
            "AND account_id=%s FOR UPDATE",
            (uid, account_id),
        ).fetchone()
        if row is None:
            raise ValueError("Ranch creature unavailable or foreign")
        if not row["inventory"] and row["biome_id"] != session.biome_id:
            raise ValueError("Creature is deployed in another Ranch biome")
        if row["released_at"] is None:
            from wakfu_server.ranch_cycle_rewards import settle_creature

            settle_creature(db, store, row, now_ms=int(store.now().timestamp() * 1000))
            row = db.execute(
                "SELECT * FROM account_ranch_creatures WHERE uid=%s FOR UPDATE", (uid,)
            ).fetchone()
        record = _record(row)
        scene_scope = None
        if not row["inventory"]:
            owner = db.execute(
                "SELECT character_id FROM account_haven_bags WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            if owner is None or owner["character_id"] != character["instance_id"]:
                raise ValueError("Deployed creature lacks its canonical Ranch owner")
            scene_scope = (1440, owner["character_id"])
        applied = row["released_at"] is None
        if applied:
            db.execute(
                "UPDATE account_ranch_creatures SET released_at=%s,"
                "released_by_character_id=%s,revision=revision+1 WHERE uid=%s",
                (store.now(), character["id"], uid),
            )
        return dict(
            creature=record,
            applied=applied,
            scene_scope=scene_scope,
            refresh_scene=scene_scope is not None,
            packets=[creature_delta([record], added=False)],
        )
