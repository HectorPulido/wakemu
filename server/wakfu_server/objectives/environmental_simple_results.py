"""Unranked resource result mapping over actual completed entitlements.

Original client base reward values are compared to the frozen entitlement,
without boosters. Personal/global progress is an explicitly declared Wakemu
interpretation of native winnerScore, not a recovered official server formula.
This module grants, reserves and acknowledges nothing.
"""
from . import environmental_storage as storage


CONTRACT = "wakemu.original-resource-single-primary-base-result.v1"
DESTROY_CONTRACT = "wakemu.original-destroy-single-primary-base-result.v1"
GROUP_CONTRACT = "wakemu.original-group-single-primary-base-result.v1"


def _components(row):
    result = []
    for kind, reference, quantity in (
        ("xp", None, row["base_xp"]),
        ("item", row["item_reference"], row["item_quantity"]),
        ("kamas", None, row["kamas"]),
    ):
        if type(quantity) is not int or not 0 <= quantity < 2**31:
            raise ValueError(
                "Original simple resource reward exceeds normalized bounds"
            )
        if not quantity:
            continue
        if kind == "item" and (type(reference) is not int or reference <= 0):
            raise ValueError("Original simple resource item lacks its reference")
        result.append((kind, reference, quantity))
    return sorted(result, key=lambda row: row[0])


