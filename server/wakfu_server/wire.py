"""Explicit fixture adapter. The complete entity serializer is still pending."""
from .paths import DATA_ROOT
import struct
import json
import hashlib
from pathlib import Path
from protocol_codec import Reader, APPEARANCE_FIELDS
from wakfu_server.spells import spell_inventory, default_deck
from wakfu_server.progression import level_xp, character_xp

TEMPLATE_ACCOUNT = 83668792
TEMPLATE_CHARACTER = 2409354
INITIAL_POSITION = struct.pack(">iih", -12, -8, -1)
PROTOCOL = DATA_ROOT
ENTITY_LAYOUTS = {
    record["format"]: record
    for record in json.loads((PROTOCOL / "entity-layouts.json").read_text())
}
ENTITY_DEFAULTS = {
    name: bytes.fromhex(value)
    for name, value in json.loads(
        (PROTOCOL / "entity-defaults.json").read_text()
    ).items()
}
EMPTY_SECTIONS = {
    "GUILD_ID",
    "GUILD_BLAZON",
    "SOCIAL_STATES",
    "NATION_ID",
    "CHARACTER_LIST_NATION_ID",
    "NATION_SYNCHRO",
    "SHORTCUT_INVENTORIES",
    "INVENTORIES",
    "BAGS",
    "PROTO_TEMPORARY_INVENTORY",
    "CHALLENGES",
    "XP",
    "XP_CHARACTERISTICS",
    "CITIZEN_POINT",
    "PET",
    "ACHIEVEMENTS",
    "PERSONAL_EFFECTS",
    "RUNNING_EFFECTS",
    "SPELL_DECK",
    "DUNGEON_PROGRESSION",
    "EQUIPMENT_APPEARANCE",
    "COSMETICS",
}


def minimal_entity(body, character):
    """Replace verified fixture sections with the client's own empty encoding."""
    if character.get("level") is None:
        return body
    level_xp(character["level"])
    layout = ENTITY_LAYOUTS.get(body[0])
    if layout is None or not any(
        s["name"] in EMPTY_SECTIONS for s in layout["sections"]
    ):
        return body
    if hashlib.sha256(body).hexdigest() != layout["template_sha256"]:
        raise ValueError("Entity fixture does not match verified section boundaries")
    for section in reversed(layout["sections"]):
        replacement = None
        if section["name"] == "APPEARANCE" and character.get("appearance"):
            replacement = appearance_section(character["appearance"])
        elif section["name"] in ("NATION_ID", "CHARACTER_LIST_NATION_ID"):
            # Own characters have no nation until an authoritative local model exists.
            replacement = struct.pack(">i", 0)
        elif section["name"] == "NATION_SYNCHRO":
            # rk constructor and clear(): rank/jobs/voteDate (3*i64),
            # governmentOpinion/candidate/pvpRank (3*byte), all zero.
            replacement = bytes(27)
        elif section["name"] == "BREED":
            replacement = struct.pack(">h", character["breed"])
        elif section["name"] == "DIMENSIONAL_BAG_FOR_LOCAL_CLIENT":
            from wakfu_server.haven_bag import own_bag

            replacement = own_bag(character)
        elif section["name"] == "BAGS":
            from wakfu_server.inventory import bags

            replacement = bags(character)
        elif section["name"] == "SPELL_INVENTORY":
            replacement = spell_inventory(character)
        elif section["name"] == "SPELL_DECK" and character.get("builds"):
            from wakfu_server.builds import deck_collection

            replacement = deck_collection(character)
        elif section["name"] == "SPELL_DECK":
            deck = struct.pack(">iB", 1, 0) + default_deck(character)
            replacement = struct.pack(">H", len(deck)) + deck
        elif section["name"] == "XP":
            replacement = struct.pack(">q", character_xp(character))
        elif section["name"] in EMPTY_SECTIONS:
            replacement = ENTITY_DEFAULTS[section["name"]]
        if replacement is not None:
            body = body[: section["start"]] + replacement + body[section["end"] :]
    return body


