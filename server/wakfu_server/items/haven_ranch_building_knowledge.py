"""Native bIA Ranch building learning, separate from bIx decoration ownership."""
import struct

from .inventory_owner import lock_inventory_character, lock_item_owner


def library_payload(references, *, biomes=None, animals=None):
    """Original fxS account sections and fBX known/new building references.

    The default empty collections also serve standalone target validation.
    Owned biome snapshots use the same fBE serializer as scene bootstrap.
    """
    refs = sorted(references)
    if len(refs) != len(set(refs)) or any(
        type(ref) is not int or not 0 < ref < 2**31 for ref in refs
    ):
        raise ValueError("Invalid native Ranch building references")
    values = struct.pack(">I", len(refs)) + b"".join(
        struct.pack(">i", ref) for ref in refs
    )
    library = values + values  # fBX.abO adds newly learned entries to both sets.
    animals = struct.pack(">II", 0, 0) if animals is None else animals
    if not isinstance(animals, bytes):
        raise ValueError("Invalid native Ranch animal section")
    biomes = {} if biomes is None else biomes
    if not isinstance(biomes, dict) or len(biomes) > 32767:
        raise ValueError("Invalid native Ranch biome collection")
    for identity, record in biomes.items():
        if (
            type(identity) is not int
            or not 0 < identity < 2**31
            or not isinstance(record, bytes)
        ):
            raise ValueError("Invalid native Ranch biome record")
    biomes = struct.pack(">h", len(biomes)) + b"".join(
        struct.pack(">i", identity) + biomes[identity] for identity in sorted(biomes)
    )
    return b"".join(
        struct.pack(">I", len(part)) + part for part in (animals, biomes, library)
    )


def herd_sectors(db, account_id, biome_id, sectors):
    """Read the same durable herd collections for account and scene snapshots."""
    from .haven_ranch_herd import sector_records, paddocks

    creatures_by_sector = {sector: [] for sector in sectors}
    paddocks_by_sector = {sector: [] for sector in sectors}
    for sector_id, creatures in sector_records(db, account_id, biome_id).items():
        if sector_id not in creatures_by_sector:
            raise ValueError("Owned creature references an unknown Ranch sector")
        creatures_by_sector[sector_id] = creatures
    for paddock in paddocks(db, account_id, biome_id):
        if paddock["sector_id"] not in paddocks_by_sector:
            raise ValueError("Owned paddock references an unknown Ranch sector")
        paddocks_by_sector[paddock["sector_id"]].append(paddock)
    return creatures_by_sector, paddocks_by_sector


def _owned_biomes(db, account_id, now_ms):
    """Read persisted ownership without creating sectors in a read-only snapshot."""
    owned = {}
    for row in db.execute(
        "SELECT biome_id,sector_id FROM account_ranch_sectors "
        "WHERE account_id=%s ORDER BY biome_id,sector_id",
        (account_id,),
    ):
        owned.setdefault(row["biome_id"], []).append(row["sector_id"])
    if not owned:
        return {}
    from .ranch_native_geometry import initial_sectors, account_buildings_by_sector
    from .haven_ranch_furniture import _rows, _policy
    from .haven_ranch_furniture_wire import biome_record
    from .haven_ranch_bridges import snapshot as bridge_snapshot
    from .ranch_reward_retrieval import records as reward_records

    bag = db.execute(
        "SELECT character_id FROM account_haven_bags WHERE account_id=%s",
        (account_id,),
    ).fetchone()
    if bag is None:
        raise ValueError("Owned Ranch sectors have no account Haven Bag")
    policy, _, _ = _policy(db)
    result = {}
    for biome_id, sectors in owned.items():
        if biome_id != policy["biome_id"] or tuple(sectors) != initial_sectors(
            biome_id
        ):
            raise ValueError("Owned Ranch biome sectors differ from native topology")
        creatures_by_sector, paddocks_by_sector = herd_sectors(
            db,
            account_id,
            biome_id,
            sectors,
        )
        result[biome_id] = biome_record(
            sectors,
            _rows(db, bag["character_id"]),
            now_ms,
            building_states=bridge_snapshot(db, bag["character_id"]),
            buildings_by_sector=account_buildings_by_sector(db, account_id, biome_id),
            creatures_by_sector=creatures_by_sector,
            paddocks_by_sector=paddocks_by_sector,
            rewards=reward_records(db, account_id),
        )
    return result


