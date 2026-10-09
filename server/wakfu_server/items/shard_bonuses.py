"""Native passive bonuses from installed shard slots.

The installed client `fpN.y` evaluates a shard's effect at the effective level
selected by `fpG.WA(slot_level)`, then doubles its value when the shard's
equipment-family set contains the equipped item's family. This module consumes
those offline-exported native values; it does not infer installation or charge
rules.
"""
from wakfu_server import native_catalog as protocol_catalog
import json

from .paths import DATA_ROOT
from .inventory_shards import validate
from .shard_identification import _catalog as _socket_templates
from wakfu_server.wire import proto_fields


_DOCUMENT = protocol_catalog.load(DATA_ROOT / "item-shard-effects.json")
_ROWS = _DOCUMENT.get("items")
if (
    _DOCUMENT.get("source", {}).get("mechanism")
    != "fpN.y(fnO), eVn.a(level), fpG.WA(slotLevel), fpG.gjC()"
    or not isinstance(_ROWS, list)
    or len(_ROWS) != 17
):
    raise ValueError("Incomplete native shard-effect catalog")
_references = [row.get("reference") for row in _ROWS]
if any(
    type(reference) is not int or reference <= 0 for reference in _references
) or len(_references) != len(set(_references)):
    raise ValueError("Invalid or duplicate native shard-effect reference")
CATALOG = {row["reference"]: row for row in _ROWS}


def _int32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & (1 << 31) else value


def _slots(blob):
    validate(blob)
    result = []
    for tag, nested in proto_fields(blob):
        if tag != 10:
            continue
        fields = dict(proto_fields(nested))
        result.append(
            dict(
                position=fields.get(80, 0),
                reference=_int32(fields.get(88, 0)),
                color=fields.get(96, 0),
                slot_level=_int32(fields.get(112, 0)),
            )
        )
    positions = [slot["position"] for slot in result]
    if len(positions) != len(set(positions)) or sorted(positions) != list(
        range(len(positions))
    ):
        raise ValueError("Invalid native shard slot positions")
    for slot in result:
        if type(slot["position"]) is not int or not 0 <= slot["position"] <= 3:
            raise ValueError("Invalid native shard slot position")
        if type(slot["color"]) is not int or not 0 <= slot["color"] <= 4:
            raise ValueError("Invalid native shard color enum")
    return result


def bonuses(item, equipment_family):
    """Return native-confirmed passive stat deltas for one equipped item.

    Unsupported shard effects are reported and skipped using the same narrow
    runner policy as equipment_stats. Missing/empty shard state adds nothing.
    """
    if type(equipment_family) is not int or not 0 <= equipment_family <= 255:
        raise ValueError("Invalid native equipment family")
    blob = item.get("shard_state")
    if blob is None:
        return {"stats": {}, "unsupported": []}

    stats = {}
    unsupported = []
    slots = _slots(bytes(blob))
    templates = _socket_templates()
    template = templates.get(item.get("reference"))
    if template is not None and len(slots) > template["max_sockets"]:
        raise ValueError("Persisted shard slots exceed native item template")
    for slot in slots:
        if slot["reference"] <= 0 or slot["color"] == 0:
            continue
        if slot["slot_level"] < 0:
            raise ValueError("Invalid negative native shard slot level")
        shard = CATALOG.get(slot["reference"])
        if shard is None:
            unsupported.append(
                dict(
                    uid=item.get("uid"),
                    reference=slot["reference"],
                    slot=slot["position"],
                    reason="missing-native-shard-effect-catalog",
                )
            )
            continue
        level_map = shard["slot_level_map"]
        if not level_map:
            raise ValueError("Missing native shard slot-level map")
        level_row = level_map[0]
        for candidate in level_map[1:]:
            if candidate["slot_level"] > slot["slot_level"]:
                break
            level_row = candidate
        # The compact native map records only WA transition points. The final
        # transition remains valid for all larger slot-level inputs.
        effective_level = level_row["effective_level"]

        matching_family = equipment_family in {
            row["native_id"] for row in shard["equipment_families"]
        }
        selected_effects = []
        for effect in shard["effects"]:
            evaluated = next(
                (
                    row["values"]
                    for row in effect["levels"]
                    if row["effective_level"] == effective_level
                ),
                None,
            )
            if evaluated is None:
                # Level outside the native effect's fKR..fKS interval.
                continue
            native = dict(effect, values=evaluated)
            values = native["values"]
            supported = (
                not native["effect_criteria"]
                and not native["has_triggers"]
                and native["target_mask"] == 0
                and native["stat_id"] >= 0
            )
            if native["runner"] == "eWQ":
                supported = (
                    supported and native["parameter_count"] == 1 and len(values) == 1
                )
            elif native["runner"] == "eWN":
                supported = (
                    supported
                    and native["parameter_count"] == 3
                    and len(values) == 3
                    and values[1:] == [1, 0]
                )
            else:
                supported = False
            if not supported:
                unsupported.append(
                    dict(
                        uid=item.get("uid"),
                        reference=slot["reference"],
                        slot=slot["position"],
                        effect_id=native["id"],
                        generic=native["generic"],
                        reason="unsupported-native-shard-effect",
                    )
                )
                continue
            delta = values[0] * (2 if matching_family else 1)
            stats[native["stat_id"]] = stats.get(native["stat_id"], 0) + delta

    return {"stats": stats, "unsupported": unsupported}
