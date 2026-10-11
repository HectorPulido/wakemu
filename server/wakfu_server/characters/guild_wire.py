"""Strict codecs for guild contracts evidenced by the installed client probes.

These helpers carry bytes only. Authorization, identity semantics and game rules
belong to the guild service. Unknown request and delta layouts are never guessed.
"""
import math
import struct
from collections.abc import Mapping


def _integer(value, bits):
    if type(value) is not int or not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError(f"Expected signed int{bits}")
    return value


def _varint(value):
    value &= (1 << 64) - 1
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field(number, kind, value):
    if kind in (32, 64):
        return _varint(number << 3) + _varint(_integer(value, kind))
    if kind == "bool":
        if type(value) is not bool:
            raise ValueError("Expected boolean")
        return _varint(number << 3) + bytes((int(value),))
    if kind == "str":
        if type(value) is not str:
            raise ValueError("Expected string")
        value = value.encode("utf-8")
    elif type(value) is not bytes:
        raise ValueError("Expected bytes")
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _model(model, schema):
    if not isinstance(model, Mapping):
        raise ValueError("Expected guild model mapping")
    missing = [name for _, name, _ in schema if name not in model]
    if missing:
        raise ValueError("Missing required guild fields: " + ", ".join(missing))
    return b"".join(_field(number, kind, model[name]) for number, name, kind in schema)


RANK_FIELDS = (
    (1, "id", 64),
    (2, "name", "str"),
    (3, "authorizations", 64),
    (4, "position", 32),
)
BONUS_FIELDS = ((1, "id", 32), (2, "activationDate", 64), (3, "buyDate", 64))
MEMBER_FIELDS = (
    (1, "id", 64),
    (2, "ownerId", 64),
    (3, "guildPoints", 32),
    (4, "rank", 64),
    (5, "xp", 64),
    (6, "isConnected", "bool"),
    (7, "smiley", "bytes"),
    (8, "sex", "bytes"),
    (9, "breedId", 32),
    (10, "nationId", 32),
    (11, "name", "str"),
    (12, "saveDate", 64),
    (13, "serializedLanguages", "bytes"),
    (14, "accountCommunityId", "bytes"),
)
GUILD_FIELDS = (
    (1, "guildId", 64),
    (2, "level", 32),
    (3, "blazon", 64),
    (5, "name", "str"),
    (6, "description", "str"),
    (7, "message", "str"),
    (8, "currentGuildPoints", 32),
    (9, "totalGuildPoints", 32),
    (10, "weeklyPointsLimit", 32),
    (11, "earnedPointsLimit", 32),
    (12, "lastEarningPointWeek", 32),
)


def serialize_rank(model):
    return _model(model, RANK_FIELDS)


def serialize_member(model):
    payload = _model(model, MEMBER_FIELDS)
    for name in ("smiley", "sex", "serializedLanguages", "accountCommunityId"):
        if len(model[name]) != 1:
            raise ValueError("Native member field requires exactly one byte: " + name)
    return payload


def serialize_bonus(model):
    return _model(model, BONUS_FIELDS)


def serialize_guild(model):
    result = _model(model, GUILD_FIELDS)
    for number, key, serializer in (
        (13, "ranks", serialize_rank),
        (14, "members", serialize_member),
        (15, "bonuses", serialize_bonus),
    ):
        entries = model.get(key, ())
        if not isinstance(entries, (list, tuple)):
            raise ValueError("Expected list or tuple for " + key)
        result += b"".join(
            _field(number, "bytes", serializer(entry)) for entry in entries
        )
    return result


def local_section(model=None, moderation_bonus_learning_factor=0.0):
    """qH body; caller must use the established local entity section carrier."""
    factor = moderation_bonus_learning_factor
    if type(factor) not in (float, int) or not math.isfinite(factor):
        raise ValueError("Expected finite moderation factor")
    payload = b"" if model is None else serialize_guild(model)
    if len(payload) > 65535:
        raise ValueError("Guild protobuf exceeds local section size")
    try:
        return struct.pack(">H", len(payload)) + payload + struct.pack(">f", factor)
    except (OverflowError, struct.error) as exc:
        raise ValueError("Moderation factor exceeds float32") from exc


