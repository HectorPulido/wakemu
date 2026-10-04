"""Owned native seed actions and SQL planting receipts/outbox.

Territorial authorization and outcome/growth are caller policies; unknown
conditions are not fabricated. Resource and seed commit together in SQLite.
Publishing a prepared monster group to Redis is retried from the durable outbox.
"""
import json
import secrets
import struct
from .paths import DATA_ROOT
from .inventory_items import _lease
from .monsters import reference, owned_instance
from .combat_groups import Groups
from .combat_monster_world import spawn_group
from .wire import proto_field

SEEDS = {
    r["item_reference"]: r
    for r in json.loads((DATA_ROOT / "seed-actions.json").read_text())
}
RESOURCES = {
    r["resource_reference"]: r
    for r in json.loads((DATA_ROOT / "plant-resources.json").read_text())
}


def decode(body):
    if len(body) != 20:
        raise ValueError("Invalid native seed request size")
    action, uid, x, y = struct.unpack(">iqii", body)
    if uid <= 0 or action <= 0:
        raise ValueError("Invalid seed action identity")
    return dict(action_id=action, item_uid=uid, x=x, y=y)


def resource_packet(resource):
    # cAz13135 → zk ProtoResourcePartition → cFL/bOm or bOi.
    fields = (
        (8, resource["resource_reference"]),
        (16, resource["x"]),
        (24, resource["y"]),
        (32, resource["z"]),
        (40, resource["stage"]),
        (48, 0),
        (56, resource["creation_time"]),
        (64, 0),
    )
    return (
        13135,
        b"".join(
            proto_field(tag, value if value >= 0 else (1 << 64) + value)
            for tag, value in fields
        ),
    )


def result_packet(prefix_long, prefix_int, success):
    # cAZ's cgN handler reads only success; both prefix fields are preserved
    # explicitly until their server-side identities are fully interpreted.
    return (12954, struct.pack(">qiB", prefix_long, prefix_int, int(success)))


