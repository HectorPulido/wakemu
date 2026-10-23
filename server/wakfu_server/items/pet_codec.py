"""Original companion rA and shared ProtoPet, with valid native model zero."""
import struct

from .mount_codec import _field, _integer


def companion_section(state):
    """rw first optional record: present rA followed by six big-endian int32."""
    if state is None:
        return b"\x00"
    fields = (
        "definition_id",
        "color_item_ref",
        "equipped_item_ref",
        "sleep_item_ref",
        "health",
        "reskin_item_ref",
    )
    return b"\x01" + struct.pack(
        ">6i", *(_integer(state[key], 0, 2**31 - 1) for key in fields)
    )


def item_pet(state):
    """Original ProtoItem.field50/ProtoPet fields; model0 is a real companion."""
    if type(state["name"]) is not str:
        raise ValueError("Invalid companion pet name")
    values = {2: state["name"].encode("utf-8")}
    for number, key in (
        (1, "definition_id"),
        (3, "color_item_ref"),
        (4, "equipped_item_ref"),
        (5, "health"),
        (6, "xp"),
        (9, "sleep_item_ref"),
    ):
        values[number] = _integer(state[key], 0, 2**31 - 1)
    for number, key in (
        (7, "last_meal_date"),
        (8, "last_hungry_date"),
        (10, "sleep_date"),
    ):
        values[number] = _integer(state[key], -(2**63), 2**63 - 1)
    daily_limit = state.get("daily_limit_enabled", True)
    if type(daily_limit) is not bool:
        raise ValueError("Invalid pet feeding daily-limit policy")
    if not daily_limit:
        values[7] = 0
    return _field(
        50, b"".join(_field(number, values[number]) for number in sorted(values))
    )


def binary_option(state):
    """Original vv/wS legacy item option, verified independently of ProtoPet."""
    if state is None:
        return b"\x00"
    item_pet(state)
    name = state["name"].encode("utf-8")
    if len(name) > 65535:
        raise ValueError("Pet legacy name exceeds unsigned-short capacity")
    last_meal = state["last_meal_date"] if state.get("daily_limit_enabled", True) else 0
    return (
        b"\x01"
        + struct.pack(">iH", state["definition_id"], len(name))
        + name
        + struct.pack(
            ">iiiiqqiq",
            state["color_item_ref"],
            state["equipped_item_ref"],
            state["health"],
            state["xp"],
            last_meal,
            state["last_hungry_date"],
            state["sleep_item_ref"],
            state["sleep_date"],
        )
    )
