"""Compile and publish bounded original GenericActivable programs, never grants.

The existing migration273 tables and normal native reward executor own live
eligibility, inventory/payment and native script delivery. Publication seals
new policies atomically and compares existing immutable records on retries.
"""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from zipfile import ZipFile
from pathlib import Path

SCHEMA = "native-generic-reward-batch-v1"
APPROACH = "wakemu.reconstructed-cardinal-native-walkable.v1"
PROGRAM_FIELDS = (
    "policy_id",
    "version",
    "authority",
    "lifecycle_mode",
    "catalog_revision",
    "descriptor_id",
    "wire_action",
    "native_action_id",
    "group_id",
    "mru",
    "group_cof",
    "group_cog",
    "group_cnd",
    "group_cod",
    "group_coe",
    "raw_cob",
    "action_criterion",
)
EFFECT_FIELDS = (
    "policy_id",
    "effect_order",
    "effect_reference",
    "effect_type",
    "criterion",
    "parameters",
    "item_reference",
    "item_quantity",
    "loot_list_id",
    "source_sha256",
    "loot_source_sha256",
)
LOCATION_FIELDS = (
    "policy_id",
    "map_id",
    "object_id",
    "x",
    "y",
    "z",
    "payload_hex",
    "state_payload_hex",
    "geometry_sha256",
    "approach_policy",
)


