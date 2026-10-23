"""Explicit durable projections for native environmental variable arrays.

This Wakemu policy reconstructs counters from committed event records. It does
not claim the original server arithmetic was recovered from client variable names.
The caller owns the transaction and event lock; this module never writes or scans
maps. A missing profile policy returns None for the legacy publication path.
"""
import re

from . import environmental_runtime as rules
from . import environmental_storage as storage


CONTRACT = "wakemu.durable-native-variable-projection.v1"
_ENTITY_NAMES = {"Resource": "resource", "Group": "group", "Mob": "monster"}
_CONSTANTS = frozenset(
    (
        "challengeDuration",
        "challengeLevelMin",
        "challengeLevelMax",
        "notificationIntervalDuration",
        "nbGroupForReward",
        "nbMobForReward",
        "nbResourceForReward",
    )
)


def _binding(row):
    name, kind = row["native_name"], row["binding_kind"]
    if kind in ("configconstant", "declared_threshold"):
        expected_key = name.lower()
        if kind == "declared_threshold":
            expected_key = {
                "nbResourceMin": "nbresourceforreward",
                "nbMobMin": "nbmobforreward",
            }.get(name)
            if expected_key is None or not row.get("source_authority"):
                raise ValueError(
                    "Missing declared Wakemu threshold reconstruction authority"
                )
        elif name not in _CONSTANTS:
            raise ValueError("Unsupported native environmental constant")
        if (
            row["normalized_key"] != expected_key
            or not re.fullmatch(r"-?[0-9]+", row["native_value"] or "")
            or int(row["native_value"]) != row["constant_value"]
        ):
            raise ValueError(
                "Environmental constant lacks its exact native configuration"
            )
        return
    if kind in ("entity_personal_progress", "entity_global_progress"):
        entity = row["entity_kind"]
        prefix = {"monster": "Mob", "group": "Group"}.get(entity)
        suffix = "Player" if kind == "entity_personal_progress" else "Global"
        if (
            prefix is None
            or name != "nb" + prefix + suffix
            or not row.get("objective_key")
            or not isinstance(row.get("source_authority"), str)
            or not row["source_authority"].strip()
        ):
            raise ValueError("Missing declared entity progress authority")
        return
    if kind == "leader_progress":
        if (
            name not in ("nbResourceMax", "nbMobMax")
            or not row.get("objective_key")
            or not row.get("source_authority")
        ):
            raise ValueError("Missing declared competitive leader-progress authority")
        return
    for prefix, entity in _ENTITY_NAMES.items():
        for suffix, expected in (
            ("Player", "personal_progress"),
            ("Global", "global_progress"),
            ("Spawned", "spawned"),
            ("Left", "remaining"),
        ):
            if name == "nb" + prefix + suffix and kind == expected:
                if kind in ("spawned", "remaining") and row["entity_kind"] != entity:
                    break
                return
    raise ValueError("Unsupported or incorrectly scoped environmental native variable")


