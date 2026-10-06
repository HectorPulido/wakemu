"""Current client build editing (cnR 12772 / ctU 12284), locally owned only."""
import struct
from protocol_codec import Reader
from wakfu_server.wire import proto_fields, proto_field, varint

KEYS = ("sheet", "equipment", "deck", "aptitudes")
EMPTY_EQUIPMENT = bytes.fromhex("a803ffffffffffffffffff01")
EMPTY_APTITUDES = bytes.fromhex("18ffffffffffffffffff01")


def capacity_message(character):
    """Native cEp22318 configuration delta; preserve unrelated settings."""
    limit = character["non_permanent_build_limit"]
    if type(limit) is not int or not 1 <= limit <= 24:
        raise ValueError("Invalid non-permanent build capacity")
    key = b"non.permanent.build.limit"
    value = str(limit).encode("utf-8")
    return (
        22318,
        struct.pack(">I", len(key)) + key + struct.pack(">I", len(value)) + value,
    )


def decode_activation(body):
    if len(body) != 9:
        raise ValueError("Invalid13776 activation length")
    actor_id, index = struct.unpack(">qb", body)
    if actor_id <= 0 or not valid_index(index):
        raise ValueError("Invalid13776 activation identity")
    return actor_id, index


def decode_deletion(body):
    if len(body) != 9:
        raise ValueError("Invalid13169 deletion length")
    actor_id, index = struct.unpack(">qb", body)
    if actor_id <= 0 or not valid_index(index):
        raise ValueError("Invalid13169 deletion identity")
    return actor_id, index


def deletion_message(actor_id, index, *, failed):
    # cnP.aIm()==true selects the error branch in cEN, not success.
    if (
        type(actor_id) is not int
        or not 0 < actor_id < (1 << 63)
        or not valid_index(index)
    ):
        raise ValueError("Invalid deletion response identity")
    if type(failed) is not bool:
        raise ValueError("Invalid deletion response status")
    return 12837, struct.pack(">qbB", actor_id, index, int(failed))


def selection_message(character):
    index = character["active_build_index"]
    if not valid_index(index) or index not in catalog_indices(character):
        raise ValueError("Invalid authoritative build selection")
    return 13811, struct.pack(">qb", character["id"], index)


def decode(body):
    r = Reader(body)
    character_id = r.number("q")
    blobs = {}
    for key in KEYS:
        size = r.number("I")
        if size > 65536:
            raise ValueError("Build section too large")
        blobs[key] = r.take(size)
    r.finish()
    fields = dict(proto_fields(blobs["sheet"]))
    if 8 not in fields:
        raise ValueError("Missing build index")
    return character_id, fields[8], blobs


def signed32(value):
    return (value & 0xFFFFFFFF) - (1 << 32) if value & 0x80000000 else value


def valid_index(index):
    """Native activation uses a signed byte; negative IDs are sentinels."""
    return type(index) is int and 0 <= index <= 127


def effective_sheet_level(character, index):
    if not valid_index(index) or index not in catalog_indices(character):
        raise ValueError("Unknown owned build level")
    saved = character.get("builds", {}).get(index)
    if saved is None:
        return character["level"]
    if not isinstance(saved.get("sheet"), str):
        raise ValueError("Missing owned build metadata")
    data = dict(proto_fields(bytes.fromhex(saved["sheet"])))
    if 24 not in data or type(data[24]) is not int:
        raise ValueError("Missing owned build level")
    level = signed32(data[24])
    if level == -1:
        return character["level"]
    if not 1 <= level <= character["level"]:
        raise ValueError("Owned build exceeds character level")
    return level


def validate_capacity(character, index, data):
    saved = character.get("builds", {})
    previous = saved.get(index)
    permanent = bool(data.get(64, 0))
    if index != 0:
        was_permanent = previous is not None and bool(
            dict(proto_fields(bytes.fromhex(previous["sheet"]))).get(64, 0)
        )
        if permanent != was_permanent:
            raise ValueError("Client cannot change permanent build classification")
    limit = character.get("non_permanent_build_limit", 24)
    if type(limit) is not int or not 1 <= limit <= 24:
        raise ValueError("Invalid non-permanent build capacity")
    # Only owned saved sheets consume capacity; default build0 is permanent.
    non_permanent = set()
    for key, build in saved.items():
        if key and not dict(proto_fields(bytes.fromhex(build["sheet"]))).get(64, 0):
            non_permanent.add(key)
    if index and not data.get(64, 0):
        non_permanent.add(index)
    if len(non_permanent) > limit:
        raise ValueError("Non-permanent build capacity exceeded")


