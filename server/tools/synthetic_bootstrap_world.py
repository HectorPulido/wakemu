"""Typed neutral world wrappers over freshly serialized original entities.

Slots preserve the existing server replay windows. No captured packet body,
account credential, player inventory, progress or environmental state is read.
Unknown and unnecessary replay records are deliberately absent from the result.
"""
from collections.abc import Mapping
import struct
import zlib


def _varint(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError("Invalid synthetic protobuf integer")
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _bytes_field(number, body):
    return _varint((number << 3) | 2) + _varint(len(body)) + body


def _entity(entities, format_id):
    body = entities.get(format_id)
    if type(body) is not bytes or not body or body[0] != format_id:
        raise ValueError("Missing freshly serialized native entity format")
    if len(body) > 32767:
        raise ValueError("Synthetic entity exceeds native signed-short wrapper")
    return body


def map_context(entity28):
    """csW13974: own entity, empty protector/fight lists, native eUZ defaults.

    csW.dp reads four unsigned-short-sized blocks; ciu passes block4 through
    eVa.eD into ProtoDungeon. The values below match the original eUZ constructor
    and existing proto_dungeon defaults, rather than an empty guessed payload.
    """
    if type(entity28) is not bytes or len(entity28) != 56 or entity28[0] != 28:
        raise ValueError("Native map context requires complete format28 entity")
    dungeon = bytes((8, 0, 16, 2, 24, 0, 32, 1, 40, 0, 48, 0, 64, 0))
    blocks = (entity28, struct.pack(">H", 0), struct.pack(">H", 0), dungeon)
    return b"".join(struct.pack(">H", len(block)) + block for block in blocks)


def world_frames(entities, account_id, character_id, name):
    """Return slot -> (opcode,body), leaving unsupported slots to the assembler.

    Account component markers are replaced by actual owned serializers in
    local_game_server.replay; they contain only native constructor defaults.
    These synthetic identities must match the final generator's template IDs.
    """
    from wakfu_server.social import ACCOUNT_DEFAULTS
    from wakfu_server.company_authority import preselection_packet

    if (
        not isinstance(entities, Mapping)
        or type(account_id) is not int
        or not 0 < account_id < 2**63
        or type(character_id) is not int
        or not 0 < character_id < 2**63
        or account_id == character_id
        or type(name) is not str
        or not name
    ):
        raise ValueError("Invalid explicit synthetic world identities")
    entity5, entity10, entity11, entity22, entity28 = (
        _entity(entities, key) for key in (5, 10, 11, 22, 28)
    )
    for entity in (entity5, entity10, entity11, entity28):
        if len(entity) < 9 or struct.unpack_from(">q", entity, 1)[0] != character_id:
            raise ValueError("Synthetic world entity belongs to another actor")

    qchar = struct.pack(">q", character_id)
    company = preselection_packet(account_id)[1]
    frames = {
        28: (22731, struct.pack(">h", -1)),
        31: (13078, qchar + struct.pack(">I", 0)),
        32: (13078, qchar + struct.pack(">I", 0)),
        34: (13078, qchar + struct.pack(">I", 0)),
        36: (13873, struct.pack(">III", 2, 0, 0) + company[4:]),
        37: (13873, struct.pack(">III", 2, 8, 0) + struct.pack(">II", 9, 0)),
        38: (13873, struct.pack(">II", 1, 7) + ACCOUNT_DEFAULTS[7]),
        40: (23548, struct.pack(">BI", 1, len(entity5)) + entity5 + b"\x00"),
        41: (22790, b"\x00"),
        # cEi.dp reads one byte; cgY.a enters the selected-world handlers
        # only for zero. Nonzero is error.characterSelection, not success.
        45: (23082, b"\x00"),
        46: (13873, company),
        58: (630, b""),
        60: (12996, qchar + struct.pack(">I", 0)),
        61: (12103, qchar + struct.pack(">I", 0)),
        62: (
            12666,
            struct.pack(">HI", 0, len(entity10)) + entity10 + struct.pack(">II", 0, 0),
        ),
        63: (13713, qchar + struct.pack(">BH", 4, 0)),
        64: (13974, map_context(entity28)),
        65: (13778, struct.pack(">bb", 0, 0)),
        66: (12318, entity28[18:26]),
        77: (
            12608,
            struct.pack(">BBBqH", 0, 1, 0, character_id, len(entity11)) + entity11,
        ),
        92: (15548, qchar + struct.pack(">h", len(entity22)) + entity22),
        95: (1029, struct.pack(">I", 0)),
        99: (15529, qchar + struct.pack(">h", 0)),
        109: (15548, qchar + struct.pack(">h", len(entity22)) + entity22),
    }
    # hN contains one hV; only its explicit identity is needed by the owned
    # equipment_registry replacement, which supplies actual build sheets.
    registry = _bytes_field(1, _varint(16) + _varint(character_id))
    frames[39] = (12393, struct.pack(">I", len(registry)) + registry)

    # Replay recognizes these by section header, not historical slot position.
    # All nonempty defaults are the shared source-qualified component encodings.
    for slot, section in (
        (47, 4),
        (48, 7),
        (49, 8),
        (50, 9),
        (51, 10),
        (52, 11),
        (53, 12),
        (54, 13),
        (55, 14),
        (100, 15),
        (108, 17),
        (110, 18),
    ):
        component = struct.pack(">I", 0) if section == 4 else ACCOUNT_DEFAULTS[section]
        frames[slot] = (13873, struct.pack(">II", 1, section) + component)
    for slot in (80, 97, 98):
        # Native12436 template only; wire.adapt substitutes owned HP and regen.
        frames[slot] = (12436, qchar + struct.pack(">ii", 1, 0))
    for slot in range(125, 130):
        frames[slot] = (14303, zlib.compress(b""))
    return frames
