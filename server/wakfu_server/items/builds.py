"""Current client build editing (cnR 12772 / ctU 12284), locally owned only."""
import struct
from protocol_codec import Reader
from wakfu_server.wire import proto_fields, proto_field, varint

KEYS = ("sheet", "equipment", "deck", "aptitudes")
EMPTY_EQUIPMENT = bytes.fromhex("a803ffffffffffffffffff01")
EMPTY_APTITUDES = bytes.fromhex("18ffffffffffffffffff01")


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


def validate(character, index, blobs):
    if type(index) is not int or not 0 <= index <= 2:
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
        signed32(data[24]) not in (-1, character["level"])
        or not 0 <= data[56] <= 255
        or data.get(64, 0) not in (0, 1)
    ):
        raise ValueError("Invalid build properties")
    if blobs["equipment"]:
        from wakfu_server.equipment import validate_sheet

        validate_sheet(character, blobs["equipment"])
    if blobs["aptitudes"]:
        from wakfu_server.aptitudes import validate as validate_aptitudes

        validate_aptitudes(character, blobs["aptitudes"])
    if blobs["deck"]:
        from wakfu_server.spells import validate_deck

        validate_deck(blobs["deck"], character["breed"], character["level"])


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

        packets.append(outside_progression(character, wp=wp))
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
    if type(index) is not int or not 0 <= index <= 2:
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
    decks = [
        (index, bytes.fromhex(data["deck"]))
        for index, data in sorted(character.get("builds", {}).items())
        if data["deck"]
    ]
    if not any(index == 0 for index, _ in decks):
        from wakfu_server.spells import default_deck

        decks.insert(0, (0, default_deck(character)))
    raw = struct.pack(">i", len(decks)) + b"".join(
        struct.pack(">b", index) + deck for index, deck in decks
    )
    return struct.pack(">H", len(raw)) + raw


def equipment_set(character, original):
    fields = list(proto_fields(original))
    saved = character.get("builds", {})
    out = []
    for tag, value in fields:
        if tag == 10:
            entry = dict(proto_fields(value))
            index = entry.get(8)
            if index in saved and saved[index]["equipment"]:
                value = proto_field(8, index) + proto_field(
                    18, bytes.fromhex(saved[index]["equipment"])
                )
        out.append(proto_field(tag, value))
    return b"".join(out)


def build_set(character, original):
    # Native slot zero is permanent, but editable; the fixture additionally
    # contained permanent level20..140 builds, which do not belong to this player.
    list(proto_fields(original))
    saved = character.get("builds", {})
    indices = sorted({0, 1, *saved})
    result = proto_field(8, 0)
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
    indices = sorted({0, *saved})
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
        for index in sorted({0, 1, *saved})
    )