def validate(character, index, blobs):
    if not valid_index(index):
        raise ValueError("Invalid build index")
    fields = list(proto_fields(blobs["sheet"]))
    data = dict(fields)
    if (
        len(data) != len(fields)
        or set(data) - {8, 18, 24, 56, 64}
        or not {8, 18, 24, 56} <= set(data)
    ):
        raise ValueError("Invalid build sheet")
    if data[8] != index or not isinstance(data[18], bytes) or len(data[18]) > 128:
        raise ValueError("Invalid build identity")
    data[18].decode("utf8")
    if (
        (signed32(data[24]) != -1 and not 1 <= signed32(data[24]) <= character["level"])
        or not 0 <= data[56] <= 255
        or data.get(64, 0) not in (0, 1)
    ):
        raise ValueError("Invalid build properties")
    validate_capacity(character, index, data)
    cap = character["level"] if signed32(data[24]) == -1 else signed32(data[24])
    validation_character = dict(character, level=cap, effective_level=cap)
    if blobs["equipment"]:
        from wakfu_server.equipment import validate_sheet

        validate_sheet(validation_character, blobs["equipment"])
    if blobs["aptitudes"]:
        from wakfu_server.aptitudes import validate as validate_aptitudes

        validate_aptitudes(validation_character, blobs["aptitudes"])
    if blobs["deck"]:
        from wakfu_server.spells import validate_deck

        validate_deck(blobs["deck"], character["breed"], cap)


def response(character, index, status=0):
    # ctU.dp calls eQQ.eP(byte), which indexes values(): OK=0. eQQ.d()
    # returns a separate localization error code (-1 for OK), not the wire byte.
    saved = character.get("builds", {}).get(index)
    has_data = status == 0 and saved is not None
    result = struct.pack(">qibB", character["id"], index, status, int(has_data))
    if has_data:
        from wakfu_server.spells import default_deck

        # Absent protobuf level fields decode as zero. The UI queries its
        # aptitude-level catalog and has no level-zero record; -1 means the
        # current character level, as in the official fresh-character sheets.
        defaults = {
            "sheet": b"",
            "equipment": EMPTY_EQUIPMENT,
            "deck": default_deck(character),
            "aptitudes": EMPTY_APTITUDES,
        }
        for key in KEYS:
            blob = bytes.fromhex(saved[key]) or defaults[key]
            result += struct.pack(">I", len(blob)) + blob
    return result


def response_messages(character, index, *, wp, status=0):
    """ACK first, then the owned effective actor snapshot after local preview.

    fpm equips optimistically and invokes biB.doT/eHi.fuP, which evaluates
    item effects locally. Our running-effect inventory is currently empty;
    a canonical snapshot prevents that preview from retaining a duplicate
    bonus over an already-effective bootstrap. This does not manufacture
    native running effects or replace the equipment registry carrier.
    """
    packets = [(12284, response(character, index, status))]
    if status == 0 and index in character.get("builds", {}):
        from wakfu_server.combat_lifecycle import outside_progression

        registry = proto_field(10, equipment_registry(character))
        aptitudes = aptitude_registry(character)
        packets.extend(
            [
                (12393, struct.pack(">I", len(registry)) + registry),
                (
                    12103,
                    struct.pack(">qI", character["id"], len(aptitudes)) + aptitudes,
                ),
                outside_progression(character, wp=wp),
            ]
        )
    return packets


def rejection_response(character, index, *, status):
    """Return the prior authoritative sheet alongside a failed save status.

    cER reads has_data independently of eQQ success, so an unsuccessful
    optimistic edit can be replaced without pretending its validation passed.
    Slot0 always exists in our native bootstrap; unknown new slots have no
    prior sheet to restore and receive only their ordinary negative ACK.
    """
    if type(status) is not int or not 0 < status < 128:
        raise ValueError("Expected failed native build status")
    saved = character.get("builds", {})
    if index != 0 and index not in saved:
        return response(character, index, status)
    canonical = character
    if index not in saved:
        default = next(
            value
            for tag, value in proto_fields(build_set(character, b""))
            if tag == 18 and dict(proto_fields(value))[8] == index
        )
        canonical = dict(
            character,
            builds={
                **saved,
                index: dict(
                    sheet=default.hex(),
                    equipment=EMPTY_EQUIPMENT.hex(),
                    deck="",
                    aptitudes=EMPTY_APTITUDES.hex(),
                ),
            },
        )
    # Keep the four authoritative blobs while substituting the error byte.
    body = response(canonical, index)
    body = body[:12] + struct.pack(">b", status) + body[13:]
    return body


