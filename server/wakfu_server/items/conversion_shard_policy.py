"""Explicit Wakemu lossless conversion policy using native socket validators.

This validates destination acceptance, not an upstream inheritance algorithm.
Unknown extensions are refused without modifying the original carrier.
"""
from wakfu_server.wire import proto_fields


def validate_target(db, reference, state):
    from .inventory_shards import validate
    from .shard_identification import _catalog
    from .socket_enchantment import _slots, _bonus_catalog, _native_pattern_matches
    from .sublimation_eligibility import pattern, special_target

    validate(state)
    template = _catalog().get(reference)
    if template is None:
        raise ValueError("Conversion destination has no native socket contract")
    fields = list(proto_fields(state))
    # Additional gems and unknown extensions have no qualified transfer rule.
    if any(tag not in (10, 24, 32, 72) for tag, _ in fields):
        raise ValueError("Unqualified conversion socket extension")
    for tag in (24, 32, 72):
        if sum(key == tag for key, _ in fields) > 1:
            raise ValueError("Ambiguous conversion socket scalar")
    for tag, value in fields:
        if tag == 10:
            nested = list(proto_fields(value))
            tags = [key for key, _ in nested]
            if (
                any(key not in (80, 88, 96, 112) for key in tags)
                or len(tags) != len(set(tags))
                or not {80, 88, 96} <= set(tags)
                or any(not 0 <= scalar < (1 << 31) for _, scalar in nested)
            ):
                raise ValueError("Unqualified conversion socket slot")
    rows = _slots(state)
    if not template["min_sockets"] <= len(rows) <= template["max_sockets"]:
        raise ValueError("Conversion sockets exceed the native destination bounds")
    catalog = _bonus_catalog()
    for row in rows:
        if (
            row["color"] not in (1, 2, 3, 4)
            or row["reference"] < 0
            or row["level"] < 0
            or ((row["reference"] == 0) != (row["level"] == 0))
        ):
            raise ValueError("Invalid conversion socket contents")
        if row["reference"]:
            bonus = catalog.get(row["reference"])
            if (
                bonus is None
                or not bonus["selectable"]
                or (row["color"] != 4 and bonus["color"] != row["color"])
                or row["level"]
                not in {
                    amount
                    for amount, minimum in zip(bonus["costs"], bonus["minimum_levels"])
                    if minimum <= template["item_level"]
                }
            ):
                raise ValueError(
                    "Conversion socket bonus violates the native destination contract"
                )
    scalars = {tag: value for tag, value in fields if tag != 10}
    if not 0 <= scalars.get(72, 0) <= 255:
        raise ValueError("Invalid conversion socket charges")
    for tag in (24, 32):
        attached = scalars.get(tag, 0)
        if not 0 <= attached < (1 << 31):
            raise ValueError("Invalid conversion sublimation reference")
        if not attached:
            continue
        attachment = pattern(db, attached)
        if attachment["tag"] != tag:
            raise ValueError("Conversion sublimation slot differs from its native kind")
        if tag == 24:
            if not _native_pattern_matches(rows, attachment["colors"]):
                raise ValueError("Conversion sublimation colors do not match")
        else:
            special_target(db, reference, kind=attachment["kind"])
    return state