def appearance_section(appearance):
    """oW: u16 length + dS ProtoAppearance, with signed int32 varints."""
    if any(
        key not in APPEARANCE_FIELDS
        or type(value) is not int
        or not -(1 << 31) <= value < (1 << 31)
        for key, value in appearance.items()
    ):
        raise ValueError("Invalid appearance fields")
    appearance = {
        **{
            key: -1 if number < 9 else 0
            for number, key in enumerate(APPEARANCE_FIELDS[:12])
        },
        **appearance,
    }
    encoded = b"".join(
        varint(number << 3) + varint(value if value >= 0 else value + (1 << 64))
        for number, key in enumerate(APPEARANCE_FIELDS, 1)
        if (value := appearance.get(key)) is not None
    )
    return struct.pack(">H", len(encoded)) + encoded


def initial_progression(body, character):
    """Set owned character XP in the two verified eHf entity formats.

    Offsets apply before the variable-length name is rewritten. eHk's section
    readers consumed both original blobs completely; sG reads one i64 XP.
    Equipment and aptitudes still require separate initialization.
    """
    offsets = {5: 262, 10: 4614}
    offset = offsets.get(body[0])
    if offset is None or character.get("level") is None:
        return body
    if struct.unpack_from(">q", body, offset)[0] != 4094076145:
        raise ValueError("Unexpected fixture XP layout")
    return (
        body[:offset] + struct.pack(">q", character_xp(character)) + body[offset + 8 :]
    )


def character_levels(body, character):
    """13873 CHARACTERS section: count, kind=0, count, (i64, i16)."""
    r = Reader(body)
    sections, kind = r.number("I"), r.number("I")
    if kind != 0:
        return identity(body, character["account_id"], character)
    r.take(r.number("I") * 10)
    return struct.pack(
        ">IIIqH", sections, kind, 1, character["id"], character["level"]
    ) + identity(body[r.pos :], character["account_id"], character)


def without_equipment_appearance(body, character):
    """pO is u8 count + count pR entries (slot u8, item i32, skin i32).

    Boundaries come from OfflineEntityLayout for this exact fixture; applied
    before the name changes. Inventory ownership is initialized separately.
    """
    if character.get("level") is None:
        return body
    level_xp(character["level"])
    bounds = {5: (147, 256), 10: (10336, 10445), 11: (808, 917)}
    if body[0] not in bounds:
        return body
    start, end = bounds[body[0]]
    if len(body) < end or 1 + body[start] * 9 != end - start:
        raise ValueError("Unexpected fixture equipment appearance layout")
    return body[:start] + b"\x00" + body[end:]


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def proto_fields(body):
    """Read protobuf wire fields without interpreting opaque nested messages."""
    r = Reader(body)

    def integer():
        value = 0
        for shift in range(0, 70, 7):
            byte = r.number("B")
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Invalid protobuf varint")

    while r.pos < len(body):
        tag = integer()
        kind = tag & 7
        if kind == 0:
            value = integer()
        elif kind == 2:
            value = r.take(integer())
        elif kind in (1, 5):
            value = r.take(8 if kind == 1 else 4)
        else:
            raise ValueError("Unsupported protobuf field")
        yield tag, value


def proto_field(tag, value):
    if tag & 7 == 0:
        return varint(tag) + varint(value)
    if tag & 7 == 2:
        return varint(tag) + varint(len(value)) + value
    return varint(tag) + value


def attribute_sheets(body, characters):
    """12393/cxD: u32 length + hN, repeated hV with characterId field 2.

    Layout confirmed against cia, fpi and hV.writeTo in this client version.
    Clean defaults match the observed fresh-character sheet at every level: map key 0,
    an empty ia/ProtoEquipmentSheet with level -1 (field 53), and own characterId.
    """
    r = Reader(body)
    sets = list(proto_fields(r.take(r.number("I"))))
    r.finish()
    templates = [list(proto_fields(value)) for tag, value in sets if tag == 10]
    template = next(
        fields for fields in templates if (16, TEMPLATE_CHARACTER) in fields
    )
    from wakfu_server.builds import equipment_registry

    result = b"".join(
        proto_field(10, equipment_registry(character))
        if character.get("level") is not None
        else proto_field(
            10,
            b"".join(
                proto_field(tag, character["id"] if tag == 16 else value)
                for tag, value in template
            ),
        )
        for character in characters
    )
    return struct.pack(">I", len(result)) + result


