"""Native inventory teleports with atomic consumption and complete relocation.

The World adapter owns private-scene capabilities and native map publication.
This service accepts only the durable source, fences buffered positions, and
returns a pending delivery receipt after the SQL operation has committed.
"""
from functools import lru_cache
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
import uuid

from psycopg.types.json import Jsonb

SOURCE_SHA256 = "6019d4be49d73238a6331128d9baeeea5811efc35efd17a7d40a08f8bf5e3210"
LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")


@lru_cache(maxsize=1)
def descriptors():
    payload = Path(__file__).with_name("native_item_teleports.json").read_bytes()
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native item teleport descriptors")
    return json.loads(payload)


def _request(body):
    if not isinstance(body, (bytes, bytearray, memoryview)) or len(body) != 12:
        raise ValueError("Invalid native item teleport action")
    action_id, uid = struct.unpack(">iq", body)
    if action_id <= 0 or uid <= 0:
        raise ValueError("Invalid native item teleport identity")
    return action_id, uid


def action_class(body):
    if not isinstance(body, (bytes, bytearray, memoryview)) or len(body) < 12:
        raise ValueError("Invalid native item action header")
    action_id = struct.unpack_from(">i", body)[0]
    native_class = next(
        (
            row["native_class"]
            for row in descriptors()["items"]
            if row["action_id"] == action_id
        ),
        None,
    )
    if native_class is None:
        from wakfu_server.item_scenario_teleports import (
            action_class as scenario_action_class,
        )

        native_class = scenario_action_class(body)
    if native_class is not None:
        _request(body)
    return native_class


def plan(action_id, *, geometry=None):
    """Resolve original coordinates, applying the authorized arrival policy."""
    from wakfu_server.combat_terrain import map_geometry

    if geometry is None:
        return deepcopy(_native_plan(action_id))
    rows = [row for row in descriptors()["items"] if row["action_id"] == action_id]
    if len(rows) != 1:
        raise ValueError("Unknown native item teleport action")
    row = dict(rows[0])
    requested = dict(
        row["native_destination"] or descriptors()["recall_policy"]["destination"]
    )
    native = (geometry or map_geometry)(requested["map_id"])
    if native.get("map_id") != requested["map_id"]:
        raise ValueError("Item teleport geometry belongs to another map")
    cells = {tuple(cell) for cell in native.get("cells", ())}
    target = tuple(requested[key] for key in ("x", "y", "z"))
    if not cells or any(
        len(cell) != 3 or any(type(value) is not int for value in cell)
        for cell in cells
    ):
        raise ValueError("Missing native item teleport walkable cells")
    exact = target in cells
    if not exact:
        target = min(
            cells,
            key=lambda cell: (
                abs(cell[0] - requested["x"]) + abs(cell[1] - requested["y"]),
                abs(cell[2] - requested["z"]),
                *cell,
            ),
        )
    row.update(
        requested_destination=requested,
        destination=dict(
            map_id=requested["map_id"],
            instance_id=0,
            **dict(zip(("x", "y", "z"), target))
        ),
        arrival_policy="exact_native_cell"
        if exact
        else descriptors()["arrival_policy"],
        recall_policy=descriptors()["recall_policy"]["kind"]
        if row["native_class"] == "bIr"
        else None,
    )
    return row


@lru_cache(maxsize=11)
def _native_plan(action_id):
    from wakfu_server.combat_terrain import map_geometry

    return plan(action_id, geometry=map_geometry)


def _result(store, db, account_id, character_id, receipt, *, packets=(), applied=False):
    metadata = dict(receipt["metadata"])
    return dict(
        character=store.character(account_id, character_id, db),
        packets=list(packets),
        applied=applied,
        pending_delivery=receipt["delivered_at"] is None,
        native_class=metadata["native_class"],
        consumed=1 if applied else 0,
        transition=dict(
            token=receipt["token"],
            source=dict(receipt["source"]),
            destination=dict(receipt["destination"]),
            **metadata
        ),
    )


