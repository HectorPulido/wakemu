"""Stable account-chest tabs over the existing durable global slot space.

The provisioned count is server policy, not an asserted official shop maximum.
The signed-smallint storage limit bounds total capacity; growth never shrinks it.
"""
import os
import uuid

TAB_CAPACITY = 100
MAX_TABS = 32767 // TAB_CAPACITY


def provisioned_capacity():
    value = os.environ.get("WAKFU_HAVEN_CHEST_COMPARTMENTS", "20")
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid provisioned haven chest compartment count") from error
    if not 1 <= count <= MAX_TABS:
        raise ValueError("Provisioned haven chest compartments exceed storage width")
    return count * TAB_CAPACITY


def compartments(chest):
    capacity = chest["capacity"]
    width = chest.get("compartment_size", capacity)
    if (
        type(capacity) is not int
        or not 1 <= capacity <= 32767
        or type(width) is not int
        or not 1 <= width <= 32767
    ):
        raise ValueError("Invalid chest compartment capacity")
    result = []
    for index, offset in enumerate(range(0, capacity, width)):
        identity = (
            chest["id"]
            if index == 0
            else str(uuid.uuid5(uuid.UUID(chest["id"]), f"compartment:{index}"))
        )
        result.append(
            dict(
                id=identity,
                index=index,
                offset=offset,
                capacity=min(width, capacity - offset),
            )
        )
    return result


def resolve(chest, identity):
    for entry in compartments(chest):
        if entry["id"] == identity:
            return entry
    raise ValueError("Foreign chest compartment")