def start_packet(*, mun, hvY, actor_id, profession_id, duration, egY, x, y):
    # cyK.dp: byte,short,long,int,int,int,int,int. ctQ is widened i32.
    return (
        12815,
        struct.pack(
            ">Bhqiiiii", mun, hvY, actor_id, profession_id, duration, egY, x, y
        ),
    )


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS planted_resources(
        resource_uid INTEGER PRIMARY KEY, map_id INTEGER NOT NULL, instance_id INTEGER NOT NULL,
        x INTEGER NOT NULL,y INTEGER NOT NULL,z INTEGER NOT NULL,resource_reference INTEGER NOT NULL,
        stage INTEGER NOT NULL,creation_time INTEGER NOT NULL,
        UNIQUE(map_id,instance_id,x,y))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS planting_receipts(
        operation_id TEXT PRIMARY KEY,character_id INTEGER NOT NULL,item_uid INTEGER NOT NULL,
        request TEXT NOT NULL,resource TEXT NOT NULL,group_payload TEXT,
        published INTEGER NOT NULL DEFAULT 0)"""
    )


def prepare(
    store,
    account,
    generation,
    character,
    body,
    *,
    authorize_cell,
    open_test_policy=False
):
    request = decode(body)
    with store.connection() as db:
        _lease(store, db, account, generation, character["id"])
        current = store.character(account, character["id"], db)
        item = next(
            (
                item
                for item in current["inventory_items"]
                if item["uid"] == request["item_uid"]
            ),
            None,
        )
        if item is None:
            raise ValueError("Seed unavailable or foreign")
        seed = SEEDS.get(item["reference"])
        if (
            seed is None
            or seed["action_id"] != request["action_id"]
            or (seed["has_item_criteria"] and not open_test_policy)
        ):
            raise ValueError("Unknown, mismatched or conditional seed action")
        resource = RESOURCES.get(seed["resource_reference"])
        if resource is None:
            raise ValueError("Unknown native resource reference")
        from .profession_store import schema as profession_schema

        profession_schema(db)
        learned = db.execute(
            "SELECT level FROM character_professions WHERE character_id=? AND profession_id=?",
            (current["id"], seed["profession_id"]),
        ).fetchone()
        if not open_test_policy and (
            learned is None or learned["level"] < seed["minimum_level"]
        ):
            raise ValueError("Profession unlearned or below seed requirement")
    # Caller verifies authoritative territory permissions, exact native
    # ground/height and ecosystem rules, rather than a made-up radius/chance.
    z = authorize_cell(current, request, seed, resource)
    if type(z) is not int or not -(1 << 15) <= z < (1 << 15):
        raise ValueError("Planting cell is not authorized")
    return dict(character=current, request=request, seed=seed, definition=resource, z=z)


def complete(
    store,
    account,
    generation,
    prepared,
    *,
    operation_id,
    stage,
    creation_time,
    result_prefix,
    monster_members=None,
    group_id=None
):
    if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 128:
        raise ValueError("Invalid planting receipt ID")
    if (
        type(stage) is not int
        or not 0 <= stage <= 127
        or type(creation_time) is not int
        or creation_time < 0
    ):
        raise ValueError("Invalid native resource state")
    character = prepared["character"]
    request = prepared["request"]
    definition = prepared["definition"]
    resource = dict(
        resource_uid=secrets.randbits(62) + 1,
        map_id=character["map_id"],
        instance_id=character["instance_id"],
        x=request["x"],
        y=request["y"],
        z=prepared["z"],
        resource_reference=definition["resource_reference"],
        stage=stage,
        creation_time=creation_time,
    )
    if stage not in definition["stages"]:
        raise ValueError("Resource stage is absent from native definition")
    group = None
    if monster_members is not None:
        if not definition["monster_resource"]:
            raise ValueError("A plant cannot produce a monster group")
        for member in monster_members:
            if (
                reference(member["ref"])["family_id"]
                not in definition["monster_family_ids"]
            ):
                raise ValueError("Monster is not in the seed native family")
        key = Groups().register(
            character["map_id"], character["instance_id"], group_id, monster_members
        )
        group = dict(key=key, members=monster_members)
    encoded_request = json.dumps(request, sort_keys=True)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account, generation, character["id"])
        schema(db)
        old = db.execute(
            "SELECT * FROM planting_receipts WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if old:
            if (
                old["character_id"] != character["id"]
                or old["request"] != encoded_request
            ):
                raise ValueError("Planting operation ID was reused")
            return dict(
                resource=json.loads(old["resource"]),
                duplicate=True,
                packets=[],
                group=None,
            )
        current = store.character(account, character["id"], db)
        if any(
            current[k] != character[k] for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Planting origin changed")
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=? AND character_id=?",
            (request["item_uid"], character["id"]),
        ).fetchone()
        if item is None or item["reference"] != prepared["seed"]["item_reference"]:
            raise ValueError("Seed no longer owned")
        db.execute(
            "INSERT INTO planted_resources VALUES(?,?,?,?,?,?,?,?,?)",
            tuple(resource.values()),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=?", (item["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=?",
                (item["uid"],),
            )
        db.execute(
            "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,group_payload) VALUES(?,?,?,?,?,?)",
            (
                operation_id,
                character["id"],
                item["uid"],
                encoded_request,
                json.dumps(resource),
                json.dumps(group) if group else None,
            ),
        )
    # cgN consumes one client seed on BOTH success and failure12954. Never
    # also emit12470 for this successful consumption, which would double it.
    return dict(
        resource=resource,
        duplicate=False,
        group=group,
        packets=[resource_packet(resource), result_packet(*result_prefix, True)],
        character=store.character(account, character["id"]),
    )


def publish_groups(store, groups):
    """Idempotent SQL outbox → Redis/group registry; retain failures for retry."""
    with store.connection() as db:
        schema(db)
        pending = list(
            db.execute(
                "SELECT operation_id,group_payload FROM planting_receipts WHERE published=0 AND group_payload IS NOT NULL"
            )
        )
    published = []
    for row in pending:
        group = json.loads(row["group_payload"])
        key = tuple(group["key"])
        groups.register(*key, group["members"])
        with store.connection() as db:
            db.execute(
                "UPDATE planting_receipts SET published=1 WHERE operation_id=?",
                (row["operation_id"],),
            )
        published.append((12608, spawn_group(group["members"], group_id=key[2])))
    return published