def _snapshot(db, account_id, *, now_ms):
    refs = [
        row["building_ref"]
        for row in db.execute(
            "SELECT building_ref FROM account_ranch_building_knowledge "
            "WHERE account_id=%s ORDER BY building_ref",
            (account_id,),
        )
    ]
    from .haven_ranch_herd import records
    from .haven_ranch_herd_wire import account_animals

    return 13873, struct.pack(">II", 1, 18) + library_payload(
        refs,
        biomes=_owned_biomes(db, account_id, now_ms),
        animals=account_animals(records(db, account_id)),
    )


def packet(store, account_id):
    with store.connection() as db:
        return _snapshot(db, account_id, now_ms=int(store.now().timestamp() * 1000))


def scene_packet(store, account_id, *, biome_id):
    """Publish host-tagged scene state after a separately authorized mutation.

    Owner-only creature deltas must never populate a visitor's fxS library.
    This fBE context identifies its actual host account instead.
    """
    from .ranch_native_geometry import native_biome

    world = native_biome(biome_id)["native_world_map_id"]
    with store.connection() as db:
        biomes = _owned_biomes(db, account_id, int(store.now().timestamp() * 1000))
    if biome_id not in biomes:
        raise ValueError("Ranch scene publication requires an owned biome")
    return 13864, struct.pack(">qqB", account_id, world, 1) + biomes[biome_id]


def learn(store, account_id, generation, character_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Ranch building learning requires exactly 12 request bytes")
    action_id, source_uid = struct.unpack(">iq", body)
    if action_id <= 0 or source_uid <= 0:
        raise ValueError("Invalid Ranch building learning action or item UID")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM ranch_building_learning_receipts "
            "WHERE account_id=%s AND source_uid=%s",
            (account_id, source_uid),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["action_id"] != action_id:
                raise ValueError(
                    "Ranch building learning receipt does not match request"
                )
            return {
                "character": store.character(account_id, character_id, db),
                "packets": [
                    _snapshot(
                        db, account_id, now_ms=int(store.now().timestamp() * 1000)
                    )
                ],
                "applied": False,
            }
        character_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, character_id),
        ).fetchone()
        if item is None or item["quantity"] < 1:
            raise ValueError("Ranch building learning item unavailable or foreign")
        native = db.execute(
            "SELECT * FROM native_ranch_building_learning_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        from .haven_bag_furniture_knowledge import _rules

        rule = _rules().get(item["reference"])
        if (
            native is None
            or native["native_class"] != "bIA"
            or native["action_id"] != action_id
            or rule is None
            or rule.get("use_action_class") != "bIA"
            or rule.get("use_action_id") != action_id
            or rule.get("use_has_criteria") is not False
        ):
            raise ValueError(
                "Unsupported native Ranch building learning action or criteria"
            )
        from .profession_store import stored_level

        profession_level = stored_level(db, account_id, native["profession_id"])
        if (0 if profession_level is None else profession_level) < native[
            "minimum_level"
        ]:
            raise ValueError(
                "Profession level does not meet native Ranch building requirement"
            )
        from .wire import proto_fields

        character = store.character(account_id, character_id, db)
        for build in character.get("builds", {}).values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == source_uid:
                    raise ValueError(
                        "Unequip the Ranch building learning item before use"
                    )
        for table in (
            "inventory_item_elements",
            "inventory_item_shards",
            "inventory_mounts",
            "inventory_pets",
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE uid=%s", (source_uid,)
            ).fetchone():
                raise ValueError(
                    "Ranch building learning item has unsupported specific data"
                )
        refs = native["building_refs"]
        library_payload(refs)  # Validate the exact immutable native target domain.
        from .haven_ranch_building_catalog import validate_published

        for ref in refs:
            validate_published(db, ref)
        known = {
            row["building_ref"]
            for row in db.execute(
                "SELECT building_ref FROM account_ranch_building_knowledge "
                "WHERE account_id=%s ORDER BY building_ref",
                (account_id,),
            )
        }
        added = sorted(set(refs) - known)
        if not added:
            raise ValueError("Ranch building is already learned")
        for ref in added:
            db.execute(
                "INSERT INTO account_ranch_building_knowledge(account_id,building_ref) "
                "VALUES(%s,%s)",
                (account_id, ref),
            )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
        db.execute(
            "INSERT INTO ranch_building_learning_receipts"
            "(account_id,source_uid,character_id,source_ref,action_id,learned_refs) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (account_id, source_uid, character_id, item["reference"], action_id, added),
        )
        return {
            "character": store.character(account_id, character_id, db),
            "packets": [
                (12470, struct.pack(">qh", source_uid, -1)),
                _snapshot(db, account_id, now_ms=int(store.now().timestamp() * 1000)),
            ],
            "applied": True,
        }
