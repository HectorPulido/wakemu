"""Strict native codecs for consensual DUEL invitations and answers."""
import struct


def decode_challenge(body):
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Invalid native duel challenge length")
    target, x, y, z, auto_lock, mode = struct.unpack(">qii hBB", body)
    if target <= 0 or auto_lock not in (0, 1) or mode != 1:
        raise ValueError("Unsupported native duel challenge")
    return {
        "target_character_id": target,
        "claimed_position": (x, y, z),
        "auto_lock": bool(auto_lock),
        "mode": mode,
    }


def invite(challenger_character_id, mode=1):
    if (
        type(challenger_character_id) is not int
        or not 0 < challenger_character_id < 2**63
        or type(mode) is not int
        or mode != 1
    ):
        raise ValueError("Invalid native duel invitation")
    return 13179, struct.pack(">qB", challenger_character_id, mode)


def decode_answer(body):
    if not isinstance(body, bytes) or len(body) != 10:
        raise ValueError("Invalid native duel answer length")
    challenger, accepted, auto_lock = struct.unpack(">qBB", body)
    if challenger <= 0 or accepted not in (0, 1) or auto_lock not in (0, 1):
        raise ValueError("Invalid native duel answer")
    return {
        "challenger_character_id": challenger,
        "accepted": bool(accepted),
        "auto_lock": bool(auto_lock),
    }


def cancellation(reason):
    if type(reason) is not int or reason not in range(8):
        raise ValueError("Invalid native duel cancellation reason")
    return 12708, struct.pack(">B", reason)
