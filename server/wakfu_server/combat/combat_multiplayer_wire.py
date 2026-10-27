"""Native join/external envelopes; caller supplies owned nested actor/topology data."""
import struct
from protocol_codec import Reader
from .combat_wire import _blob, _read_blob


# Local server namespace reserved for synthetic external-fight map markers.
# Native `fbm` accepts a signed 64-bit actor UID; this range is disjoint from
# this server's positive character/NPC IDs and negative monster IDs.
EXTERNAL_MARKER_UID_BASE = 1 << 51


def external_marker_actor_id(fight_id):
    """Derive a stable, collision-separated marker UID from the fight ID.

    This is a Wakemu local allocation policy, not a claim about Ankama's ID
    convention. Fight IDs are positive signed i32 values, so the mapping is
    injective and remains below the exact-integer ceiling of the client's
    Lua number bridge, as well as the signed i64 ceiling.
    """
    if type(fight_id) is not int or not 0 < fight_id < 2**31:
        raise ValueError("Invalid fight ID for external marker")
    actor_id = EXTERNAL_MARKER_UID_BASE + fight_id
    if not 0 < actor_id <= 2**53:
        raise ValueError("External marker actor ID exceeds exact client integer")
    return actor_id


def decode_join(body):
    if len(body) != 9:
        raise ValueError("Invalid13241 join request length")
    actor_id, locked = struct.unpack(">qB", body)
    if actor_id == 0 or locked not in (0, 1):
        raise ValueError("Invalid13241 target/autoLock")
    return dict(target_id=actor_id, auto_lock=bool(locked))


def added(fight_id, actor_id, *, actor_type, team, stats, effects, controller=None):
    if (
        type(fight_id) is not int
        or not 0 < fight_id < 2**31
        or type(actor_id) is not int
        or actor_id == 0
    ):
        raise ValueError("Invalid joined actor identity")
    # cvg.myR carries the original actor discriminator, including companion5.
    # ckT resolves the already registered actor by UID; this is no NPC admission.
    if actor_type not in (0, 1, 5) or team not in (0, 1):
        raise ValueError("Invalid native actor kind/team")
    out = (
        struct.pack(">iqbb", fight_id, actor_id, actor_type, team)
        + _blob(stats, "h")
        + _blob(effects, "i")
    )
    if controller is None:
        out += b"\x00"
    else:
        # cvg/SQ: SR type code, long controller ID, int opaque native parameter.
        kind, owner, parameter = controller
        if not 0 <= kind <= 127 or owner == 0:
            raise ValueError("Invalid native controller")
        out += b"\x01" + struct.pack(">bqi", kind, owner, parameter)
    return 13091, out


def decode_added(body):
    r = Reader(body)
    value = dict(
        fight_id=r.number("i"),
        actor_id=r.number("q"),
        actor_type=r.number("b"),
        team=r.number("b"),
        stats=_read_blob(r, "h"),
        effects=_read_blob(r, "i"),
    )
    present = r.number("B")
    if present not in (0, 1):
        raise ValueError("Invalid controller flag")
    value["controller"] = (
        tuple(r.number(t) for t in ("b", "q", "i")) if present else None
    )
    r.finish()
    return value


def removed(fight_id, actor_id, *, action_id, action_context):
    """Encode cvM/12347 with an explicitly owned cvB header.

    cuQ.fj reads fight_id; cvB.fl reads cbc()/eId(); cvM then reads OO().
    Native fresh cvB constructor values are 0/-1, but callers must supply
    their actual context. This removes external membership, not world actors.
    """
    if (
        type(fight_id) is not int
        or not 0 < fight_id < 2**31
        or type(actor_id) is not int
        or actor_id == 0
        or not -(2**63) <= actor_id < 2**63
        or any(
            type(value) is not int or not -(2**31) <= value < 2**31
            for value in (action_id, action_context)
        )
    ):
        raise ValueError("Invalid native external member removal")
    return 12347, struct.pack(">iiiq", fight_id, action_id, action_context, actor_id)


def decode_removed(body):
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Invalid12347 external member removal length")
    fight_id, action_id, action_context, actor_id = struct.unpack(">iiiq", body)
    removed(fight_id, actor_id, action_id=action_id, action_context=action_context)
    return dict(
        fight_id=fight_id,
        action_id=action_id,
        action_context=action_context,
        actor_id=actor_id,
    )


def external(value):
    """cuY13753 exact fields; no guesses about neutral myo/myp/jqi/myu semantics.

    topology is fct/QI, not a participant bootstrap myD of arbitrary shape.
    myr is byte-count q-list; teams is i16-count (q ID,b team); mys b-count(h,h).
    """
    if value["phase_code"] not in range(6):
        raise ValueError("Unknown native external phase")
    lists = (value["myr"], value["teams"], value["mys"])
    if len(lists[0]) > 127 or len(lists[1]) > 32767 or len(lists[2]) > 127:
        raise ValueError("External fight list too long")
    if (
        len(lists[0]) != 2
        or len(set(lists[0])) != 2
        or not set(lists[0]) <= {actor for actor, team in lists[1]}
    ):
        raise ValueError("External fight requires two existing team leaders")
    flags = value["flags"]
    if len(flags) != 4 or any(type(flag) is not bool for flag in flags):
        raise ValueError("Invalid external native flags")
    out = struct.pack(
        ">ibqqhq",
        value["fight_id"],
        value["kind"],
        value["myo"],
        value["myp"],
        value["jqi"],
        value["myu"],
    )
    out += struct.pack(">b", len(lists[0])) + b"".join(
        struct.pack(">q", n) for n in lists[0]
    )
    out += struct.pack(">h", len(lists[1])) + b"".join(
        struct.pack(">qb", *entry) for entry in lists[1]
    )
    out += struct.pack(">b", value["phase_code"]) + bytes(flags)
    out += struct.pack(">b", len(lists[2])) + b"".join(
        struct.pack(">hh", *pair) for pair in lists[2]
    )
    if not isinstance(value["topology"], bytes):
        raise ValueError("External topology must be own bytes")
    out += value["topology"]
    return 13753, out


def decode_external(body):
    r = Reader(body)
    v = {
        key: r.number(t)
        for key, t in zip(
            ("fight_id", "kind", "myo", "myp", "jqi", "myu"),
            ("i", "b", "q", "q", "h", "q"),
        )
    }

    def count(fmt):
        n = r.number(fmt)
        if n < 0:
            raise ValueError("Negative external fight list")
        return n

    v["myr"] = [r.number("q") for _ in range(count("b"))]
    v["teams"] = [tuple(r.number(t) for t in ("q", "b")) for _ in range(count("h"))]
    v["phase_code"] = r.number("b")
    flags = [r.number("B") for _ in range(4)]
    if any(n not in (0, 1) for n in flags):
        raise ValueError("Invalid external fight flags")
    v["flags"] = [bool(n) for n in flags]
    v["mys"] = [tuple(r.number("h") for _ in range(2)) for _ in range(count("b"))]
    v["topology"] = r.take(len(body) - r.pos)
    r.finish()
    return v
