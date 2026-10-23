"""Explicit Wakemu grants and native-list mapping for original resource ranks.

Display base XP/items are adopted by a declared policy, without boosters. Client
reward predicates identify bands; they do not recover original server payouts or
choose a new winner count. Missing policies retain the legacy reward path.
"""
import re

from . import environmental_storage as storage


CONTRACT = "wakemu.original-resource-rank-bands-base-rewards.v1"
DESTROY_CONTRACT = "wakemu.original-destroy-rank-bands-base-rewards.v1"
GROUP_CONTRACT = "wakemu.original-group-rank-bands-base-rewards.v1"
_RANK = re.compile(
    r'ListContains\(GetUser\(\), GetPlayerInRankRange\(([1-9][0-9]*), ([1-9][0-9]*), "(nbResourcePlayer|nbMobPlayer)", False\)\)'
)


def parse_native_reward_band(text, *, variable="nbResourcePlayer"):
    """Return (inclusive_min,inclusive_max), or None for the exact blank fallback."""
    if variable not in ("nbResourcePlayer", "nbMobPlayer"):
        raise ValueError("Unsupported original rank counter")
    if type(text) is not str:
        raise ValueError("Missing original resource reward predicate")
    if text == "":
        return None
    match = _RANK.fullmatch(text)
    if match is None:
        raise ValueError("Unsupported original resource reward predicate")
    if match.group(3) != variable:
        raise ValueError("Original rank predicate uses another entity counter")
    lower, upper = map(int, match.groups()[:2])
    if not lower <= upper <= 32767:
        raise ValueError("Invalid original resource reward rank bounds")
    return lower, upper


