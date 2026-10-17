"""Bounded native FIGHTER_DATAS projection of the current owned PC producer."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import struct

from protocol_codec import Reader


def public_player_fighter_stats(stats, *, actor_id, fight_id):
    """Drop only native XP; preserve all eleven native fighter-data groups.

    Accept only the current ordinary player producer's complete format3.
    NPC eHj format2 and character-copy/summon formats need their own paths.
    """
    if (
        type(stats) is not bytes
        or type(actor_id) is not int
        or actor_id <= 0
        or type(fight_id) is not int
        or not 0 < fight_id < 2**31
    ):
        raise ValueError("Invalid public player fighter source")
    try:
        r = Reader(stats)
        if r.number("B") != 3:
            raise ValueError("Expected native player FIGHTER_DATAS_WITH_XP")
        r.take(8)  # eHe XP; omitted by the native format2 group definition.
        r.take(20)  # Native position.
        if r.number("i") != fight_id:
            raise ValueError("Mismatched public fighter fight identity")
        r.take(6)  # Remaining native fight properties.
        for _ in range(r.number("H")):
            r.take(17)  # Native characteristic identity and four signed ints.
        r.take(1)  # Native AI control flag.
        r.take(2)  # Breed.
        if r.number("B") != 0:
            raise ValueError("Unmodeled native fighter cosmetic sections")
        for _ in range(r.number("H")):
            r.take(17)
        identity, linked, account, linked_account, level = struct.unpack(
            ">qBqBh", r.take(20)
        )
        if (
            identity != actor_id
            or linked != 0
            or account <= 0
            or linked_account != 0
            or not 1 <= level <= MAX_CHARACTER_LEVEL
            or r.pos != len(stats)
        ):
            raise ValueError("Mismatched public fighter actor identity or boundary")
    except (struct.error, IndexError) as error:
        raise ValueError("Truncated public fighter source") from error
    return b"\x02" + stats[9:]
