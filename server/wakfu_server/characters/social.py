"""Account initialization without social data inherited from a capture."""
import struct
import zlib
from protocol_codec import Reader
from .nation_state import nation_id

ACCOUNT_DEFAULTS = {
    7: bytes(9),
    8: bytes(4),
    9: bytes(4),
    10: bytes(4),
    11: bytes(4),
    # fzy's native constructor keeps the two default transport categories.
    12: bytes.fromhex("000000080a0208020a020801"),
    13: bytes(4),
    14: bytes.fromhex("0000000a120208001a0418002000"),
    15: bytes(4),
    17: bytes(8),
    18: bytes.fromhex("000000080000000000000000000000020000000000080000000000000000"),
}


def company(account_id, character):
    # eSO.qD uses native rank ranges beginning at XP=1. XP=0 falls through
    # to the highest rank and produces negative progress in the client.
    return struct.pack(
        ">qqiqIiB",
        account_id,
        character["id"] if character else 0,
        nation_id(character),
        (character.get("guild_native") or {}).get("guildId", 0) if character else 0,
        0,
        1,
        int(character is not None),
    )


def adapt(opcode, body, account_id, character=None, owned=None, cosmetic_record=None):
    if opcode == 22731:
        # cEs/aZq -> eSH.dS: constructor sentinel -1 disables the weekly
        # free companion, independently of the account-owned collection.
        if len(body) != 2:
            raise ValueError("Invalid free companion selector")
        return struct.pack(">h", -1)
    if opcode == 14303:
        # cDs.dp inflates a sequence of market-average-price records.
        # An empty inflated sequence is a valid empty authoritative map.
        return zlib.compress(b"")
    if opcode == 22790:
        # aZk.dS reads a signed byte count. aZk.a first calls eSt.qw(account)
        # to remove the preceding companion collection, even for count zero.
        return b"\x00"
    if opcode == 15984:
        # cyq regional world records. Format17 is the complete public nation
        # initialization, including government names, elections and mandates.
        # A native frk with the client aHd factory serializes to ID +49 zeros.
        r = Reader(body)
        result = bytearray()
        changed = False
        while r.pos < len(body):
            region = r.number("i")
            payload = r.take(r.number("I"))
            if payload and payload[0] == 17:
                if (
                    len(payload) < 5
                    or struct.unpack_from(">i", payload, 1)[0] != region
                ):
                    raise ValueError("Regional nation identity mismatch")
                payload = struct.pack(">Bi", 17, region) + bytes(49)
                changed = True
            result.extend(struct.pack(">iI", region, len(payload)) + payload)
        return bytes(result) if changed else None
    if opcode == 630:
        # NT.dp -> fa/ProtoFriendListsForClient: two optional repeated lists.
        # An empty initialized protobuf represents zero friends and zero ignored.
        return b""
    if opcode == 1029:
        # cDd: i32 section count; the captured initialization is already empty.
        if body != bytes(4):
            raise ValueError("Unexpected captured account-information sections")
        return bytes(4)
    if opcode == 13873 and len(body) >= 8 and struct.unpack(">II", body[:8]) == (1, 1):
        # eDS.COMPANY/eSJ is a fixed record, not a length-prefixed protobuf:
        # account, chief character, nation, guild, name, XP, activated.
        r = Reader(body)
        r.take(8)
        r.take(28)
        r.take(r.number("I"))
        r.take(5)
        r.finish()
        return struct.pack(">II", 1, 1) + company(account_id, character)
    if opcode == 13873 and len(body) >= 8:
        count, kind = struct.unpack(">II", body[:8])
        cosmetic_components = {}
        cosmetic_record = (
            cosmetic_record
            if cosmetic_record is not None
            else (None if character is None else character.get("owned_cosmetics"))
        )
        if cosmetic_record is not None:
            from .cosmetics import OwnedCosmetics

            cosmetics = OwnedCosmetics.from_record(
                cosmetic_record, account_id=account_id
            )
            cosmetic_components = {
                8: cosmetics.inventory_component(),
                9: cosmetics.preset_component(),
            }
        if count == 1 and kind in ACCOUNT_DEFAULTS:
            r = Reader(body)
            r.take(8)
            if kind == 17:
                r.take(8)
            elif kind == 7:
                r.take(9)
            elif kind == 18:
                for _ in range(3):
                    r.take(r.number("I"))
            else:
                r.take(r.number("I"))
            r.finish()
            return struct.pack(">II", 1, kind) + cosmetic_components.get(
                kind, ACCOUNT_DEFAULTS[kind]
            )
        if (count, kind) == (2, 8):
            # The login also combines cosmetics and presets in one packet.
            r = Reader(body)
            r.take(8)
            r.take(r.number("I"))
            if r.number("I") != 9:
                raise ValueError("Unexpected cosmetic preset tail")
            r.take(r.number("I"))
            r.finish()
            return (
                struct.pack(">II", 2, 8)
                + cosmetic_components.get(8, ACCOUNT_DEFAULTS[8])
                + struct.pack(">I", 9)
                + cosmetic_components.get(9, ACCOUNT_DEFAULTS[9])
            )
        if (count, kind) == (2, 0):
            # Account roster followed by COMPANY; replacing only the first
            # section left the captured company progress in the second one.
            r = Reader(body)
            r.take(8)
            r.take(r.number("I") * 10)
            if r.number("I") != 1:
                raise ValueError("Unexpected account roster tail")
            r.take(28)
            r.take(r.number("I"))
            r.take(5)
            r.finish()
            own = owned if owned is not None else [character] if character else []
            roster = struct.pack(">III", 2, 0, len(own)) + b"".join(
                struct.pack(">qh", entry["id"], entry["level"]) for entry in own
            )
            return roster + struct.pack(">I", 1) + company(account_id, character)
    return None
