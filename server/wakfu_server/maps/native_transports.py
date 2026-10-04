"""Native ZAAP test routes from installed client data; no inherited world actors."""
from .paths import DATA_ROOT
import json, struct
from pathlib import Path

CATALOG = json.loads((DATA_ROOT / "native-transports.json").read_text())
ZAAPS = {row["id"]: row for row in CATALOG if row["kind"] == 1}
TRANSPORTS = {row["id"]: row for row in CATALOG if row["kind"] in (1, 2)}
OBJECTS = {
    row["id"]: row
    for row in json.loads((DATA_ROOT / "native-transport-objects.json").read_text())
}


def registration(character, body):
    if len(body) != 12:
        raise ValueError("Invalid interactive registration")
    identity, action = struct.unpack(">qH", body[:10])
    if action != 24 or body[10:] != b"\0\0":
        raise ValueError("Not a native REGISTER action")
    source = _source(character, identity)
    return source["kind"], source["id"]


def _source(character, identity):
    source = TRANSPORTS.get(identity)
    obj = OBJECTS.get(identity)
    if (
        source is None
        or obj is None
        or character["instance_id"] != 0
        or obj["map_id"] != character["map_id"]
    ):
        raise ValueError("Unknown or foreign-map ZAAP")
    source_heights = (obj["z"], *obj.get("arrival_heights", ()))
    if (
        min(abs(character["z"] - z) for z in source_heights) > 1
        or abs(character["x"] - obj["x"]) + abs(character["y"] - obj["y"]) > 4
    ):
        raise ValueError("Character is too far from the ZAAP")
    return source


def resolve(character, body, *, known_ids, waive_criteria=False):
    if len(body) != 16:
        raise ValueError("Invalid native transport request")
    source_id, destination_id = struct.unpack(">qq", body)
    source = _source(character, source_id)
    destination = TRANSPORTS.get(destination_id)
    obj = OBJECTS.get(destination_id)
    known = (
        known_ids.get(source["kind"], ()) if isinstance(known_ids, dict) else known_ids
    )
    if (
        destination is None
        or obj is None
        or destination["kind"] != source["kind"]
        or destination_id not in known
    ):
        raise ValueError("Unknown ZAAP destination")
    if len(obj["arrival_heights"]) != 1:
        raise ValueError("Unverified destination altitude")
    # Native entries may have criteria. The explicit local all-ZAAP test policy
    # waives them; restricted mode rejects criteria until their evaluator exists.
    if not waive_criteria and (source["condition"] or destination["condition"]):
        raise ValueError("Unsupported native travel criterion")
    return {
        "source_id": source_id,
        "destination_id": destination_id,
        "destination": dict(
            map_id=obj["map_id"],
            instance_id=0,
            x=destination["x"],
            y=destination["y"],
            z=obj["arrival_heights"][0],
        ),
    }


def bootstrap(character, *, direction=3):
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Invalid native arrival direction")
    # eHf28=ID(qt),IDENTITY(qv),POSITION(rE). rH is an empty secondary
    # position, matching a native newly constructed world context.
    entity = struct.pack(
        ">BqBqiihqBBiihq",
        28,
        character["id"],
        0,
        character["account_id"],
        character["x"],
        character["y"],
        character["z"],
        character["map_id"],
        direction,
        1,
        0,
        0,
        0,
        0,
    )
    # eVa.b(new eUZ()) verified by current JAR: clean non-dungeon defaults.
    context = bytes.fromhex("0800100218002001280030004000")
    body = b"".join(
        struct.pack(">H", len(block)) + block
        for block in (entity, b"\0\0", b"\0\0", context)
    )
    return [
        (13256, b""),
        (13974, body),
        (12318, struct.pack(">ii", character["x"], character["y"])),
    ]


def static_objects(map_id):
    """13984/cwJ current-map static Zaap/Drago data, from installed env only.

    cEX invokes bEG.b(ID,blob), reapplying native state and aWA visuals.
    Send when the destination environment objects have loaded, e.g. after
    client map-ready14689; early arrival can find no object and be ignored.
    """
    rows = sorted(
        (row for row in OBJECTS.values() if row["map_id"] == map_id),
        key=lambda row: row["id"],
    )
    records = []
    for row in rows:
        data = bytes.fromhex(row["payload_hex"])
        records.append(struct.pack(">qH", row["id"], len(data)) + data)
    return 13984, struct.pack(">H", len(records)) + b"".join(records)