def identity(body, account_id, character=None):
    body = body.replace(
        struct.pack(">q", TEMPLATE_ACCOUNT), struct.pack(">q", account_id)
    )
    if character:
        body = body.replace(
            struct.pack(">q", TEMPLATE_CHARACTER), struct.pack(">q", character["id"])
        )
    return body


def header(body, account_id, character):
    r = Reader(body)
    r.take(18)  # type u8, actor i64, identity flag u8, account i64
    name = r.text("H")
    if name != "Pekebu":
        raise ValueError("Unexpected captured character header")
    suffix = body[r.pos :]
    encoded_name = character["name"].encode()
    return (
        identity(body[:18], account_id, character)
        + struct.pack(">H", len(encoded_name))
        + encoded_name
        + suffix
    )


def position(body, character):
    if body.count(INITIAL_POSITION) != 1:
        raise ValueError("Ambiguous captured position")
    return body.replace(
        INITIAL_POSITION,
        struct.pack(">iih", character["x"], character["y"], character["z"]),
    )


def character_list(template, account_id, characters):
    r = Reader(template)
    r.take(1)
    template_blob = r.take(r.number("I"))
    result = bytearray([len(characters)])
    for character in characters:
        blob = header(minimal_entity(template_blob, character), account_id, character)
        result.extend(struct.pack(">I", len(blob)))
        result.extend(blob)
    result.extend(b"\x00")  # No inherited companion records.
    return bytes(result)


def spawn_player(template, character):
    blob = header(
        position(minimal_entity(template, character), character),
        character["account_id"],
        character,
    )
    return b"\x00\x01" + struct.pack(">BqH", 0, character["id"], len(blob)) + blob


def remove_player(character_id):
    # ctA: teleport flag, secondary flag, count, then (type, actorId).
    return b"\x00\x00\x01" + struct.pack(">Bq", 0, character_id)


def without_captured_players(body):
    r = Reader(body)
    flag = r.number("B")
    entries = []
    for _ in range(r.number("B")):
        actor_type, actor_id = r.number("B"), r.number("q")
        blob = r.take(r.number("H"))
        if actor_type != 0:
            entries.append(struct.pack(">BqH", actor_type, actor_id, len(blob)) + blob)
    r.finish()
    return bytes([flag, len(entries)]) + b"".join(entries)


def captured_haven_bag_records(body):
    """cwG (13664): dynamic interactive records from the captured session.

    Template 3700 is confirmed by the fixture's owner name Manama and the
    client's visible "Merkasako de Manama" tooltip. Preserve other templates.
    """
    r = Reader(body)
    entries = []
    for _ in range(r.number("H")):
        start = r.pos
        instance_id, template_id = r.number("q"), r.number("q")
        r.take(r.number("H"))
        r.number("q")
        entries.append((instance_id, template_id, body[start : r.pos]))
    r.finish()
    return entries


def without_captured_haven_bags(body):
    entries = [
        record
        for _, template, record in captured_haven_bag_records(body)
        if template != 3700
    ]
    return struct.pack(">H", len(entries)) + b"".join(entries)


def remove_captured_haven_bags(body):
    ids = [
        instance
        for instance, template, _ in captured_haven_bag_records(body)
        if template == 3700
    ]
    return struct.pack(">H", len(ids)) + b"".join(
        struct.pack(">q", instance) for instance in ids
    )


def movement_path(character_id, request_body):
    """csR (13852): forward the client's exact packed path, including height.

    cny (13331) prefixes aAT with an i32 movement mode; csR replaces that
    prefix with i64 actor ID. The owning client already animates this path.
    """
    from protocol_codec import decode_body

    decode_body("out", 13331, request_body)
    return struct.pack(">q", character_id) + request_body[4:]


def chat(character, text):
    name, text = character["name"].encode(), text.encode()
    if len(name) > 255 or not 1 <= len(text) <= 2048:
        raise ValueError("Invalid chat message length")
    # On (674), vicinity: NQ payload without NP's channel prefix.
    # The identity flag is true for a character ID, false for an account ID.
    return (
        struct.pack(">B", len(name))
        + name
        + struct.pack(">BBqB", 6, 4, character["id"], 1)
        + struct.pack(">H", len(text))
        + text
    )


