"""Native eZV/eZU remote running-effect envelope, independent of class."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class RemoteRunningEffect:
    effect_class: int
    payload: bytes
    remaining_milliseconds: int = 0

    def __post_init__(self):
        if type(self.effect_class) is not int or not -(1 << 31) <= self.effect_class < (
            1 << 31
        ):
            raise ValueError("Invalid native remote effect class")
        if type(self.payload) is not bytes or len(self.payload) > 32767:
            raise ValueError("Invalid native remote effect payload")
        if type(self.remaining_milliseconds) is not int or not -(
            1 << 31
        ) <= self.remaining_milliseconds < (1 << 31):
            raise ValueError("Invalid native remote effect remaining timer")


def encode_remote_effects(ordered_effects):
    """Encode an attested native population; callers preserve state-first order.

    This codec does not decide inclusion, rebuild running effects, or replay
    family 649 independently of its owning state. Those are producer facts.
    """
    records = tuple(ordered_effects)
    if len(records) > 32767:
        raise ValueError("Native remote effect population exceeds signed short")
    if any(not isinstance(record, RemoteRunningEffect) for record in records):
        raise ValueError("Missing typed native remote running effect")
    body = struct.pack(">h", len(records)) + b"".join(
        struct.pack(">ih", record.effect_class, len(record.payload))
        + record.payload
        + struct.pack(">i", record.remaining_milliseconds)
        for record in records
    )
    # eZU returns an empty population when its serialized size exceeds 50,000.
    return body if len(body) <= 50000 else bytes(2)


def decode_remote_effects(body):
    """Inspect the native envelope without instantiating or executing effects."""
    if type(body) is not bytes or len(body) < 2:
        raise ValueError("Truncated native remote effect population")
    count = struct.unpack_from(">h", body)[0]
    if count < 0:
        raise ValueError("Negative native remote effect population")
    offset, records = 2, []
    for _ in range(count):
        if offset + 6 > len(body):
            raise ValueError("Truncated native remote effect header")
        effect_class, size = struct.unpack_from(">ih", body, offset)
        offset += 6
        if size < 0 or offset + size + 4 > len(body):
            raise ValueError("Truncated native remote effect payload")
        payload = body[offset : offset + size]
        offset += size
        remaining = struct.unpack_from(">i", body, offset)[0]
        offset += 4
        records.append(RemoteRunningEffect(effect_class, payload, remaining))
    if offset != len(body):
        raise ValueError("Trailing native remote effect bytes")
    return tuple(records)


def _time_data(payload):
    from .combat_effect_removal import _read_varint

    offset, timing = 0, None
    while offset < len(payload):
        tag, offset = _read_varint(payload, offset)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            _, offset = _read_varint(payload, offset)
        elif wire == 2:
            size, offset = _read_varint(payload, offset)
            if offset + size > len(payload):
                raise ValueError("Truncated native remote effect message")
            if field == 11:
                if timing is not None:
                    raise ValueError("Duplicate native remote effect timing")
                timing = payload[offset : offset + size]
            offset += size
        elif wire in (1, 5):
            offset += 8 if wire == 1 else 4
        else:
            raise ValueError("Unsupported native remote effect protobuf")
        if offset > len(payload):
            raise ValueError("Truncated native remote effect protobuf")
    return timing


def active_actor_effects(fight, actor_id, *, now_milliseconds=None):
    """Complete live fSp snapshot for a registered actor's current Qf manager.

    eZU.fSp includes every retained runner, with state carriers first. Native
    HashMap keys use Object identity hashes, so internal partition order has no
    UID contract; retain this server's actual Qf encounter order. This server
    deliberately uses the complete fSp contract for active bootstrap, rather
    than guessing the unavailable original server's choice of exposure mode.
    """
    if fight.phase != "active" or actor_id not in fight.actors:
        raise ValueError("Native active effect snapshot requires a live actor")
    return (
        _live_actor_effects(fight, actor_id)
        if now_milliseconds is None
        else _live_actor_effects(fight, actor_id, now_milliseconds=now_milliseconds)
    )


def initial_npc_actor_effects(fight, actor_id, *, now_milliseconds=None):
    """Exact constructor Qf for placement; no second cle replay on the client.

    Native big.a -> dq -> eZV.a clears the old world manager before restoring
    myF. Empty effects would erase the descriptor's retained initial states.
    """
    from .combat_actor import actor_effects

    if fight.phase != "placement" or actor_id not in fight.actors:
        raise ValueError("Native initial effect snapshot requires placement actor")
    from wakfu_server.maps.dungeon_combat_scaling import validates_constructor_receipt

    scaling_constructor = validates_constructor_receipt(fight, actor_id)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor_id)
    if receipt is None:
        if scaling_constructor:
            return (
                _live_actor_effects(fight, actor_id)
                if now_milliseconds is None
                else _live_actor_effects(
                    fight, actor_id, now_milliseconds=now_milliseconds
                )
            )
        return actor_effects()
    actor = fight.actors[actor_id]
    if actor.controlled or receipt.get("initialized") is not True:
        raise ValueError("Missing ordinary native constructor proof")
    from .combat_summon_initial_states import initial_state_plan
    from dataclasses import asdict

    plan = initial_state_plan(
        receipt.get("raw_triples"), receipt.get("descriptor_level")
    )
    expected = [dict(state_id=p.state_id, level=p.level, applied=True) for p in plan]
    if (
        not plan
        or receipt.get("descriptor_level") != actor.effective_level
        or receipt.get("resolved_states") != [asdict(p) for p in plan]
        or receipt.get("applications") != expected
    ):
        raise ValueError("Incomplete ordinary native initial-state applications")
    return (
        _live_actor_effects(fight, actor_id)
        if now_milliseconds is None
        else _live_actor_effects(fight, actor_id, now_milliseconds=now_milliseconds)
    )


def _live_actor_effects(fight, actor_id, *, now_milliseconds=None):
    from .combat_pending_state import pending_state_uids
    from .combat_retained_runtime import native_retained_condition_effects
    from .combat_effect_removal import _identity_fields

    if pending_state_uids(fight):
        raise ValueError("Native active snapshot contains pending state registration")
    # This validates the complete population, exact ownership, and stored order
    # against all current state/stat/group/area payloads without mutating Fight.
    native_retained_condition_effects(fight, actor_id)
    carriers, ordinary = [], []
    for uid in fight.native_retained_order:
        entry = fight.native_retained_records[uid]
        if entry["manager_id"] != actor_id:
            continue
        sources = []
        if uid in fight.state_wire_payloads:
            sources.append(fight.state_wire_payloads[uid])
        for name in (
            "owned_stat_effects",
            "native_owned_group_effects",
            "native_owned_area_effects",
            "native_owned_spatial_effects",
        ):
            row = getattr(fight, name, {}).get(uid)
            if row is not None:
                sources.append(row.get("payload"))
        if len(sources) != 1 or type(sources[0]) is not str:
            raise ValueError("Missing unique live native remote effect payload")
        payload = bytes.fromhex(sources[0])
        fields = _identity_fields(payload, integer_fields=(1, 3, 9, 10))
        if fields.get(1) != uid:
            raise ValueError("Native remote effect payload UID differs from ownership")
        generic = fields.get(3)
        if generic == (1 << 64) - 1:
            generic = -1
        if generic != entry["generic_effect"]:
            raise ValueError("Native remote effect definition differs from ownership")
        present = entry.get("container_present")
        if present is True:
            identity = fields.get(10)
            if identity is not None and identity >= 1 << 63:
                identity -= 1 << 64
            if (fields.get(9), identity) != (
                entry.get("container_type"),
                entry.get("container_id"),
            ):
                raise ValueError(
                    "Native remote effect container differs from ownership "
                    f"(actor={actor_id}, uid={uid}, family={entry['effect_class']}, "
                    f"wire={(fields.get(9), identity)}, "
                    f"owned={(entry.get('container_type'), entry.get('container_id'))})"
                )
        elif present is not False or 9 in fields or 10 in fields:
            raise ValueError("Unverified native remote effect container absence")
        timing = _time_data(payload)
        remaining = 0
        if timing is not None:
            value = _identity_fields(timing, integer_fields=(4,)).get(4, 0)
            if value >= 1 << 63:
                value -= 1 << 64
            if value > 0:
                if entry["effect_class"] == 310:
                    from .combat_remote_state_clock import state_remaining_milliseconds

                    remaining = state_remaining_milliseconds(
                        fight, actor_id, uid, value, now_milliseconds
                    )
                else:
                    deadline = getattr(
                        fight, "native_remote_effect_wall_deadlines", {}
                    ).get(uid)
                    if type(deadline) is not int or type(now_milliseconds) is not int:
                        raise ValueError(
                            "Missing native remote effect wall timer authority"
                        )
                    remaining = max(0, deadline - now_milliseconds)
                    remaining = ((remaining + (1 << 31)) % (1 << 32)) - (1 << 31)
        record = RemoteRunningEffect(entry["effect_class"], payload, remaining)
        (carriers if entry["effect_class"] == 310 else ordinary).append(record)
    return encode_remote_effects((*carriers, *ordinary))