def _hash(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def compile_entry(
    program,
    source,
    *,
    catalog_revision,
    source_sha256,
    geometry_sha256,
    approaches,
    state=None,
    lifecycle_mode="NATIVE_INVENTORY_GUARD",
    authority,
    loot_tables=None,
    external_quest_scripts=(),
):
    entry = deepcopy(
        dict(
            program=program,
            source=source,
            catalog_revision=catalog_revision,
            source_sha256=source_sha256,
            geometry_sha256=geometry_sha256,
            approaches=approaches,
            state=state,
            lifecycle_mode=lifecycle_mode,
            authority=authority,
            loot_tables={} if loot_tables is None else loot_tables,
            external_quest_scripts=list(external_quest_scripts),
        )
    )
    jar = Path(__file__).resolve().parents[2] / "client/contents/scripts/scripts.jar"
    with ZipFile(jar) as archive:
        entry["script_sources"] = {
            str(effect["action_reference"]): sha256(
                archive.read(f'genericIEActions/{effect["action_reference"]}.lua')
            ).hexdigest()
            for group in program["groups"]
            for action in group["actions"]
            for effect in action["effects"]
            if effect["effect_type"] == 1
            and f'genericIEActions/{effect["action_reference"]}.lua'
            in archive.namelist()
        }
    _records(entry)
    return entry


def _records(entry):
    from wakfu_server import native_generic_rewards

    if not all(
        _hash(entry.get(key))
        for key in ("catalog_revision", "source_sha256", "geometry_sha256")
    ):
        raise ValueError(
            "Native generic source requires exact revision and source pins"
        )
    if not isinstance(entry.get("authority"), str) or not entry["authority"].strip():
        raise ValueError(
            "Native generic publication requires explicit reviewed authority"
        )
    program, source = entry["program"], entry["source"]
    if (
        program.get("native_class") != "aLl"
        or source.get("type") != "GenericActivableInteractiveElement"
        or source.get("descriptor_id") != program.get("descriptor_id")
        or type(program.get("descriptor_id")) is not int
        or program["descriptor_id"] <= 0
        or len(program.get("groups", ())) != 1
    ):
        raise ValueError(
            "Native generic object lacks its exact single original program"
        )
    group = program["groups"][0]
    if group.get("native_class") != "aLo" or len(group.get("actions", ())) != 1:
        raise ValueError("Native generic publication requires one original action")
    action = group["actions"][0]
    if (
        action.get("native_class") != "aLn"
        or action.get("wire_action") != 0
        or action.get("raw_cob") != 1.0
        or group.get("cnd") != 0
        or group.get("cog") != 0
    ):
        raise ValueError("Unsupported timed or probabilistic native generic action")
    if entry["lifecycle_mode"] not in (
        "NATIVE_INVENTORY_GUARD",
        "ONCE_PER_CHARACTER_RECONSTRUCTED",
    ):
        raise ValueError("Unsupported native generic lifecycle")
    if (
        any(type(group.get(k)) is not int or group[k] < 0 for k in ("cod", "coe"))
        or (group["cod"] == 0) != (group["coe"] == 0)
        or group["coe"] > 32767
        or (group["cod"] and group.get("cof") is not True)
    ):
        raise ValueError("Unqualified native generic payment")
    policy = f'native.generic.reward.{program["descriptor_id"]}.v1'
    rule = dict(
        policy_id=policy,
        version=1,
        authority=entry["authority"],
        lifecycle_mode=entry["lifecycle_mode"],
        catalog_revision=entry["catalog_revision"],
        descriptor_id=program["descriptor_id"],
        wire_action=action["wire_action"],
        native_action_id=action["native_id"],
        group_id=group["id"],
        mru=group["clx"],
        group_cof=group["cof"],
        group_cog=group["cog"],
        group_cnd=group["cnd"],
        group_cod=group["cod"],
        group_coe=group["coe"],
        raw_cob=action["raw_cob"],
        action_criterion=action["criterion"],
    )
    external = {}
    for binding in entry.get("external_quest_scripts", ()):
        if (
            type(binding) is not dict
            or set(binding)
            != {"effect_reference", "quest_id", "objective_id", "native_criterion"}
            or any(
                type(binding[key]) is not int or binding[key] <= 0
                for key in ("effect_reference", "quest_id", "objective_id")
            )
            or type(binding["native_criterion"]) is not str
            or binding["effect_reference"] in external
        ):
            raise ValueError("Invalid external native quest callback declaration")
        external[binding["effect_reference"]] = binding
    unused_external = set(external)
    effects, tables = [], {}
    for index, raw in enumerate(action["effects"]):
        kind, parameters = raw["effect_type"], raw["parameters"]
        if (
            raw.get("native_class") != "aLm"
            or kind not in (1, 4, 12)
            or not isinstance(parameters, list)
            or any(type(p) is not str for p in parameters)
        ):
            raise ValueError("Unsupported original native generic effect")
        effect = dict(
            policy_id=policy,
            effect_order=index,
            effect_reference=raw["action_reference"],
            effect_type=kind,
            criterion=raw["criterion"],
            parameters=parameters,
            item_reference=None,
            item_quantity=None,
            loot_list_id=None,
            source_sha256=entry["source_sha256"],
            loot_source_sha256=None,
        )
        if kind == 1:
            if parameters not in ([], ["false"], ["true"]):
                raise ValueError("Unknown original script binding parameters")
            jar = (
                Path(__file__).resolve().parents[2]
                / "client/contents/scripts/scripts.jar"
            )
            with ZipFile(jar) as archive:
                name = f'genericIEActions/{raw["action_reference"]}.lua'
                script = archive.read(name) if name in archive.namelist() else None
            declared = external.get(raw["action_reference"])
            if declared is not None:
                if (
                    script is not None
                    or declared["native_criterion"] != raw["criterion"]
                ):
                    raise ValueError(
                        "External quest callback must retain its absent native client script and exact criterion"
                    )
                unused_external.remove(raw["action_reference"])
            elif (
                script is None
                or not script.strip()
                or entry.get("script_sources", {}).get(str(raw["action_reference"]))
                != sha256(script).hexdigest()
            ):
                raise ValueError("Native generic script source is absent")
        elif kind == 12:
            if len(parameters) != 2:
                raise ValueError("Invalid original fixed item effect")
            effect.update(
                item_reference=int(parameters[0]), item_quantity=int(parameters[1])
            )
            if (
                not 0 < effect["item_reference"] < 2**31
                or not 1 <= effect["item_quantity"] <= 32767
            ):
                raise ValueError("Invalid original fixed item quantity")
        else:
            if len(parameters) != 1:
                raise ValueError("Invalid original loot table effect")
            reference = int(parameters[0])
            original = entry["loot_tables"].get(
                str(reference), entry["loot_tables"].get(reference)
            )
            if (
                not original
                or not _hash(original.get("source_sha256"))
                or original["payload"].get("d") != reference
            ):
                raise ValueError("Native generic loot lacks its exact original table")
            tables[reference] = original
            effect.update(
                loot_list_id=reference, loot_source_sha256=original["source_sha256"]
            )
        if kind != 1 and rule["lifecycle_mode"] == "NATIVE_INVENTORY_GUARD":
            qualified = (
                kind == 12
                and effect["criterion"]
                == f"GetItemQuantity({effect['item_reference']}) <= 0"
            )
            if kind == 4:
                if sum(row["effect_type"] != 1 for row in action["effects"]) != 1:
                    raise ValueError(
                        "Repeatable native loot requires one item-producing effect"
                    )
                row = tables[effect["loot_list_id"]]
                db = SimpleNamespace(
                    execute=lambda *_: SimpleNamespace(fetchone=lambda: row)
                )
                qualified = native_generic_rewards._inventory_loot_guard(db, effect)
            if not qualified:
                raise ValueError(
                    "Repeatable original loot lacks its positive native inventory guard"
                )
        effects.append(effect)
    if not effects or len({r["effect_reference"] for r in effects}) != len(effects):
        raise ValueError("Native generic program needs distinct original effects")
    points = entry["approaches"]
    if (
        not isinstance(points, list)
        or not points
        or any(
            not isinstance(p, list)
            or len(p) != 3
            or any(type(v) is not int for v in p)
            or abs(p[0] - source["x"]) + abs(p[1] - source["y"]) not in (1, 2)
            or abs(p[2] - source["z"]) > 4
            for p in points
        )
        or len(set(map(tuple, points))) != len(points)
    ):
        raise ValueError("Native generic approach lacks exact adjacent walkable proof")
    if any(
        type(source.get(k)) is not int or source[k] <= 0 for k in ("map_id", "id")
    ) or any(
        type(source.get(k)) not in (int, float) or int(source[k]) != source[k]
        for k in ("x", "y", "z")
    ):
        raise ValueError("Native generic placement must be integral")
    state = entry["state"]
    location = dict(
        policy_id=policy,
        map_id=source["map_id"],
        object_id=source["id"],
        **{k: int(source[k]) for k in ("x", "y", "z")},
        payload_hex=source["payload_hex"],
        state_payload_hex=None if state is None else state["payload_hex"],
        geometry_sha256=entry["geometry_sha256"],
        approach_policy=APPROACH,
    )
    if state is not None and (
        state["map_id"] != source["map_id"] or state["type"] != source["type"]
    ):
        raise ValueError("Native generic state belongs to another placement")
    if unused_external:
        raise ValueError("External native quest callback is absent from this program")
    return rule, effects, location, tables


def _insert_or_compare(db, table, values, keys):
    from psycopg.types.json import Jsonb

    condition = " AND ".join(f"{key}=%s" for key in keys)
    old = db.execute(
        f"SELECT * FROM {table} WHERE {condition}", tuple(values[k] for k in keys)
    ).fetchone()
    if old is not None:
        if any(old.get(key) != value for key, value in values.items()):
            raise ValueError("Immutable native generic publication differs: " + table)
        return False
    fields = tuple(values)
    db.execute(
        f"INSERT INTO {table} ("
        + ",".join(fields)
        + ") VALUES ("
        + ",".join(["%s"] * len(fields))
        + ")",
        tuple(
            Jsonb(values[k]) if isinstance(values[k], dict) else values[k]
            for k in fields
        ),
    )
    return True


def install(db, document):
    from wakfu_server import native_generic_rewards

    if (
        document.get("schema") != SCHEMA
        or not isinstance(document.get("entries"), list)
        or not document["entries"]
    ):
        raise ValueError("Invalid native generic reward batch")
    db.execute("SELECT pg_advisory_xact_lock(%s)", (202611160273,))
    prepared = [(entry, *_records(entry)) for entry in document["entries"]]
    for entry, rule, _, location, _ in prepared:
        for binding in entry.get("external_quest_scripts", ()):
            actual = db.execute(
                "SELECT quest_id,objective_id,native_criterion FROM quest_interactive_bindings "
                "WHERE map_id=%s AND object_id=%s AND action_id=%s AND parameter=0 "
                "AND native_effect_reference=%s AND script_id=0",
                (
                    location["map_id"],
                    location["object_id"],
                    rule["wire_action"],
                    binding["effect_reference"],
                ),
            ).fetchone()
            if actual is None or any(
                actual[key] != binding[key]
                for key in ("quest_id", "objective_id", "native_criterion")
            ):
                raise ValueError(
                    "External native quest callback requires its exact installed guarded interaction"
                )
    identities = [
        (location["map_id"], location["object_id"]) for _, _, _, location, _ in prepared
    ]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate native generic placement in batch")
    grouped = {}
    for row in prepared:
        grouped.setdefault(row[1]["policy_id"], []).append(row)
    inserted = 0
    for rows in grouped.values():
        rule, effects = rows[0][1:3]
        if any(row[1] != rule or row[2] != effects for row in rows):
            raise ValueError(
                "One native descriptor has contradictory original programs"
            )
        for _, _, _, _, tables in rows:
            for reference, table in tables.items():
                _insert_or_compare(
                    db,
                    "native_random_item_tables",
                    dict(reference=reference, **table),
                    ("reference",),
                )
        exists = db.execute(
            "SELECT * FROM native_generic_reward_programs WHERE policy_id=%s",
            (rule["policy_id"],),
        ).fetchone()
        if exists is not None:
            if not exists["sealed"] or any(exists[k] != v for k, v in rule.items()):
                raise ValueError("Immutable native generic program differs")
        else:
            _insert_or_compare(
                db, "native_generic_reward_programs", rule, ("policy_id",)
            )
            for effect in effects:
                _insert_or_compare(
                    db,
                    "native_generic_reward_effects",
                    effect,
                    ("policy_id", "effect_reference"),
                )
            for entry, _, _, location, _ in rows:
                _insert_or_compare(
                    db,
                    "native_generic_reward_locations",
                    location,
                    ("map_id", "object_id"),
                )
                for point in entry["approaches"]:
                    _insert_or_compare(
                        db,
                        "native_generic_reward_approaches",
                        dict(
                            map_id=location["map_id"],
                            object_id=location["object_id"],
                            **dict(zip(("x", "y", "z"), point)),
                        ),
                        ("map_id", "object_id", "x", "y", "z"),
                    )
            db.execute(
                "UPDATE native_generic_reward_programs SET sealed=true WHERE policy_id=%s",
                (rule["policy_id"],),
            )
            inserted += 1
        for entry, _, _, location, _ in rows:
            current = native_generic_rewards._rule(
                db, location["map_id"], location["object_id"]
            )
            if (
                current is None
                or any(current[k] != v for k, v in location.items())
                or current["effects"] != effects
                or sorted(current["approaches"]) != sorted(entry["approaches"])
            ):
                raise ValueError("Immutable native generic children differ")
            native_generic_rewards._source(current)
            from wakfu_server.combat_geometry import published_geometry

            if (
                not set(map(tuple, entry["approaches"]))
                <= published_geometry(location["map_id"]).cells
            ):
                raise ValueError(
                    "Native generic approaches leave original walkable geometry"
                )
    return dict(programs=len(grouped), inserted=inserted, locations=len(identities))
