"""Native cvB action identities are unique, distinct from a cast request ID.

The original aEV.xX removes by cbc(), including effects executed by Lua
executeAllAction. Reusing the animation's ID for its effects can remove the
animation and execute an effect twice. No running-effect UID is changed here.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import struct
from wakfu_server.paths import DATA_ROOT

NATIVE_ACTION_PACKETS = frozenset(
    int(k)
    for k in protocol_catalog.load(DATA_ROOT / "native-combat-action-packets.json")[
        "packets"
    ]
)

MAX_NATIVE_ACTION_ID = (1 << 31) - 1


class NativeDelivery(tuple):
    """Private prepared delivery; retains logical-to-native correlation."""

    def __new__(cls, packets, *, fight_id, actions):
        value = super().__new__(cls, packets)
        value.fight_id = fight_id
        value.native_actions = tuple(actions)
        return value


def prepare_native_delivery(packets, *, fight_id, previous_id):
    """Validate atomically, then return delivery and last native action ID.

    13510 is a turn number, not an action acknowledgement. 13420 closes a
    client-local FIFO block; neither body is rewritten. A signed32 exhaustion
    rejects before publication rather than wrapping onto pending client IDs.
    """
    if type(previous_id) is not int or not 0 <= previous_id <= MAX_NATIVE_ACTION_ID:
        raise ValueError("Invalid native action counter")
    if type(fight_id) is not int or not -(1 << 31) <= fight_id < (1 << 31):
        raise ValueError("Invalid native action fight")
    if isinstance(packets, NativeDelivery):
        if packets.fight_id != fight_id or any(
            entry["native_action_id"] > previous_id for entry in packets.native_actions
        ):
            raise ValueError("Native delivery belongs to another allocator")
        return packets, previous_id
    result, actions = [], []
    next_id = previous_id
    for opcode, payload in packets:
        if type(opcode) is not int or not isinstance(payload, bytes):
            raise ValueError("Invalid native delivery packet")
        if opcode in NATIVE_ACTION_PACKETS:
            if len(payload) < 12:
                raise ValueError("Truncated native cvB action header")
            owner, request_action, special_id = struct.unpack_from(">iii", payload)
            if owner != fight_id:
                raise ValueError("Native action belongs to another fight")
            if next_id == MAX_NATIVE_ACTION_ID:
                raise ValueError("Native action sequence exhausted")
            next_id += 1
            payload = payload[:4] + struct.pack(">i", next_id) + payload[8:]
            actions.append(
                dict(
                    opcode=opcode,
                    request_action_id=request_action,
                    native_action_id=next_id,
                    special_id=special_id,
                )
            )
        result.append((opcode, payload))
    return NativeDelivery(result, fight_id=fight_id, actions=actions), next_id


def native_delivery_boundary(operation):
    """Prepare a whole runtime boundary once, including nested turn packets.

    Pending next-turn packets stay unnumbered until acknowledge_turn delivers
    them. Allocation failure cannot commit gameplay mutations or an ACK clear.
    """
    from functools import wraps
    from copy import deepcopy
    from .combat_area_boundary import adopt_runtime

    @wraps(operation)
    def apply(runtime, *args, **kwargs):
        if getattr(runtime, "_native_delivery_depth", 0):
            return operation(runtime, *args, **kwargs)
        candidate = deepcopy(runtime)
        candidate._native_delivery_depth = 1
        # This boundary already supplies the same preview/adopt transaction.
        candidate._area_atomic_depth = True
        packets = operation(candidate, *args, **kwargs)
        delivery = candidate.prepare_delivery(packets) if packets else packets
        candidate.__dict__.pop("_native_delivery_depth", None)
        adopt_runtime(runtime, candidate)
        return delivery

    return apply
