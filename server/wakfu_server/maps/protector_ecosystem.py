"""Publish native protector tax objects without inventing actors or nations."""
from functools import lru_cache
import math
import os
import threading
import struct

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT

SETTING = "native_protector_tax_policy"


@lru_cache(maxsize=1)
def _map_ids():
    territories = native_catalog.load(DATA_ROOT / "territory-protector-bonuses.json")[
        "territories"
    ]
    identities = {}
    for row in native_catalog.load(DATA_ROOT / "monster-encyclopedia.json")[
        "territories"
    ]:
        territory = row["territory_id"]
        raw = row["raw_native"]
        definition = territories.get(str(territory))
        if definition is None or definition["map_id"] is None:
            continue
        identity, world, nation = raw["ctC"], definition["map_id"], raw["Xt"]
        if (
            any(
                type(value) is not int or not 0 < value < 2**31
                for value in (territory, identity, world)
            )
            or raw["ctH"] != territory
            or type(nation) is not int
            or not 0 <= nation < 2**31
        ):
            raise ValueError("Invalid native protector territory identity")
        # Original bLU.c(aMD) initializes both xh nation fields from Xt.
        # ctH is the exact native territory join; no actor/appearance is inferred.
        contract = (identity, nation, nation, territory)
        known = identities.setdefault(world, {})
        if identity in known and known[identity] != contract:
            raise ValueError("Conflicting native protector territory identity")
        known[identity] = contract
    return {
        world: tuple(values[identity] for identity in sorted(values))
        for world, values in identities.items()
    }


@lru_cache(maxsize=1)
def _wishes():
    """Encode native bLU/bLW/bLX targets from the database catalog."""
    result = {}
    for row in native_catalog.load(DATA_ROOT / "monster-encyclopedia.json")[
        "territories"
    ]:
        raw = row["raw_native"]
        sections = []
        for name in ("ctN", "ctO"):
            targets = raw[name]
            if not isinstance(targets, list) or len(targets) > 65535:
                raise ValueError("Invalid native protector wishes")
            bindings = {}
            for target in targets:
                family, low, high = target["aIc"], target["ctP"], target["ctQ"]
                if (
                    any(type(value) is not int for value in (family, low, high))
                    or not 0 < family < 2**31
                    or not 0 <= low <= high < 2**31
                    or family in bindings
                ):
                    raise ValueError("Invalid native protector wish range")
                bindings[family] = (low, high)
            sections.append(
                b"\x01"
                + struct.pack(">H", len(bindings))
                + b"".join(
                    struct.pack(">iii", family, *bindings[family])
                    for family in sorted(bindings)
                )
            )
        result[raw["ctC"]] = b"".join(sections) + b"\x00"
    return result


def _with_wishes(record, wishes, satisfaction=None):
    # Last three optional sections are xd monster targets, xl plant targets, xa.
    if record[-3:] != bytes(3):
        raise ValueError("Unsupported existing native protector wish sections")
    if satisfaction is None:
        return record[:-3] + wishes
    if record[-4] != 0:
        raise ValueError("Unsupported existing protector satisfaction section")
    return record[:-4] + struct.pack(">Bb", 1, satisfaction) + wishes


def _satisfaction(db, map_id, instance_id):
    """Use the same complete population authority as territorial bonuses."""
    from wakfu_server import ecology_context, ecology_population
    from wakfu_server.characters import territory_bonuses

    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid protector instance identity")
    bindings = _map_ids().get(map_id, ())
    if not bindings:
        return {}
    population = ecology_population.snapshot(
        db,
        map_id,
        instance_id,
        locate=ecology_context.population_region,
        exclude_unassigned=True,
    )
    if not population["complete"]:
        return {}
    result = {}
    for identity, _, _, territory in bindings:
        counts = population["regions"].get(territory, {"monster": {}, "plant": {}})
        region = territory_bonuses.evaluate_population(
            territory, dict(counts.get("monster", {})), dict(counts.get("plant", {}))
        )
        result[identity] = {None: -1, 1917: 1, 1915: 2, 1916: 3}[region["state_id"]]
    return result


def _taxes(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    policy = None if row is None else row["value"]
    if (
        not isinstance(policy, dict)
        or policy.get("schema_version") != 1
        or set(policy) != {"schema_version", "contexts"}
        or not isinstance(policy["contexts"], dict)
        or set(policy["contexts"]) != {"1"}
    ):
        raise ValueError("Missing or invalid native protector tax policy")
    value = policy["contexts"]["1"]
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0.05 <= value <= 0.7
    ):
        raise ValueError("Invalid native market tax value")
    return struct.pack(">HBf", 1, 1, value)


def _enrich(record, taxes):
    """Preserve the accredited captured xh/wX profile and add its tax section."""
    # Existing NPC protectors publish only territory/nations and appearance/actor.
    if (
        not isinstance(record, bytes)
        or len(record) not in (41, 48)
        or record[4] != 1
        or record[17] != 1
        or record[30:35] != bytes(5)
    ):
        raise ValueError("Unsupported captured protector record profile")
    if len(record) == 41:
        if record[35:] != bytes(6):
            raise ValueError("Invalid captured protector optional sections")
        return record[:35] + b"\x01" + taxes + record[36:]
    if record[35] != 1 or record[43:] != bytes(5) or record[36:39] != b"\x00\x01\x01":
        raise ValueError("Invalid existing captured protector tax section")
    return record[:36] + taxes + record[43:]


def bootstrap_records(db, map_id, existing_records=(), *, instance_id=0):
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid protector map identity")
    taxes = _taxes(db)
    result = {}
    for record in existing_records:
        if not isinstance(record, bytes) or len(record) < 4:
            raise ValueError("Invalid captured protector record")
        identity = struct.unpack_from(">i", record)[0]
        if identity <= 0 or identity in result:
            raise ValueError("Duplicate or invalid captured protector identity")
        result[identity] = _enrich(record, taxes)
    for identity, original_nation, current_nation, territory in _map_ids().get(
        map_id, ()
    ):
        if identity not in result:
            # fwR rejects tax-only records because gqO()/territory remains null.
            result[identity] = (
                struct.pack(
                    ">iBiii", identity, 1, original_nation, current_nation, territory
                )
                + bytes(6)
                + b"\x01"
                + taxes
                + bytes(5)
            )
    wishes = _wishes()
    satisfaction = _satisfaction(db, map_id, instance_id)
    return tuple(
        _with_wishes(result[identity], wishes[identity], satisfaction.get(identity))
        if identity in wishes
        else result[identity]
        for identity in sorted(result)
    )


_policy_pool = None
_policy_pool_lock = threading.Lock()


def _policy_database():
    # Catalog decoding can acquire its own bounded pool while encoding policy.
    # Never hold a catalog connection across those nested document reads.
    global _policy_pool
    with _policy_pool_lock:
        if _policy_pool is None:
            from wakfu_server.postgres import Database

            _policy_pool = Database(
                os.environ["WAKFU_DATABASE_URL"],
                password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
            )
        return _policy_pool


def message_records(map_id, existing_records=(), *, instance_id=0):
    """Shared native13974 encoder seam using PostgreSQL policy authority."""
    with _policy_database().connection() as db:
        return bootstrap_records(db, map_id, existing_records, instance_id=instance_id)
