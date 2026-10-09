"""Owned native seed actions and SQL planting receipts/outbox.

Territorial authorization and outcome/growth are caller policies; unknown
conditions are not fabricated. Resource and seed commit together in PostgreSQL.
Publishing a prepared monster group to Redis is retried from the durable outbox.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import secrets
import struct
import math
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from .paths import DATA_ROOT
from .inventory_items import _lease
from .monsters import reference, owned_instance
from .combat_groups import Groups
from .combat_monster_world import spawn_group
from .wire import proto_field

SEEDS = {
    r["item_reference"]: r
    for r in protocol_catalog.load(DATA_ROOT / "seed-actions.json")
}
RESOURCES = {
    r["resource_reference"]: r
    for r in protocol_catalog.load(DATA_ROOT / "plant-resources.json")
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
        # zk field 7 is ownerAccount, not the planting timestamp. World
        # flora is public; creation_time remains in PostgreSQL for growth.
        (56, 0),
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
        from .profession_store import stored_level

        learned = stored_level(db, account, seed["profession_id"])
        # The test override relaxes requirements, never account ownership of
        # profession progress. Reject before starting an uncreditable action.
        if learned is None or (
            not open_test_policy and learned < seed["minimum_level"]
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
    success=True,
    probability=None,
    monster_members=None,
    group_id=None
):
    if type(success) is not bool:
        raise ValueError("Invalid authoritative planting outcome")
    if probability is not None and (
        type(probability) not in (int, float)
        or not 0 <= probability <= 1
        or not math.isfinite(probability)
    ):
        raise ValueError("Invalid authoritative planting probability")
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
    with store.connection() as db:
        _lease(store, db, account, generation, character["id"])
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("planting:" + operation_id,),
        )
        old = db.execute(
            "SELECT * FROM planting_receipts WHERE operation_id=%s", (operation_id,)
        ).fetchone()
        if old:
            if old["character_id"] != character["id"] or old["request"] != request:
                raise ValueError("Planting operation ID was reused")
            return dict(
                resource=old["resource"],
                duplicate=True,
                packets=[],
                group=None,
                success=old["success"],
                probability=old["probability"],
            )
        current = store.character(account, character["id"], db)
        if any(
            current[k] != character[k] for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Planting origin changed")
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (request["item_uid"], character["id"]),
        ).fetchone()
        if item is None or item["reference"] != prepared["seed"]["item_reference"]:
            raise ValueError("Seed no longer owned")
        cell = tuple(resource[key] for key in ("map_id", "instance_id", "x", "y"))
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("planting-cell:" + ":".join(map(str, cell)),),
        )
        if db.execute(
            "SELECT 1 FROM planted_resources "
            "WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
            cell,
        ).fetchone():
            raise ValueError("Planting resource identity or cell already occupied")
        if probability is not None:
            from .planting_probability import succeeds

            success = succeeds(probability, secrets.randbelow(1 << 53) / (1 << 53))
        from .flora_ecology import change as ecological_change
        from hashlib import sha256

        from .ecology_feedback import information

        ecology = (
            ecological_change(
                db,
                character["id"],
                resource,
                operation="planting:" + sha256(operation_id.encode()).hexdigest(),
                action="plant",
            )
            if success
            else dict(
                packets=[
                    information(
                        "Ecosistema: la plantación no arraigó. "
                        "La población y tu afinidad Wakfu/Stasis no cambian."
                    )
                ],
                reason="planting_failed",
            )
        )
        try:
            with db.transaction():
                if success:
                    db.execute(
                        "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        tuple(resource.values()),
                    )
        except UniqueViolation as exc:
            raise ValueError(
                "Planting resource identity or cell already occupied"
            ) from exc
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (item["uid"],),
            )
        db.execute(
            "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,group_payload,success,probability) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                operation_id,
                character["id"],
                item["uid"],
                Jsonb(request),
                Jsonb(resource) if success else None,
                Jsonb(group) if success and group else None,
                success,
                probability,
            ),
        )
        from .profession_rewards import base_xp
        from .profession_store import award
        from hashlib import sha256

        if success:
            from wakfu_server.territory_bonuses import (
                current_region,
                profession_xp_percent,
            )

            territory = current_region(db, current)
            territory_percent = profession_xp_percent(territory, "planting")
            progress = award(
                store,
                db,
                account,
                generation,
                character["id"],
                prepared["seed"]["profession_id"],
                base_xp=base_xp(db, "planting"),
                operation="planting:" + sha256(operation_id.encode()).hexdigest(),
                territory_percent=territory_percent,
            )
        else:
            progress = dict(packets=[])
    # cgN12954 calls bJt.d/e, which only displays item.selfDrop; it does not
    # mutate the inventory. Publish the committed quantity delta exactly once.
    return dict(
        resource=resource if success else None,
        success=success,
        probability=probability,
        duplicate=False,
        group=group if success else None,
        packets=([resource_packet(resource)] if success else [])
        + [
            result_packet(*result_prefix, success),
            (12470, struct.pack(">qh", item["uid"], -1)),
        ]
        + progress["packets"]
        + ecology["packets"],
        ecology=ecology,
        character=store.character(account, character["id"]),
    )


def publish_groups(store, groups):
    """Idempotent SQL outbox → Redis/group registry; retain failures for retry."""
    with store.connection() as db:
        pending = list(
            db.execute(
                "SELECT operation_id,group_payload FROM planting_receipts WHERE published=FALSE AND group_payload IS NOT NULL"
            )
        )
    published = []
    for row in pending:
        group = row["group_payload"]
        key = tuple(group["key"])
        from .npc_actor_identity_repair import actor_aliases, aliased_members

        with store.connection() as db:
            group = dict(
                group, members=aliased_members(group["members"], actor_aliases(db, key))
            )
        groups.register(*key, group["members"])
        with store.connection() as db:
            db.execute(
                "UPDATE planting_receipts SET published=TRUE WHERE operation_id=%s",
                (row["operation_id"],),
            )
        published.append((12608, spawn_group(group["members"], group_id=key[2])))
    return published
