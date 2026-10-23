"""Original equippable definitions omitted by the legacy nonempty-effect export."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from wakfu_server import native_catalog

SOURCE_SHA256 = "e86f4aecb0532cbe3e443fa002deb8ad65554ada3bbcede0f011ef31b94792be"
CATALOG_REVISION = "b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450"


@lru_cache(maxsize=1)
def definitions():
    raw = Path(__file__).with_name("native_empty_equipment_effects.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting original empty equipment definitions")
    if native_catalog.release() != CATALOG_REVISION:
        raise ValueError("Empty equipment definitions belong to another native release")
    data = json.loads(raw)
    if (
        data["policy"] != "original-bIJ-equip-rule-match-gjg-empty-v1"
        or data["requested_count"] != 626
        or data["factory_seen_count"] != 626
        or any(
            data[key]
            for key in (
                "nonempty",
                "failed_factory",
                "not_equippable",
                "rule_mismatch",
                "not_found",
            )
        )
    ):
        raise ValueError("Incomplete original empty equipment recovery")
    result = {row["reference"]: row for row in data["verified_empty"]}
    if len(result) != 626 or any(row["effects"] != [] for row in result.values()):
        raise ValueError("Invalid original empty equipment effect list")
    return result


def template(reference):
    """Return zero effects only for an original definition matching current rules.

    Unknown missing definitions keep the existing unsupported-template behavior.
    This never replaces an actual published effect template, including passives
    whose execution has not been qualified.
    """
    from wakfu_server.equipment import RULES

    row = definitions().get(reference)
    if row is None:
        return None
    rule = RULES.get(reference)
    if rule is None or any(
        rule.get(key) != row[key]
        for key in (
            "minimum_level",
            "native_dte",
            "slots",
            "occupied_slots",
            "has_conditions",
        )
    ):
        raise ValueError("Recovered empty equipment conflicts with native rules")
    return dict(reference=reference, item_level=row["minimum_level"], effects=[])
