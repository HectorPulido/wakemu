"""Verified native raw effect2000 snapshot codec, staged for activation.

sa.Ym/sd.TM contains a legacy raw runner snapshot. bjo.doM consumes it during
initial reconstruction; bjN.zm ignores it on ordinary live section refresh.
This codec alone therefore does not provide dynamic actor bonus publication.
"""
import struct


def snapshot_section(actor_id, bonuses, *, first_uid):
    """Encode owned per-profession bonuses without overwriting live effects.

    Callers must merge this with any other owned running effects before
    publishing a complete snapshot. UIDs are allocated by the caller.
    """
    from wakfu_server.wire import proto_field

    if (
        type(actor_id) is not int
        or not 0 < actor_id < (1 << 63)
        or type(first_uid) is not int
        or not 0 < first_uid < (1 << 63)
        or not isinstance(bonuses, dict)
        or len(bonuses) > 1000
    ):
        raise ValueError("Invalid native planting effect ownership")
    records = []
    for index, (profession, amount) in enumerate(sorted(bonuses.items())):
        if (
            type(profession) is not int
            or not 0 < profession < (1 << 31)
            or type(amount) is not int
            or not -(1 << 31) <= amount < (1 << 31)
            or first_uid + index >= (1 << 63)
        ):
            raise ValueError("Invalid native planting effect bonus")
        uid = first_uid + index
        # Installed generic effect72217 is native class2000, mode0/permanent.
        # A valid generic definition retains the public application lifecycle.
        fields = (
            (1, uid),
            (2, uid),
            (3, 72217),
            (4, amount),
            (6, actor_id),
            (7, actor_id),
        )
        payload = b"".join(
            proto_field(field << 3, value if value >= 0 else value + (1 << 64))
            for field, value in fields
        )
        # eXx.f reads ij.Mg, whose protobuf field is19, into profession kdm.
        payload += proto_field((8 << 3) | 2, proto_field(19 << 3, profession))
        records.append(
            struct.pack(">ih", 2000, len(payload)) + payload + struct.pack(">i", 0)
        )
    raw = struct.pack(">h", len(records)) + b"".join(records)
    if len(raw) > 65535:
        raise ValueError("Native planting effect snapshot exceeds ushort length")
    return b"\x01" + struct.pack(">H", len(raw)) + raw + b"\x00"


def delta_packet(actor_id, profession_id, delta, *, uid, action_id):
    """Native world12613 candidate: retained evaluated effect2000 application.

    The global cjj handler routes12613 without requiring a fight; cjK uses
    bcz/bio world context for fightID=-1. Incremental application must still be
    accepted graphically before callers activate the policy in production.
    """
    if type(action_id) is not int or not 0 < action_id < (1 << 31):
        raise ValueError("Invalid native planting action identity")
    section = snapshot_section(actor_id, {profession_id: delta}, first_uid=uid)
    raw = section[3:-1]
    # One raw snapshot record: short count, int class, short length, protobuf.
    length = struct.unpack_from(">h", raw, 6)[0]
    payload = raw[8 : 8 + length]
    return (
        12613,
        struct.pack(">iiiBih", -1, action_id, -1, 0, 2000, len(payload)) + payload,
    )


def publication(store, character, previous_bonuses, *, allocate_uid, allocate_action):
    """Prepare deltas; commit the returned marker only after successful sends.

    The caller resets the marker to{} whenever the native actor is recreated,
    and owns its connection/actor-generation fence. A socket-level resend is
    not a new application. Other running effects are preserved by this path.
    """
    from wakfu_server.planting_level_policy import account_bonuses

    if not isinstance(previous_bonuses, dict):
        raise ValueError("Missing native planting publication baseline")
    with store.connection() as db:
        current = account_bonuses(db, character["account_id"])
    packets = []
    for profession in sorted(set(current) | set(previous_bonuses)):
        before, after = previous_bonuses.get(profession, 0), current.get(profession, 0)
        if type(before) is not int:
            raise ValueError("Invalid previous native planting bonus")
        if before != after:
            packets.append(
                delta_packet(
                    character["id"],
                    profession,
                    after - before,
                    uid=allocate_uid(),
                    action_id=allocate_action(),
                )
            )
    if packets:
        # Installed cjj/cjK queues12613; cjq/13420 flushes the world (-1) queue.
        # The marker may advance only after this final frame is delivered too.
        packets.append((13420, struct.pack(">i", -1)))
    return dict(packets=packets, bonuses=current)