def empty_equipment_sheets(body, character):
    """Keep build slots, remove each ProtoEquipmentSheet's item references."""
    r = Reader(body)
    r.take(8)
    fields = list(proto_fields(r.take(r.number("I"))))
    r.finish()
    result = bytearray()
    for tag, value in fields:
        if tag == 10:  # ProtoEquipmentSet.sheets map entry
            entry = bytearray()
            for entry_tag, entry_value in proto_fields(value):
                if entry_tag == 18:
                    entry_value = b"".join(
                        proto_field(t, (1 << 64) - 1 if t == 424 else v)
                        for t, v in proto_fields(entry_value)
                        if t != 10
                    )
                entry.extend(proto_field(entry_tag, entry_value))
            value = bytes(entry)
        elif tag == 16:
            value = character["id"]
        result.extend(proto_field(tag, value))
    return struct.pack(">qI", character["id"], len(result)) + result


def adapt(opcode, body, account_id, character=None, *, kamas=None):
    if opcode == 12436 and character is not None:
        from wakfu_server.health import packet

        return packet(character["id"], character["hp"], 1)
    if kamas is None:
        kamas = character.get("kamas", 0) if character else 0
    if type(kamas) is not int or not 0 <= kamas < 2**63:
        raise ValueError("Invalid account wallet balance")
    if opcode == 13021:
        # foF applies this balance after account initialization; replaying the
        # captured value would overwrite the local account's zero kamas.
        if len(body) != 8:
            raise ValueError("Invalid kama update length")
        return struct.pack(">q", kamas)
    if opcode == 13873 and len(body) >= 8 and struct.unpack(">II", body[:8]) == (1, 4):
        r = Reader(body)
        r.take(8)
        r.take(r.number("I"))
        r.finish()
        return struct.pack(">III", 1, 4, 0)
    if opcode == 13873 and len(body) == 16 and struct.unpack(">II", body[:8]) == (1, 6):
        return account_kamas(kamas)
    if character and character.get("level") is not None:
        if opcode == 13078:
            from wakfu_server.inventory_items import equipment_inventory

            return equipment_inventory(character)[1]
        if opcode == 12103:
            from wakfu_server.builds import aptitude_registry

            proto = aptitude_registry(character)
            return struct.pack(">qI", character["id"], len(proto)) + proto
        if opcode == 12996:
            from wakfu_server.builds import build_set

            r = Reader(body)
            r.take(8)
            proto = r.take(r.number("I"))
            r.finish()
            proto = build_set(character, proto)
            return struct.pack(">qI", character["id"], len(proto)) + proto
        if opcode == 13713:
            return struct.pack(">q", character["id"]) + minimal_entity(
                body[8:], character
            )
    if opcode == 12666 and character:
        r = Reader(body)
        count = r.number("H")
        prefix = struct.pack(">H", count) + r.take(count * 8)
        blocks = [r.take(r.number("I")) for _ in range(3)]
        r.finish()
        blocks[0] = header(
            position(minimal_entity(blocks[0], character), character),
            account_id,
            character,
        )
        blocks[1:] = [identity(block, account_id, character) for block in blocks[1:]]
        if character.get("level") is not None:
            from wakfu_server.builds import aptitude_registry

            blocks[2] = aptitude_registry(character)
        if character.get("level") is not None:
            from wakfu_server.builds import build_set

            blocks[1] = build_set(character, blocks[1])
        return prefix + b"".join(
            struct.pack(">I", len(block)) + block for block in blocks
        )
    if opcode == 13974 and character:
        from wakfu_server.haven_bag import map_transition

        return map_transition(body, character, character["map_id"])
    if opcode == 13873 and character:
        return character_levels(body, character)
    return identity(body, account_id, character)


def account_kamas(amount):
    """13873/eDS.KAMAS/fpq: single section with signed i64 balance."""
    if type(amount) is not int or not 0 <= amount < (1 << 63):
        raise ValueError("Invalid kama balance")
    return struct.pack(">IIq", 1, 6, amount)