def _inventory(db, instance_id):
    # Successful owned births survive retirement as audit records. Remaining
    # reads actual retirement/group status, never reward thresholds or scores.
    # All joins start from the selected event, including the combat-group lookup.
    return db.execute(
        """
        WITH resources AS (
          SELECT 'resource'::text AS entity_kind,count(*)::bigint AS spawned,
                 count(*) FILTER (WHERE r.retired_at_ms IS NULL AND NOT EXISTS (
                   SELECT 1 FROM environmental_cleanup_outbox c
                   WHERE c.instance_id=r.instance_id AND c.entity_kind='resource'
                     AND c.entity_id=r.resource_uid AND c.completed_at_ms IS NOT NULL))::bigint AS remaining
          FROM environmental_owned_resources r
          JOIN environmental_event_memberships m ON m.instance_id=r.instance_id
            AND m.entity_kind='resource' AND m.entity_id=r.resource_uid AND m.spawn_owned
          WHERE r.instance_id=%s
        ), groups AS (
          SELECT g.*,c.status AS current_status,
            EXISTS(SELECT 1 FROM environmental_cleanup_outbox q
              WHERE q.instance_id=g.instance_id AND q.entity_kind='group'
                AND q.entity_id=g.group_id AND q.completed_at_ms IS NOT NULL) AS cleaned
          FROM environmental_owned_groups g
          JOIN environmental_event_memberships m ON m.instance_id=g.instance_id
            AND m.entity_kind='group' AND m.entity_id=g.group_id AND m.spawn_owned
          LEFT JOIN combat_groups c ON c.map_id=g.map_id
            AND c.instance_id=g.world_instance_id AND c.group_id=g.group_id
          WHERE g.instance_id=%s
        )
        SELECT resources.*,0::bigint AS invalid FROM resources
        UNION ALL SELECT 'group',count(*)::bigint,
          count(*) FILTER(WHERE retired_at_ms IS NULL AND current_status IN ('available','fighting')
                           AND NOT cleaned)::bigint,
          count(*) FILTER(WHERE retired_at_ms IS NULL AND current_status IS NULL AND NOT cleaned)::bigint FROM groups
        UNION ALL SELECT 'monster',count(*)::bigint,
          count(*) FILTER(WHERE g.retired_at_ms IS NULL AND g.current_status IN ('available','fighting')
                           AND NOT g.cleaned)::bigint,0::bigint
          FROM environmental_owned_group_members m JOIN groups g
            ON g.instance_id=m.instance_id AND g.group_ordinal=m.group_ordinal
        """,
        (instance_id, instance_id),
    ).fetchall()


