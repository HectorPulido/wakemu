"""Native characteristic checks over explicit, hash-bound catalog inputs.

Catalog bytes are supplied by the caller before inspection. No loader, clock,
provider, setter or listener is invoked by this module.
"""
from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class ResourceDefinition:
    stat: int
    hard_minimum: int
    hard_maximum: int
    over_max_current: bool


@dataclass(frozen=True)
class ResourceAuthority:
    revision: str
    actor_sha256: str
    copy_sha256: str
    definitions: tuple

    def __post_init__(self):
        if (
            type(self.revision) is not str
            or not self.revision
            or type(self.definitions) is not tuple
            or len(self.definitions) != 4
            or any(type(row) is not ResourceDefinition for row in self.definitions)
            or tuple(row.stat for row in self.definitions) != (1, 2, 3, 4)
        ):
            raise ValueError("Complete explicit resource authority required")
        for value in (self.actor_sha256, self.copy_sha256):
            if (
                type(value) is not str
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError("Explicit catalog document hashes required")
        for row in self.definitions:
            if (
                type(row.stat) is not int
                or type(row.hard_minimum) is not int
                or type(row.hard_maximum) is not int
                or not -(1 << 31) <= row.hard_minimum <= row.hard_maximum < (1 << 31)
                or type(row.over_max_current) is not bool
            ):
                raise ValueError("Invalid native characteristic definition")

    @classmethod
    def from_documents(
        cls, *, revision, actor_bytes, copy_bytes, actor_sha256, copy_sha256
    ):
        """Verify consumed bytes, then retain only the immutable needed facts."""
        for raw, expected in ((actor_bytes, actor_sha256), (copy_bytes, copy_sha256)):
            if (
                type(raw) is not bytes
                or len(raw) > 64 * 1024 * 1024
                or hashlib.sha256(raw).hexdigest() != expected
            ):
                raise ValueError(
                    "Resource authority bytes differ from catalog manifest"
                )
        actor = json.loads(actor_bytes)["characteristics"]
        copied = json.loads(copy_bytes)["fresh_characteristics"]
        definitions = []
        for stat in (1, 2, 3, 4):
            row, native = actor[str(stat)], copied[str(stat)]
            if (
                row["hard_minimum"] != native["hard_minimum"]
                or row["hard_maximum"] != native["hard_maximum"]
            ):
                raise ValueError("Native characteristic documents disagree")
            definitions.append(
                ResourceDefinition(
                    stat,
                    row["hard_minimum"],
                    row["hard_maximum"],
                    native["over_max_current"],
                )
            )
        return cls(revision, actor_sha256, copy_sha256, tuple(definitions))

    def as_dict(self):
        return dict(
            revision=self.revision,
            actor_sha256=self.actor_sha256,
            copy_sha256=self.copy_sha256,
        )


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def _effective_maximum(raw, percentage, low, high):
    # fff.aYU uses signed32 multiplication and Java truncation toward zero.
    product = _int32(raw * percentage)
    quotient = (abs(product) // 100) * (-1 if product < 0 else 1)
    return max(low, min(high, _int32(raw + quotient)))


def check_resource_definitions(row, path, authority, issue, unknown, checked):
    if authority is None:
        unknown(
            "resource.hard_bounds",
            path,
            "Hard limits and percentage definitions require explicit catalog authority",
        )
        return
    if type(authority) is not ResourceAuthority:
        raise ValueError("Typed hash-bound resource authority required")
    stats, minima, maxima = (
        row[name] for name in ("effect_stats", "effect_minima", "effect_maxima")
    )
    for definition in authority.definitions:
        stat, low, high = (
            definition.stat,
            definition.hard_minimum,
            definition.hard_maximum,
        )
        where = path + f".effect_stats[{stat}]"
        if any(type(values.get(stat)) is not int for values in (stats, minima, maxima)):
            continue  # The structural checker reports this missing authority.
        if any(not low <= values[stat] <= high for values in (stats, minima, maxima)):
            issue(
                "resource.hard_bounds",
                where,
                "Effective current, minimum or maximum exceeds native hard limits",
            )
        if stats[stat] != max(minima[stat], min(maxima[stat], stats[stat])):
            issue(
                "resource.effective_bounds",
                where,
                "Effective current is outside its native clamped projection",
            )
        # Raw may survive a later maximum/minimum change. Never compare it
        # against the visible maximum or infer nonnegativity without the row.
        copied_source = row.get("native_copy_pa_source")
        raw = None
        if (
            type(copied_source) is dict
            and copied_source.get("producer") == "eHI.pRU.ffh.a"
        ):
            currents = row.get("effect_characteristic_raw_currents")
            raw = currents.get(stat) if type(currents) is dict else None
        elif (
            stat == 1
            and row.get("native_hp_raw_current_source")
            == "fresh_initial_tB_HP.on_resource_override"
        ):
            raw = row.get("effect_hp_raw_current")
        elif (
            stat in (2, 3)
            and row.get("native_resource_raw_current_source")
            == "fresh_ffh_AP_MP_mutable_on_within_bounds"
        ):
            currents = row.get("effect_resource_raw_currents")
            raw = currents.get(stat) if type(currents) is dict else None
        if type(raw) is int and not low <= raw <= high:
            issue(
                "resource.raw_hard_bounds",
                where,
                "Raw current exceeds native hard limits",
            )
        base_maxima, base_minima, percentages = (
            row.get(name)
            for name in (
                "effect_base_maxima",
                "effect_base_minima",
                "effect_percentages",
            )
        )
        if not all(
            type(values) is dict for values in (base_maxima, base_minima, percentages)
        ) or any(
            type(values.get(stat)) is not int
            for values in (base_maxima, base_minima, percentages)
        ):
            unknown(
                "resource.maximum_authority",
                where,
                "Raw maximum/minimum/percentage operands unavailable",
            )
            continue
        base, minimum, percentage = (
            base_maxima[stat],
            base_minima[stat],
            percentages[stat],
        )
        if any(
            not -(1 << 31) <= value < (1 << 31) for value in (base, minimum, percentage)
        ):
            issue("resource.operand_width", where, "Resource operand is not signed32")
            continue
        if (
            base < minimum
            or minima[stat] != max(low, min(high, minimum))
            or maxima[stat] != _effective_maximum(base, percentage, low, high)
        ):
            issue(
                "resource.maximum_projection",
                where,
                "Effective bounds disagree with native raw/percentage operands",
            )
    checked.extend(
        (
            "resource.hard_bounds",
            "resource.raw_hard_bounds",
            "resource.effective_bounds",
            "resource.maximum_projection",
        )
    )
