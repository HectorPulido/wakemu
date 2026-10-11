"""Random, durable per-fight selection from verified native border prototypes."""
from functools import lru_cache
from hashlib import sha256
import json
import secrets

SETTING = "fight_border_policy"
POLICY = "wakemu-native-border-pool-v1"
# Only these generic null-owner roots have executable acceptance coverage.
VERIFIED = {46: (152027, 3641, 152028, 48), 48: (177618, 177619, 177620, 55)}


@lru_cache(maxsize=1)
def native_proofs():
    from .combat_effect_area import native_effect_areas
    from .combat_effect_area_catalog import area_effect_catalog

    return qualify(native_effect_areas(), area_effect_catalog()["effects"])


def qualify(areas, effects):
    """Require exact native generic roots, resource loss and once markers."""
    proofs = {}
    for reference, (root, loss, marker, loss_class) in VERIFIED.items():
        area = areas.get(str(reference))
        if (
            not isinstance(area, dict)
            or area.get("type") != "BATTLEGROUND_BORDER"
            or area.get("native_class") != "bcF"
            or area.get("raw_bdh") != []
            or area.get("effect_ids") != [root]
            or area.get("maximum_level") != 0
            or set(area.get("entry_masks", ())) != {10001, 10008, 10000}
            or area.get("exit_masks") != []
        ):
            raise ValueError("Unverified native border prototype")
        rows = {
            str(identity): effects.get(str(identity))
            for identity in (root, loss, marker)
        }
        group, change, once = (rows[str(identity)] for identity in (root, loss, marker))
        if (
            any(not isinstance(row, dict) for row in rows.values())
            or group.get("effect_class") != 330
            or group.get("children") != [loss, marker]
            or group.get("criteria")
            != f'not HasEffectWithSpecificId("target", {marker})'
            or change.get("effect_class") != loss_class
            or change.get("criteria") != ""
            or once.get("effect_class") != 400
            or once.get("criteria") != ""
            or any(row.get("variant") != 0 for row in rows.values())
        ):
            raise ValueError("Unverified native border effect closure")
        document = dict(area=area, effects=rows)
        proofs[reference] = sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    return proofs


def select(value, *, choice=secrets.choice):
    """Select once; the placement transaction persists the returned receipt."""
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "pool"}
        or type(value["version"]) is not int
        or value["version"] < 1
        or not isinstance(value["pool"], list)
        or not value["pool"]
        or any(
            type(reference) is not int or reference not in VERIFIED
            for reference in value["pool"]
        )
        or len(set(value["pool"])) != len(value["pool"])
    ):
        raise ValueError("Invalid native border selection policy")
    proofs = native_proofs()
    reference = choice(tuple(value["pool"]))
    if reference not in value["pool"]:
        raise ValueError("Border selection escaped configured pool")
    return dict(
        policy=POLICY,
        version=value["version"],
        reference=reference,
        native_sha256=proofs[reference],
    )


def validate(receipt):
    """Replays keep the original reference and fail closed on catalog drift."""
    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"policy", "version", "reference", "native_sha256"}
        or receipt.get("policy") != POLICY
        or type(receipt.get("version")) is not int
        or receipt["version"] < 1
        or type(receipt.get("reference")) is not int
        or receipt["reference"] not in VERIFIED
        or receipt.get("native_sha256") != native_proofs()[receipt["reference"]]
    ):
        raise ValueError("Invalid frozen native border receipt")
    return receipt["reference"]


def choose(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        raise ValueError("Missing native border selection policy")
    return select(row["value"])