def blocked_save_messages(character, request_body):
    """Reject an owned save during combat and restore its prior native sheet.

    Only the build ACK is sent: an outside-combat actor progression snapshot
    would overwrite authoritative combat resources. No persistence is mutated.
    """
    actor_id, index, _ = decode(request_body)
    if actor_id != character["id"]:
        raise ValueError("Build request belongs to another character")
    if not valid_index(index):
        raise ValueError("Invalid build index")
    return [(12284, rejection_response(character, index, status=2))]


def rejection_messages(character, index, *, wp, status):
    body = rejection_response(character, index, status=status)
    if not body[13]:
        return [(12284, body)]
    from wakfu_server.inventory_items import equipment_inventory
    from wakfu_server.combat_lifecycle import outside_progression

    return [
        equipment_inventory(character),
        (12284, body),
        outside_progression(character, wp=wp),
    ]


def deck_collection(character):
    from wakfu_server.spells import default_deck

    saved = character.get("builds", {})
    # bhp.dkV resolves the active sheet in this registry when opening builds.
    # Publish empty saved sheets with the same initial deck as the save ACK.
    decks = [
        (
            index,
            bytes.fromhex(saved.get(index, {}).get("deck", ""))
            or default_deck(character),
        )
        for index in catalog_indices(character)
    ]
    raw = struct.pack(">i", len(decks)) + b"".join(
        struct.pack(">b", index) + deck for index, deck in decks
    )
    return struct.pack(">H", len(raw)) + raw


def catalog_indices(character):
    """Publish the permanent default and owned saved sheets only."""
    indices = {0, *character.get("builds", {})}
    if any(not valid_index(index) for index in indices):
        raise ValueError("Invalid owned build catalog index")
    return sorted(indices)


def build_set(character, original):
    # Native slot zero is permanent, but editable; the fixture additionally
    # contained permanent level20..140 builds, which do not belong to this player.
    list(proto_fields(original))
    saved = character.get("builds", {})
    indices = catalog_indices(character)
    active = character.get("active_build_index", 0)
    if not valid_index(active) or active not in indices:
        raise ValueError("Invalid selected build")
    result = proto_field(8, active)
    for index in indices:
        if index in saved:
            sheet = bytes.fromhex(saved[index]["sheet"])
        else:
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in [
                    (8, index),
                    (18, b"Build por defecto" if index == 0 else b"Build 2"),
                    (24, (1 << 64) - 1),
                    (56, 1),
                    (64, int(index == 0)),
                ]
            )
        result += proto_field(18, sheet)
    return result


def equipment_registry(character):
    """hV/fpl: field1 map(build index -> ia gear), field2 owned character ID.

    cia decodes 12393 through fpi.eO and registers this fpl in fpo.
    biB.Dj(index) reads that registry independently of eQW/aptitude sheets.
    """
    saved = character.get("builds", {})
    indices = catalog_indices(character)
    entries = b"".join(
        proto_field(
            10,
            proto_field(8, index)
            + proto_field(
                18,
                bytes.fromhex(saved[index]["equipment"]) or EMPTY_EQUIPMENT
                if index in saved
                else EMPTY_EQUIPMENT,
            ),
        )
        for index in indices
    )
    return entries + proto_field(16, character["id"])


def aptitude_registry(character):
    """ef/eQJ map(index -> eb aptitude sheet), eQx.ey for 12103/12666."""
    saved = character.get("builds", {})
    return b"".join(
        proto_field(
            18,
            proto_field(8, index)
            + proto_field(
                18,
                bytes.fromhex(saved[index]["aptitudes"]) or EMPTY_APTITUDES
                if index in saved
                else EMPTY_APTITUDES,
            ),
        )
        for index in catalog_indices(character)
    )