def project(db, event, profile, participant, now_ms):
    """Return ordered {variable_index,name,value} rows, or None for legacy.

    Policies cover complete native arrays, and support resource/fight families
    only. Inventory variables count the exact event-owned births, including
    monster members of owned groups; wild memberships require a separate policy.
    """
    storage._transaction(db)
    rules.integer(now_ms, "native variable projection clock")
    key = (profile["profile_key"], profile["version"])
    if key != (event["profile_key"], event["version"]):
        raise ValueError("Environmental variable event/profile mismatch")
    policy = db.execute(
        "SELECT * FROM environmental_profile_native_variable_policy "
        "WHERE profile_key=%s AND version=%s",
        key,
    ).fetchone()
    if policy is None:
        return None
    if (
        not profile["sealed"]
        or policy["policy_contract"] != CONTRACT
        or profile["native_scenario_id"] != policy["native_scenario_id"]
        or profile["family"]
        not in (
            "resource_collect",
            "resource_plant",
            "group_defeat",
            "monster_defeat",
            "monster_destroy",
        )
        or participant["instance_id"] != event["instance_id"]
    ):
        raise ValueError("Invalid frozen native environmental variable projection")
    rows = db.execute(
        """SELECT b.*,v.native_name AS original_name,
        c.normalized_key,c.native_value,s.family AS native_family
        FROM environmental_profile_native_variable_bindings b
        JOIN environmental_native_variables v ON v.source_key=b.source_key
          AND v.scenario_id=b.native_scenario_id AND v.ordinal=b.variable_index
        JOIN environmental_native_scenarios s ON s.source_key=b.source_key
          AND s.scenario_id=b.native_scenario_id
        LEFT JOIN environmental_native_configuration c ON c.source_key=b.source_key
          AND c.scenario_id=b.native_scenario_id AND c.native_key=b.configuration_key
        WHERE b.profile_key=%s AND b.version=%s ORDER BY b.variable_index""",
        key,
    ).fetchall()
    original = db.execute(
        "SELECT ordinal,native_name FROM environmental_native_variables "
        "WHERE source_key=%s AND scenario_id=%s ORDER BY ordinal",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchall()
    if not rows or [(r["variable_index"], r["native_name"]) for r in rows] != [
        (r["ordinal"], r["native_name"]) for r in original
    ]:
        raise ValueError(
            "Native environmental variable array is incomplete or reordered"
        )
    group_ui = (
        db.execute(
            "SELECT 1 FROM environmental_profile_group_ui WHERE profile_key=%s AND version=%s",
            key,
        ).fetchone()
        if profile["family"] in ("monster_defeat", "group_defeat")
        else None
    )
    destroy_ui = (
        db.execute(
            "SELECT source_key,native_scenario_id FROM environmental_profile_destroy_ui "
            "WHERE profile_key=%s AND version=%s",
            key,
        ).fetchone()
        if profile["family"] == "monster_destroy"
        else None
    )
    if destroy_ui is not None and (
        destroy_ui["source_key"] != policy["source_key"]
        or destroy_ui["native_scenario_id"] != policy["native_scenario_id"]
    ):
        raise ValueError("Native destroy variable policy changed its source")
    for row in rows:
        if (group_ui is not None or destroy_ui is not None) and row["native_name"] in (
            "nbMobPlayer",
            "nbGroupPlayer",
            "nbMobGlobal",
            "nbGroupGlobal",
        ):
            expected = (
                "entity_personal_progress"
                if row["native_name"].endswith("Player")
                else "entity_global_progress"
            )
            if row["binding_kind"] != expected:
                raise ValueError(
                    "Group UI requires independent durable entity counters"
                )
        if (
            row["native_name"] != row["original_name"]
            or row["native_family"] == "portal_boss_chain"
            or row["source_key"] != policy["source_key"]
            or row["native_scenario_id"] != policy["native_scenario_id"]
        ):
            raise ValueError("Native environmental variable source identity changed")
        if (
            row["binding_kind"] == "leader_progress"
            and profile["mode"] != "competitive"
        ):
            raise ValueError(
                "Leader progress requires a competitive environmental profile"
            )
        _binding(row)
    kinds = {r["binding_kind"] for r in rows}
    progress = {}
    if kinds & {"personal_progress", "global_progress", "leader_progress"}:
        for row in db.execute(
            """
            SELECT 'personal_progress'::text AS binding_kind,objective_key,quantity
              FROM environmental_progress WHERE instance_id=%s AND character_id=%s
            UNION ALL
            SELECT 'global_progress',objective_key,sum(quantity)::bigint
              FROM environmental_shared_actions WHERE instance_id=%s GROUP BY objective_key
            UNION ALL
            SELECT 'leader_progress',objective_key,max(quantity)::bigint
              FROM environmental_progress WHERE instance_id=%s GROUP BY objective_key
            """,
            (
                event["instance_id"],
                participant["character_id"],
                event["instance_id"],
                event["instance_id"],
            ),
        ).fetchall():
            progress[(row["binding_kind"], row["objective_key"])] = row["quantity"]
    entity_progress = {}
    if kinds & {"entity_personal_progress", "entity_global_progress"}:
        if profile["family"] == "monster_destroy":
            if destroy_ui is None:
                raise ValueError("Missing qualified native destruction variable policy")
            from .environmental_monster_destroy import counters
        else:
            from .environmental_group_progress import counters

        for entity in {
            r["entity_kind"] for r in rows if r["binding_kind"].startswith("entity_")
        }:
            personal, global_count = counters(db, event, participant, entity)
            entity_progress[("entity_personal_progress", entity)] = personal
            entity_progress[("entity_global_progress", entity)] = global_count
    inventory = {}
    if kinds & {"spawned", "remaining"}:
        if destroy_ui is not None:
            from .environmental_monster_destroy import inventory as destroy_inventory

            inventory = {r["entity_kind"]: r for r in destroy_inventory(db, event)}
        else:
            inventory = {
                r["entity_kind"]: r for r in _inventory(db, event["instance_id"])
            }
        if any(r["invalid"] for r in inventory.values()):
            raise ValueError(
                "Owned environmental population lacks its current durable group"
            )
    result = []
    for row in rows:
        kind = row["binding_kind"]
        if kind in ("configconstant", "declared_threshold"):
            value = row["constant_value"]
        elif kind in ("personal_progress", "global_progress", "leader_progress"):
            value = progress.get((kind, row["objective_key"]), 0)
        elif kind in ("entity_personal_progress", "entity_global_progress"):
            value = entity_progress[(kind, row["entity_kind"])]
        else:
            value = inventory[row["entity_kind"]][kind]
        if type(value) is not int or not -(2**63) <= value < 2**63:
            raise ValueError(
                "Native environmental variable is outside signed long bounds"
            )
        result.append(
            dict(
                variable_index=row["variable_index"],
                name=row["native_name"],
                value=value,
            )
        )
    return result
