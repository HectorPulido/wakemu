"""Native RespawnPoint binding and saved-point arrival authority."""
from functools import lru_cache
import hashlib
import struct

SOURCE_SHA256 = "68b6e109987460deb3d1ebcc98bb4a85600eba6e56e8045a03d19517bcf7acb2"


@lru_cache(maxsize=1)
def points():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    path = DATA_ROOT / "native-map-objects.json"
    if hashlib.sha256(native_catalog.read_bytes(path)).hexdigest() != SOURCE_SHA256:
        raise ValueError("Native RespawnPoint source release changed")
    rows = native_catalog.load(path)
    selected = [dict(row) for row in rows if row["type"] == "RespawnPoint"]
    if len(selected) != 14 or len({row["id"] for row in selected}) != 14:
        raise ValueError("Native RespawnPoint coverage changed")
    return {row["id"]: row for row in selected}


def recognizes(body):
    return (
        isinstance(body, bytes)
        and len(body) == 12
        and struct.unpack_from(">q", body)[0] in points()
    )


def saved_identity(character):
    identity = character.get("saved_phoenix_id", 0)
    if type(identity) is not int or not 0 <= identity < 2**31:
        raise ValueError("Invalid owned native saved Phoenix identity")
    if identity and identity not in points():
        raise ValueError("Saved Phoenix is absent from the installed native map")
    return identity


def section(character):
    """Original rC.PHOENIX_PART is exactly one signed i32 object identity."""
    return struct.pack(">i", saved_identity(character))


def destination(character, *, geometry=None):
    identity = saved_identity(character)
    if not identity:
        raise ValueError("Activa primero un fénix para guardar tu punto de regreso")
    return point_destination(identity, geometry=geometry)


def point_destination(identity, *, geometry=None):
    from wakfu_server.combat_terrain import map_geometry

    point = points().get(identity)
    if point is None:
        raise ValueError("Unknown native RespawnPoint destination")
    native = (geometry or map_geometry)(point["map_id"])
    if native.get("map_id") != point["map_id"]:
        raise ValueError("Phoenix arrival geometry belongs to another map")
    cells = {tuple(cell) for cell in native["cells"]}
    origin = tuple(int(point[key]) for key in ("x", "y", "z"))
    # The interactive itself may occupy its surface. Use a native walkable
    # neighboring surface, never synthesize a tile or an altitude.
    candidates = [
        cell
        for cell in cells
        if abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 1
    ]
    if not candidates:
        raise ValueError("El fénix guardado no tiene una superficie de llegada válida")
    chosen = min(
        candidates,
        key=lambda cell: (cell[:2] == origin[:2], abs(cell[2] - origin[2]), *cell),
    )
    return dict(
        map_id=point["map_id"], instance_id=0, x=chosen[0], y=chosen[1], z=chosen[2]
    )


def activate(
    store, account_id, generation, character_id, body, *, in_fight=False, location=None
):
    """Commit only an adjacent original ACTIVATE0; the client already shows soulLinked."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("No puedes vincular un fénix durante el combate")
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid native Phoenix activation")
    identity, action, parameter = struct.unpack(">qHH", body)
    point = points().get(identity)
    if point is None or action != 0 or parameter != 0:
        raise ValueError("La acción no corresponde a un fénix original")
    from wakfu_server.simple_item_actions import _idle

    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id, selected=True)
        current = store.character(account_id, character_id, db)
        _idle(db, character_id, store.now())
        if current.get("health_dead", False) or current["hp"] <= 0:
            raise ValueError(
                "No puedes vincular un fénix mientras estás fuera de combate"
            )
        if location is not None and any(
            location.get(key) != current[key]
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError(
                "La posición del personaje cambió antes de vincular el fénix"
            )
        if current["instance_id"] != 0 or current["map_id"] != point["map_id"]:
            raise ValueError("El fénix no pertenece a tu mapa actual")
        if (
            abs(current["x"] - int(point["x"])) + abs(current["y"] - int(point["y"]))
            > 1
        ):
            raise ValueError("Acércate al fénix para guardar tu punto de regreso")
        from wakfu_server.combat_terrain import map_geometry

        native = map_geometry(current["map_id"])
        if tuple(current[key] for key in ("x", "y", "z")) not in {
            tuple(cell) for cell in native["cells"]
        }:
            raise ValueError(
                "La posición de activación no es una superficie nativa válida"
            )
        applied = current.get("saved_phoenix_id", 0) != identity
        db.execute(
            "UPDATE characters SET saved_phoenix_id=%s WHERE id=%s AND account_id=%s",
            (identity, character_id, account_id),
        )
        return dict(
            character=store.character(account_id, character_id, db),
            saved_phoenix_id=identity,
            applied=applied,
            packets=[],
        )
