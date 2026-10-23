"""Complete durable per-UID state for ownership and storage transfers.

Only mutable item state is copied. Operation receipts stay with their original
owner. The native binding/admission policies remain the caller's responsibility.
"""
from copy import deepcopy
from psycopg import sql

TABLE_KEYS = {
    "inventory_item_elements": "uid",
    "inventory_item_shards": "uid",
    "inventory_mounts": "uid",
    "inventory_pets": "uid",
    "inventory_item_bindings": "uid",
    "inventory_item_recycling_state": "uid",
    "inventory_item_appearances": "uid",
    "inventory_item_companions": "uid",
    "random_item_use_counters": "source_uid",
}
_ANIMAL_COLUMNS = (
    "uid",
    "model_id",
    "name",
    "xp",
    "health",
    "color_item_ref",
    "equipped_item_ref",
    "sleep_item_ref",
    "reskin_item_ref",
    "last_meal_date",
    "last_hungry_date",
    "sleep_date",
    "revision",
)
_COLUMNS = {
    "inventory_item_elements": ("uid", "damage_elements", "resistance_elements"),
    "inventory_item_shards": ("uid", "shard_state"),
    "inventory_mounts": _ANIMAL_COLUMNS,
    "inventory_pets": _ANIMAL_COLUMNS,
    "inventory_item_bindings": ("uid", "bound", "template_reference"),
    "inventory_item_recycling_state": ("uid", "unidentified", "socketed"),
    "inventory_item_appearances": ("uid", "appearance_ref"),
    "inventory_item_companions": ("uid", "xp"),
    "random_item_use_counters": ("source_uid", "next_use"),
}


def _validate(table, row):
    if (
        table not in TABLE_KEYS
        or not isinstance(row, dict)
        or set(row) != set(_COLUMNS[table])
    ):
        raise ValueError("Unsupported durable item custody metadata")
    uid = row[TABLE_KEYS[table]]
    if type(uid) is not int or not 0 < uid < 2**63:
        raise ValueError("Invalid item custody metadata identity")


def snapshot_many(db, uids):
    identities = sorted(set(uids))
    if any(type(uid) is not int or not 0 < uid < 2**63 for uid in identities):
        raise ValueError("Invalid item custody snapshot identities")
    result = {uid: {} for uid in identities}
    if not identities:
        return result
    for table, key in TABLE_KEYS.items():
        query = sql.SQL(
            "SELECT * FROM {} WHERE {}=ANY(%s) ORDER BY {} FOR UPDATE"
        ).format(sql.Identifier(table), sql.Identifier(key), sql.Identifier(key))
        for row in db.execute(query, (identities,)):
            row = {
                name: bytes(value) if isinstance(value, memoryview) else value
                for name, value in row.items()
            }
            _validate(table, row)
            result[row[key]][table] = row
    return result


def snapshot(db, uid):
    return snapshot_many(db, [uid])[uid]


def clone(metadata, uid):
    result = deepcopy(metadata)
    for table, row in result.items():
        _validate(table, row)
        row[TABLE_KEYS[table]] = uid
        _validate(table, row)
    return result


def identity(metadata):
    result = {}
    for table, row in metadata.items():
        _validate(table, row)
        result[table] = {
            key: value for key, value in row.items() if key != TABLE_KEYS[table]
        }
    return result


def restore(db, metadata):
    for table, row in metadata.items():
        _validate(table, row)
        columns = _COLUMNS[table]
        db.execute(
            sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table),
                sql.SQL(",").join(map(sql.Identifier, columns)),
                sql.SQL(",").join(sql.Placeholder() for _ in columns),
            ),
            tuple(row[column] for column in columns),
        )