def _text(value, maximum):
    if type(value) is not str:
        raise ValueError("Expected string")
    value = value.encode("utf-8")
    if len(value) > maximum:
        raise ValueError("Guild text exceeds native byte length")
    return value


def remote_info(guild_id, blazon, level, name):
    payload = _text(name, 65535)
    return (
        struct.pack(
            ">qqhH",
            _integer(guild_id, 64),
            _integer(blazon, 64),
            _integer(level, 16),
            len(payload),
        )
        + payload
    )


def creation_ack(name):
    payload = _text(name, 127)
    return 1000, bytes((len(payload),)) + payload


def delta_envelope(guild_id, deltas):
    """Frame externally verified (kind, payload) pairs; never infer payloads."""
    if not isinstance(deltas, (list, tuple)) or len(deltas) > 2147483647:
        raise ValueError("Expected bounded delta sequence")
    result = struct.pack(">qi", _integer(guild_id, 64), len(deltas))
    for kind, payload in deltas:
        if type(kind) is not int or not 0 <= kind <= 15:
            raise ValueError("Unknown guild delta kind")
        if type(payload) is not bytes or len(payload) > 2147483647:
            raise ValueError("Expected bounded delta bytes")
        result += struct.pack(">ib", len(payload), kind) + payload
    return 15367, result


REQUEST_OPCODES = frozenset(
    (
        13757,
        13744,
        15194,
        14088,
        14815,
        15429,
        15613,
        15542,
        15627,
        14230,
        15481,
        15511,
        14890,
        15064,
        14239,
        14995,
        12937,
        12575,
        14447,
    )
)


def decode_request(opcode, body):
    from protocol_codec import Reader

    if type(body) is not bytes or opcode not in REQUEST_OPCODES:
        raise ValueError("Unsupported native guild request")
    reader = Reader(body)
    if opcode == 13757:
        fields = dict(
            blazon=reader.number("q"),
            name=reader.text("i"),
            best_rank_name=reader.text("i"),
            worst_rank_name=reader.text("i"),
        )
    elif opcode == 13744:
        fields = dict(guild_id=reader.number("q"), text=reader.text("H"))
    elif opcode == 15194:
        fields = dict(name=reader.text("b"), authorizations=reader.number("q"))
    elif opcode == 14088:
        fields = dict(rank_id=reader.number("q"))
    elif opcode == 14815:
        fields = dict(
            rank_id=reader.number("q"),
            authorizations=reader.number("q"),
            name=reader.text("b"),
        )
    elif opcode == 12937:
        fields = dict(name=reader.text("i"))
    elif opcode == 12575:
        fields = dict(blazon=reader.number("q"))
    elif opcode in (15542, 15064):
        fields = dict(name=reader.text("b"))
    elif opcode == 15627:
        fields = dict(character_id=reader.number("q"))
    elif opcode == 14230:
        fields = dict(character_id=reader.number("q"), rank_id=reader.number("q"))
    elif opcode == 15481:
        fields = {}
    elif opcode in (15511, 14890):
        fields = dict(text=reader.text("i"))
    elif opcode == 14995:
        value = reader.number("B")
        if value not in (0, 1):
            raise ValueError("Invalid native invitation answer")
        fields = dict(accepted=bool(value))
    elif opcode == 14239:
        fields = dict(language_id=reader.number("b"))
    elif opcode in (15613, 14447):
        fields = dict(bonus_id=reader.number("i"))
    else:
        fields = dict(rank_id=reader.number("q"), position=reader.number("h"))
    reader.finish()
    return fields