def use(
    store,
    positions,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    physical_source=None,
    native_map_id=None
):
    """Consume one selected actor's item and move its company in one transaction.

    For bag/ranch projections, World validates the live private capability and
    supplies the durable exterior as physical_source plus the visible map ID.
    Unknown private runs reject before commit and consume nothing.
    """
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Sal del combate antes de teletransportarte")
    action_id, uid = _request(body)
    from wakfu_server.item_scenario_teleports import ACTIONS as SCENARIO_ACTIONS

    # Fixed routes preflight geometry before locks. Saved/national routes must
    # resolve against the selected main's locked current destination authority.
    route = None if action_id in SCENARIO_ACTIONS else plan(action_id)
    if positions is not None:
        from wakfu_server.dungeon_position_barrier import run_account_exit

        return run_account_exit(
            store,
            positions,
            account_id,
            transition=lambda: use(
                store,
                None,
                account_id,
                generation,
                character_id,
                body,
                in_fight=in_fight,
                physical_source=physical_source,
                native_map_id=native_map_id,
            ),
        )
    from wakfu_server.console_relocation import (
        lock_relocation_company,
        relocate_in_transaction,
    )
    from wakfu_server.simple_item_actions import _idle, _equipped
    from wakfu_server.native_world_context import is_battleground
    from wakfu_server.haven_bag_furniture_knowledge import _rules

    with store.connection() as db:
        cohort = lock_relocation_company(store, db, account_id, character_id)
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id, selected=True)
        current = store.character(account_id, character_id, db)
        if route is None:
            from wakfu_server.item_scenario_teleports import plan as scenario_plan

            route = scenario_plan(action_id, current)
        source = {key: current[key] for key in LOCATION_KEYS}
        if physical_source is not None and any(
            physical_source.get(key) != source[key] for key in LOCATION_KEYS
        ):
            raise ValueError("El origen del teletransporte ha cambiado")
        if is_battleground(
            current["map_id"] if native_map_id is None else native_map_id
        ):
            raise ValueError("No puedes teletransportarte desde un campo de batalla")
        for member_id in cohort:
            _idle(db, member_id, store.now())
        pending = db.execute(
            "SELECT * FROM item_teleport_receipts WHERE account_id=%s AND generation=%s "
            "AND character_id=%s AND delivered_at IS NULL FOR UPDATE",
            (account_id, generation, character_id),
        ).fetchone()
        if pending is not None:
            if (
                pending["source_item_uid"] != uid
                or pending["action_id"] != action_id
                or any(
                    current[key] != pending["destination"][key] for key in LOCATION_KEYS
                )
            ):
                raise ValueError("Espera a que termine el traslado anterior")
            return _result(store, db, account_id, character_id, pending)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        if (
            item is None
            or item["reference"] != route["item_ref"]
            or item["quantity"] < 1
        ):
            raise ValueError("Selecciona al personaje que posee este objeto")
        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_id") != action_id
            or published.get("use_action_class") != route["native_class"]
            or published.get("use_has_criteria") is not False
            or route["criteria"]
        ):
            raise ValueError("La acción no coincide con el catálogo nativo activo")
        if _equipped(current, uid):
            raise ValueError("Desequipa este objeto antes de utilizarlo")
        if source == route["destination"]:
            raise ValueError("Ya estás en el destino de este objeto")
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, character_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (uid, character_id),
            )
        relocated = relocate_in_transaction(
            store,
            db,
            account_id,
            generation,
            character_id,
            source,
            route["destination"],
            cohort=cohort,
        )
        metadata = dict(
            native_class=route["native_class"],
            native_parameters=route["parameters"],
            requested_destination=route["requested_destination"],
            arrival_policy=route["arrival_policy"],
            recall_policy=route["recall_policy"],
            source_sha256=route.get("source_sha256", SOURCE_SHA256),
            cohort=list(cohort),
            before_quantity=item["quantity"],
        )
        receipt = db.execute(
            "INSERT INTO item_teleport_receipts(token,account_id,generation,character_id,"
            "source_item_uid,source_item_ref,action_id,source,destination,metadata,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid.uuid4().hex,
                account_id,
                generation,
                character_id,
                uid,
                item["reference"],
                action_id,
                Jsonb(source),
                Jsonb(route["destination"]),
                Jsonb(metadata),
                store.now(),
            ),
        ).fetchone()
        return _result(
            store,
            db,
            account_id,
            character_id,
            receipt,
            packets=[(12470, struct.pack(">qh", uid, -1))],
            applied=True,
        )


def acknowledge(store, account_id, generation, character_id, token):
    """Fence the successful native map handoff; repeated acknowledgement is safe."""
    if not isinstance(token, str) or not token:
        raise ValueError("Invalid item teleport delivery token")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id, selected=True)
        receipt = db.execute(
            "SELECT * FROM item_teleport_receipts WHERE token=%s AND account_id=%s "
            "AND character_id=%s FOR UPDATE",
            (token, account_id, character_id),
        ).fetchone()
        if receipt is None:
            raise ValueError("Foreign item teleport delivery")
        if receipt["delivered_at"] is not None:
            return True
        current = store.character(account_id, character_id, db)
        if any(current[key] != receipt["destination"][key] for key in LOCATION_KEYS):
            raise ValueError("Item teleport delivery destination changed")
        db.execute(
            "UPDATE item_teleport_receipts SET delivered_at=COALESCE(delivered_at,%s) WHERE token=%s",
            (store.now(), token),
        )
        return True


def pending(store, account_id, generation, character_id):
    """Recover a committed arrival for the currently leased reconnecting actor."""
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id, selected=True)
        receipt = db.execute(
            "SELECT * FROM item_teleport_receipts WHERE account_id=%s AND character_id=%s "
            "AND delivered_at IS NULL ORDER BY created_at DESC,token DESC LIMIT 1 FOR UPDATE",
            (account_id, character_id),
        ).fetchone()
        if receipt is None:
            return None
        current = store.character(account_id, character_id, db)
        if any(current[key] != receipt["destination"][key] for key in LOCATION_KEYS):
            return None
        return _result(store, db, account_id, character_id, receipt)