def project(db, event, profile, participant, now_ms):
    """Return the native_result joined contract, or None without qualification.

    A completed participant must already have a durable entitlement containing
    exactly the original single primary base reward. Capacity may keep that
    entitlement unclaimed; UI publication never stands in for settlement.
    """
    storage._transaction(db)
    key = (profile["profile_key"], profile["version"])
    if key != (event["profile_key"], event["version"]):
        raise ValueError("Simple result event differs from its frozen profile")
    policy = db.execute(
        """SELECT q.*,p.mode AS frozen_mode,p.family AS frozen_family,
        p.sealed AS profile_sealed,p.native_scenario_id AS profile_scenario
        FROM environmental_profile_simple_result_policy q
        JOIN environmental_runtime_profiles p USING(profile_key,version)
        WHERE q.profile_key=%s AND q.version=%s""",
        key,
    ).fetchone()
    if policy is None:
        return None
    resource = profile["family"] == "resource_collect"
    group = profile["family"] in ("monster_defeat", "group_defeat")
    destroy = profile["family"] == "monster_destroy"
    expected_mode = {"solo": "personal_progress", "collaborative": "global_progress"}
    if (
        not profile["sealed"]
        or policy["profile_sealed"] is not True
        or not (resource or group or destroy)
        or policy["frozen_family"] != profile["family"]
        or profile["mode"] not in expected_mode
        or policy["frozen_mode"] != profile["mode"]
        or policy["parameter_mode"] != expected_mode[profile["mode"]]
        or policy["policy_contract"]
        != (CONTRACT if resource else DESTROY_CONTRACT if destroy else GROUP_CONTRACT)
        or policy["primary_reward_index"] != 0
        or policy["native_scenario_id"] != profile["native_scenario_id"]
        or policy["profile_scenario"] != profile["native_scenario_id"]
    ):
        raise ValueError("Invalid frozen simple resource result policy")
    for field in ("source_authority", "mapping_authority", "parameter_authority"):
        if type(policy[field]) is not str or not policy[field].strip():
            raise ValueError("Missing declared simple resource result authority")
    source = db.execute(
        "SELECT family,native_type,native_subtype,client_visible FROM environmental_native_scenarios "
        "WHERE source_key=%s AND scenario_id=%s",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchone()
    if (
        source is None
        or source["family"]
        != (
            "resource_interaction"
            if resource
            else "destroy_monster_action"
            if destroy
            else "group_template"
        )
        or (group and source["native_type"] not in (6, 7, 8))
        or source["client_visible"] is not True
        or source["native_subtype"] != (1 if profile["mode"] == "solo" else 4)
    ):
        raise ValueError("Simple result lacks its original resource mode/source")
    if destroy:
        from .environmental_reward_bands import _destroy_source

        _destroy_source(db, key, policy, source, profile)
    primary = db.execute(
        """SELECT d.*,r.native_text FROM environmental_native_reward_display d
        JOIN environmental_native_rewards_raw r USING(source_key,scenario_id,reward_id)
        WHERE d.source_key=%s AND d.scenario_id=%s AND d.primary_reward_list""",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchall()
    if (
        len(primary) != 1
        or primary[0]["reward_id"] != policy["reward_id"]
        or primary[0]["primary_result_index"] != 0
        or primary[0]["native_text"] != ""
    ):
        raise ValueError(
            "Simple result requires one original unconditional primary entry"
        )
    if participant["instance_id"] != event["instance_id"]:
        raise ValueError("Simple result participant belongs to another instance")
    actual = db.execute(
        """SELECT p.*,e.entitlement_id,e.earned_at_ms,
        i.profile_key AS event_profile,i.version AS event_version
        FROM environmental_participants p JOIN environmental_event_instances i USING(instance_id)
        LEFT JOIN environmental_reward_entitlements e USING(instance_id,character_id,account_id)
        WHERE p.instance_id=%s AND p.character_id=%s""",
        (event["instance_id"], participant["character_id"]),
    ).fetchone()
    if (
        actual is None
        or actual["account_id"] != participant["account_id"]
        or (actual["event_profile"], actual["event_version"]) != key
    ):
        raise ValueError("Simple result lacks its actual owned participant")
    if actual["completed_at_ms"] is None or actual["eligible"] is not True:
        return None
    if (
        actual["entitlement_id"] is None
        or actual["earned_at_ms"] != actual["completed_at_ms"]
        or participant.get("completed_at_ms") != actual["completed_at_ms"]
    ):
        raise ValueError("Simple resource completion lacks its durable entitlement")
    if (
        type(now_ms) is not int
        or type(actual["completed_at_ms"]) is not int
        or not 0 <= actual["completed_at_ms"] <= now_ms
    ):
        raise ValueError("Simple result completion clock is invalid")
    rows = db.execute(
        "SELECT kind,reference,quantity,source_authority FROM environmental_reward_components "
        "WHERE entitlement_id=%s ORDER BY ordinal",
        (actual["entitlement_id"],),
    ).fetchall()
    if any(
        type(row["source_authority"]) is not str
        or not row["source_authority"].strip()
        or type(row["quantity"]) is not int
        or not 0 < row["quantity"] < 2**31
        or row["kind"] not in ("xp", "item", "kamas")
        or (
            row["kind"] == "item"
            and (type(row["reference"]) is not int or row["reference"] <= 0)
        )
        or (row["kind"] != "item" and row["reference"] is not None)
        for row in rows
    ):
        raise ValueError("Simple resource entitlement lacks grant authority")
    earned = sorted(
        [(row["kind"], row["reference"], row["quantity"]) for row in rows],
        key=lambda row: row[0],
    )
    if earned != _components(primary[0]):
        raise ValueError(
            "Simple resource entitlement differs from original base rewards"
        )
    publication = db.execute(
        "SELECT challenge_id,secondary_id FROM environmental_profile_publication "
        "WHERE profile_key=%s AND version=%s",
        key,
    ).fetchone()
    if publication is None:
        return None
    if publication["challenge_id"] != policy["native_scenario_id"]:
        raise ValueError("Simple result differs from its native publication")
    progress = storage._progress(
        db,
        event,
        participant["character_id"]
        if policy["parameter_mode"] == "personal_progress"
        else None,
    )
    if any(type(value) is not int or value < 0 for value in progress.values()):
        raise ValueError("Simple result lacks durable nonnegative progress")
    score = sum(progress.values())
    if score >= 2**31:
        raise ValueError("Simple resource progress exceeds native winnerScore bounds")
    return dict(
        profile_key=key[0],
        version=key[1],
        instance_id=event["instance_id"],
        account_id=actual["account_id"],
        character_id=actual["character_id"],
        source_authority=policy["source_authority"],
        mapping_authority=policy["mapping_authority"],
        parameter_authority=policy["parameter_authority"],
        result_parameter=score,
        challenge_id=publication["challenge_id"],
        secondary_id=publication["secondary_id"],
        primary_reward_count=1,
        primary_reward_index=0,
        name=None,
        display_rank=0,
        terminal_state="completed",
        terminal_at_ms=actual["completed_at_ms"],
    )