def replace_local_entity(entity, model=None, moderation_bonus_learning_factor=0.0):
    """Replace qH within verified format22, preserving nation sections.

    Existing wire.minimal_entity documents the prefix as format byte, i32
    nation identity and 27-byte nation synchronization. The trailing nation
    PvP money section is eight bytes. Lengths include the variable qH model.
    """
    if type(entity) is not bytes or len(entity) < 46 or entity[0] != 22:
        raise ValueError("Expected native format22 entity")
    old_size = struct.unpack_from(">H", entity, 32)[0]
    old_end = 34 + old_size + 4
    if len(entity) != old_end + 8:
        raise ValueError("Invalid native format22 guild section length")
    return (
        entity[:32]
        + local_section(model, moderation_bonus_learning_factor)
        + entity[old_end:]
    )


def local_actor_update(character_id, entity):
    """15548 carrier for an already verified format22 local entity."""
    if (
        type(entity) is not bytes
        or not entity
        or entity[0] != 22
        or len(entity) > 65535
    ):
        raise ValueError("Invalid native local actor entity")
    if len(entity) < 46 or len(entity) != 46 + struct.unpack_from(">H", entity, 32)[0]:
        raise ValueError("Invalid native format22 guild section length")
    return 15548, struct.pack(">qH", _integer(character_id, 64), len(entity)) + entity


def decode_storage_request(opcode, body):
    """Shared storage codec; caller must bind an authorized access session.

    GAME_ADD_ITEM is server-only and is deliberately rejected on client input.
    No guild membership or compartment ownership follows from this packet.
    """
    from protocol_codec import Reader

    if type(body) is not bytes or opcode not in (12844, 12004, 14616, 12531):
        raise ValueError("Unsupported shared storage request")
    reader = Reader(body)
    if opcode == 14616:
        fields = dict(
            source_compartment_id=reader.number("i"),
            source_slot=reader.number("b"),
            destination_compartment_id=reader.number("i"),
            destination_slot=reader.number("b"),
        )
    else:
        fields = dict(compartment_id=reader.number("i"))
        if opcode == 12531:
            operation = reader.number("b")
            fields["operation"] = operation
            if operation in (0, 1):
                fields.update(
                    item_id=reader.number("q"),
                    reference=reader.number("i"),
                    quantity=reader.number("h"),
                )
                if operation == 1:
                    fields["additional_item_id"] = reader.number("q")
                fields["slot"] = reader.number("b")
            elif operation == 2:
                fields.update(item_id=reader.number("q"), slot=reader.number("b"))
            elif operation in (3, 4):
                fields["amount"] = reader.number("q")
            else:
                raise ValueError("Unsupported client storage operation")
    reader.finish()
    return fields


def invitation_notice(inviter_name, guild_name):
    """14954 has no invitation token; bind the reply to server session state."""
    inviter = _text(inviter_name, 2147483647)
    guild = _text(guild_name, 2147483647)
    return (
        14954,
        struct.pack(">i", len(inviter))
        + inviter
        + struct.pack(">i", len(guild))
        + guild,
    )


def remote_actor_update(
    character_id,
    guild_id,
    blazon,
    level,
    name,
    *,
    nation_id=0,
    nation_synchro=bytes(27),
):
    """Native format12 updates nation and remote guild identity only.

    The caller supplies the authoritative nation state; neutral defaults match
    this server's current nation policy. No fighter/stat sections are present.
    """
    if type(nation_synchro) is not bytes or len(nation_synchro) != 27:
        raise ValueError("Expected native 27-byte nation synchronization")
    entity = (
        b"\x0c"
        + struct.pack(">i", _integer(nation_id, 32))
        + nation_synchro
        + remote_info(guild_id, blazon, level, name)
    )
    if len(entity) > 65535:
        raise ValueError("Remote guild entity exceeds native actor update length")
    return 15548, struct.pack(">qH", _integer(character_id, 64), len(entity)) + entity


def rank_delta(model, *, modified=False):
    if type(modified) is not bool:
        raise ValueError("Expected boolean delta mode")
    return (8 if modified else 6), serialize_rank(model)


def member_delta(model, *, modified=False):
    if type(modified) is not bool:
        raise ValueError("Expected boolean delta mode")
    return (2 if modified else 0), serialize_member(model)