def compile_native_reward_bands(rewards, *, variable="nbResourcePlayer"):
    """Compile joined original raw/display rows, retaining actual primary indices.

    Input is the selected scenario's original primary list (SQL275 view joined
    to raw native_text). Unknown predicates, ambiguous indices and overlaps fail.
    This function creates no profile and supplies no runtime eligibility policy.
    """
    rows = list(rewards)
    if any(
        type(r.get("primary_result_index")) is not int
        or type(r.get("reward_id")) is not int
        or r["reward_id"] <= 0
        for r in rows
    ):
        raise ValueError("Original resource reward identity requires exact integers")
    if len({r["reward_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate original resource reward identity")
    rows.sort(key=lambda r: r["primary_result_index"])
    if not rows or [r["primary_result_index"] for r in rows] != list(range(len(rows))):
        raise ValueError(
            "Original resource primary indices are ambiguous or incomplete"
        )
    result, fallback, ranges = [], 0, []
    for row in rows:
        if row.get("primary_reward_list") is not True:
            raise ValueError("Resource band requires an original primary reward entry")
        bounds = parse_native_reward_band(row["native_text"], variable=variable)
        if bounds is None:
            fallback += 1
        else:
            if any(
                bounds[0] <= upper and lower <= bounds[1] for lower, upper in ranges
            ):
                raise ValueError("Original resource reward rank ranges overlap")
            ranges.append(bounds)
        result.append(
            dict(
                reward_id=row["reward_id"],
                primary_reward_index=row["primary_result_index"],
                rank_min=None if bounds is None else bounds[0],
                rank_max=None if bounds is None else bounds[1],
            )
        )
    if fallback != 1:
        raise ValueError("Original resource reward list requires one blank fallback")
    return result


def _destroy_source(db, key, policy, source, profile):
    if (
        source is None
        or source["native_type"] != 5
        or source["family"] != "destroy_monster_action"
        or source["native_subtype"]
        != {"solo": 1, "race": 2, "competitive": 3, "collaborative": 4}[profile["mode"]]
    ):
        raise ValueError("Destroy results require the exact original action3 scenario")
    qualified = db.execute(
        "SELECT 1 FROM environmental_profile_destroy_ui "
        "WHERE profile_key=%s AND version=%s AND source_key=%s AND native_scenario_id=%s",
        (*key, policy["source_key"], policy["native_scenario_id"]),
    ).fetchone()
    if qualified is None:
        raise ValueError("Missing qualified native destruction result policy")


def _selection(db, event, profile, participant):
    storage._transaction(db)
    key = (profile["profile_key"], profile["version"])
    if key != (event["profile_key"], event["version"]):
        raise ValueError("Ranked reward event differs from profile")
    policy = db.execute(
        "SELECT * FROM environmental_profile_ranked_reward_policy "
        "WHERE profile_key=%s AND version=%s",
        key,
    ).fetchone()
    if policy is None:
        return None
    resource = profile["family"] == "resource_collect"
    group = profile["family"] in ("monster_defeat", "group_defeat")
    destroy = profile["family"] == "monster_destroy"
    expected_contract = (
        CONTRACT if resource else DESTROY_CONTRACT if destroy else GROUP_CONTRACT
    )
    if (
        not profile["sealed"]
        or not (resource or group or destroy)
        or profile["mode"] not in ("competitive", "race")
        or policy["policy_contract"] != expected_contract
        or policy["native_scenario_id"] != profile["native_scenario_id"]
        or policy["eligibility_contract"] not in ("all_eligible", "ranked_winners")
    ):
        raise ValueError("Invalid frozen original resource reward policy")
    source = db.execute(
        "SELECT family,native_type,native_subtype FROM environmental_native_scenarios "
        "WHERE source_key=%s AND scenario_id=%s",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchone()
    if (
        source is None
        or (resource and source["family"] != "resource_interaction")
        or (
            group
            and (
                source["family"] != "group_template"
                or source["native_type"] not in (6, 7, 8)
                or source["native_subtype"]
                != {"race": 2, "competitive": 3}[profile["mode"]]
            )
        )
    ):
        raise ValueError(
            "Ranked resource rewards require their original resource source"
        )
    if destroy:
        _destroy_source(db, key, policy, source, profile)
    for field in ("source_authority", "grant_authority", "parameter_authority"):
        if not isinstance(policy[field], str) or not policy[field].strip():
            raise ValueError("Missing declared resource reward authority")
    rows = db.execute(
        """SELECT b.*,r.native_text,d.item_reference,d.item_quantity,
        d.base_xp,d.kamas,d.primary_reward_list,d.primary_result_index
        FROM environmental_profile_ranked_reward_bands b
        JOIN environmental_native_rewards_raw r ON r.source_key=b.source_key
          AND r.scenario_id=b.native_scenario_id AND r.reward_id=b.reward_id
        JOIN environmental_native_reward_display d ON d.source_key=r.source_key
          AND d.scenario_id=r.scenario_id AND d.reward_id=r.reward_id
        WHERE b.profile_key=%s AND b.version=%s ORDER BY b.primary_reward_index""",
        key,
    ).fetchall()
    count = db.execute(
        "SELECT count(*) AS n FROM environmental_native_reward_display "
        "WHERE source_key=%s AND scenario_id=%s AND primary_reward_list",
        (policy["source_key"], policy["native_scenario_id"]),
    ).fetchone()["n"]
    if (
        not rows
        or len(rows) != count
        or [r["primary_reward_index"] for r in rows] != list(range(count))
    ):
        raise ValueError("Incomplete original primary resource reward list")
    fallback, bands = [], []
    for row in rows:
        if (
            row["source_key"] != policy["source_key"]
            or row["native_scenario_id"] != policy["native_scenario_id"]
            or not row["primary_reward_list"]
            or row["primary_result_index"] != row["primary_reward_index"]
        ):
            raise ValueError("Original resource reward list identity changed")
        parsed = parse_native_reward_band(
            row["native_text"],
            variable="nbResourcePlayer" if resource else "nbMobPlayer",
        )
        expected = (
            None
            if row["rank_min"] is None and row["rank_max"] is None
            else (row["rank_min"], row["rank_max"])
        )
        if parsed != expected:
            raise ValueError(
                "Declared resource rank band differs from original predicate"
            )
        if parsed is None:
            fallback.append(row)
        else:
            bands.append(row)
    if len(fallback) != 1 or any(
        a["rank_min"] <= b["rank_max"] and b["rank_min"] <= a["rank_max"]
        for i, a in enumerate(bands)
        for b in bands[i + 1 :]
    ):
        raise ValueError("Ambiguous resource rank reward bands")
    actual = db.execute(
        """SELECT r.*,p.account_id,p.eligible,c.name
        FROM environmental_event_rankings r
        JOIN environmental_participants p USING(instance_id,character_id)
        JOIN characters c ON c.id=p.character_id AND c.account_id=p.account_id
        WHERE r.instance_id=%s AND r.character_id=%s""",
        (event["instance_id"], participant["character_id"]),
    ).fetchone()
    if (
        actual is None
        or actual["account_id"] != participant["account_id"]
        or participant["instance_id"] != event["instance_id"]
    ):
        raise ValueError("Ranked rewards require the durable participant ranking")
    # The evaluator must explicitly mark all qualifying contributors rewarded
    # for all_eligible. This reader never manufactures eligibility or a rank.
    if not actual["eligible"] or not actual["rewarded"]:
        return policy, None, actual, count
    rank = actual["display_rank"]
    if type(rank) is not int or not 1 <= rank <= 32767:
        raise ValueError("Invalid durable resource display rank")
    chosen = next(
        (r for r in bands if r["rank_min"] <= rank <= r["rank_max"]), fallback[0]
    )
    return policy, chosen, actual, count


def reward_components(db, event, profile, participant):
    """Return explicit normalized components, [], or None for the legacy path."""
    selected = _selection(db, event, profile, participant)
    if selected is None:
        return None
    policy, row, _, _ = selected
    if row is None:
        return []
    components = []
    for kind, reference, quantity in (
        ("xp", None, row["base_xp"]),
        ("item", row["item_reference"], row["item_quantity"]),
        ("kamas", None, row["kamas"]),
    ):
        if type(quantity) is not int or quantity < 0 or quantity >= 2**31:
            raise ValueError(
                "Original resource reward exceeds normalized runtime bounds"
            )
        if quantity == 0:
            continue
        if kind == "item" and (type(reference) is not int or reference <= 0):
            raise ValueError("Original resource item quantity lacks a reference")
        components.append(
            dict(
                ordinal=len(components),
                kind=kind,
                reference=reference,
                quantity=quantity,
                source_authority=policy["grant_authority"],
            )
        )
    return components


def native_result_mapping(db, event, profile, participant):
    """Project the selected installed primary-list index, never the progress score."""
    selected = _selection(db, event, profile, participant)
    if selected is None or selected[1] is None:
        return None
    policy, row, actual, count = selected
    publication = db.execute(
        "SELECT * FROM environmental_profile_publication "
        "WHERE profile_key=%s AND version=%s",
        (profile["profile_key"], profile["version"]),
    ).fetchone()
    if (
        publication is None
        or publication["challenge_id"] != policy["native_scenario_id"]
    ):
        raise ValueError("Ranked resource result lacks its native publication")
    winner = db.execute(
        """SELECT r.score,c.name FROM environmental_event_rankings r
        JOIN environmental_participants p USING(instance_id,character_id)
        JOIN characters c ON c.id=p.character_id AND c.account_id=p.account_id
        WHERE r.instance_id=%s ORDER BY r.position LIMIT 1""",
        (event["instance_id"],),
    ).fetchone()
    if winner is None:
        raise ValueError("Native winner display requires its durable ranking")
    if policy["result_parameter_mode"] == "winner_score":
        result_parameter = winner["score"]
    elif policy["result_parameter_mode"] == "declared_constant":
        result_parameter = policy["result_parameter"]
    else:
        raise ValueError("Unsupported native winner-score display mapping")
    if (
        type(result_parameter) is not int
        or not -(2**31) <= result_parameter < 2**31
    ):
        raise ValueError("Native winner score exceeds its signed integer wire bound")
    return dict(
        profile_key=profile["profile_key"],
        version=profile["version"],
        instance_id=event["instance_id"],
        account_id=actual["account_id"],
        character_id=participant["character_id"],
        name=winner["name"],
        source_authority=policy["source_authority"],
        mapping_authority=policy["grant_authority"],
        parameter_authority=policy["parameter_authority"],
        result_parameter=result_parameter,
        challenge_id=publication["challenge_id"],
        secondary_id=publication["secondary_id"],
        primary_reward_count=count,
        primary_reward_index=row["primary_reward_index"],
        display_rank=actual["display_rank"],
        terminal_state="completed",
        terminal_at_ms=actual["finalized_at_ms"],
    )
