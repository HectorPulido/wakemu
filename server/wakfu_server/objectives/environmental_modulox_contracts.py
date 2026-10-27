"""Source-bound Modulox contracts over the shared recurring victory backend.

The consumer uses an explicitly reconstructed final-room/competitive-level rule,
not a recovered original server event publisher. Character modulation at victory
comes from the admitted actor and immutable encounter difficulty, never the
character's current selected build or later level.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb


POLICY = "wakemu.modulox-native-adjusted-final-room-v1"
REWARD_POLICY = "native17-frozen-real-level-no-subscription"
_OFFER = re.compile(
    r"GetRealLevel\(\)>=(\d+)andGetAchievementCategoryRunningCount\((\d+)\)<1"
    r"andGetAchievementCategoryCount\((\d+)\)==GetAchievementCategoryCanBeResetCount\((\d+)\)"
)


def _transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Modulox requires an owned transaction")


def _positive(value, name):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid Modulox " + name)
    return value


def offer_parameters(criterion):
    """Parse the complete original category offer, preserving raw text elsewhere."""
    if type(criterion) is not str:
        raise ValueError("Missing original Modulox offer criterion")
    match = _OFFER.fullmatch(re.sub(r"[ \t\r\n]+", "", criterion))
    if match is None:
        raise ValueError("Unsupported original Modulox offer criterion")
    level, first, second, third = map(int, match.groups())
    if not 1 <= level <= 245 or first <= 0 or first != second or first != third:
        raise ValueError("Inconsistent original Modulox category/minimum")
    return level, first


def load(db, row, targets, rewards, *, attest):
    """Validate a source version and return its normalized target authority."""
    _transaction(db)
    key = (row["definition_id"], row["version"])
    authority = db.execute(
        "SELECT * FROM recurring_modulox_authority "
        "WHERE definition_id=%s AND version=%s",
        key,
    ).fetchone()
    if (
        authority is None
        or row["interpretation_policy"] != POLICY
        or authority["interpretation_policy"] != POLICY
        or authority["reward_policy"] != REWARD_POLICY
        or type(row["period_ms"]) is not int
        or row["period_ms"] != 86400000
        or row["cooldown_ms"] != 0
        or row["required_distinct"] != 1
        or len(targets) != 1
        or authority["boss_reference"] != targets[0]["boss_reference"]
        or row["minimum_level"] != authority["minimum_level"]
        or len(rewards) != 2
        or {r["native_type"] for r in rewards} != {5, 17}
    ):
        raise ValueError("Modulox lacks its exact recurring target/reward authority")
    order = authority["native_reward_order"]
    if (
        not isinstance(order, (list, tuple))
        or len(order) != 2
        or any(type(identity) is not int for identity in order)
        or len(set(order)) != 2
        or set(order) != {r["reward_id"] for r in rewards}
    ):
        raise ValueError("Modulox original reward order differs from its source")
    for reward in rewards:
        _positive(reward["reward_id"], "reward identity")
        amount = _positive(reward["amount"], "reward parameter")
        if (
            amount >= 2**31
            or type(reward["native_flag"]) is not bool
            or (
                reward["native_type"] == 5
                and (type(reward["reference"]) is not int or reward["reference"] <= 0)
            )
            or (reward["native_type"] == 17 and reward["reference"] is not None)
        ):
            raise ValueError("Invalid original Modulox reward payload")
    minimum, category = offer_parameters(authority["offer_criterion"])
    original_minimum = re.fullmatch(
        r"GetRealLevel\(\) >= ([0-9]+)", authority["original_eligibility_criterion"]
    )
    if (
        original_minimum is None
        or authority["original_activation_criterion"]
        != f'IsAchievementRunning({row["definition_id"]})'
        or max(minimum, int(original_minimum[1])) != authority["minimum_level"]
        or category != authority["category_id"]
    ):
        raise ValueError("Modulox offer disagrees with its category/minimum")
    _positive(authority["offer_node_id"], "offer node")
    _positive(authority["offer_choice_id"], "offer choice")
    for field in (
        "offer_source_sha256",
        "native_catalog_revision",
        "monsters_sha256",
        "plan_sha256",
    ):
        if (
            type(authority[field]) is not str
            or re.fullmatch("[0-9a-f]{64}", authority[field]) is None
        ):
            raise ValueError("Missing Modulox source digest")
    for field in ("minimum_level_authority", "source_authority"):
        if type(authority[field]) is not str or not authority[field].strip():
            raise ValueError("Missing Modulox interpretation authority")
    target_level = authority["target_effective_level"]
    objective_level = re.search(
        r" at level ([0-9]+)$", authority["original_objective_en"]
    )
    if (
        type(target_level) is not int
        or not 1 <= target_level <= 245
        or objective_level is None
        or int(objective_level[1]) != target_level
    ):
        raise ValueError("Invalid original Modulox target level")
    from wakfu_server import native_catalog

    from wakfu_server.native_catalog_compatibility import require_source_revision

    require_source_revision(
        authority["native_catalog_revision"], (authority["monsters_path"],)
    )
    attest_authority(db, authority, attest=attest)
    return dict(authority)


def _native_boss_authority(db, authority, *, kind="modulox"):
    key = (authority["definition_id"], authority["version"])
    tables = {
        "modulox": (
            "recurring_modulox_native_boss_authority",
            "recurring_modulox_native_boss_occurrences",
        ),
        "daily": (
            "recurring_hunter_native_target_authority",
            "recurring_hunter_native_target_occurrences",
        ),
    }
    if kind not in tables:
        raise ValueError("Unknown typed recurring native boss authority")
    authority_table, occurrences_table = tables[kind]
    child = db.execute(
        "SELECT * FROM " + authority_table + " WHERE definition_id=%s AND version=%s",
        key,
    ).fetchone()
    if child is None:
        return None
    if (
        child["boss_reference"] != authority["boss_reference"]
        or child["native_property_id"] != 43
        or type(child["native_property_id"]) is not int
        or type(child["source_authority"]) is not str
        or not child["source_authority"].strip()
        or type(child["provenance"]) is not dict
        or sha256(
            json.dumps(
                child["provenance"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest()
        != child["proof_sha256"]
    ):
        raise ValueError("Invalid immutable Modulox native boss authority")
    rows = db.execute(
        "SELECT * FROM "
        + occurrences_table
        + " WHERE definition_id=%s AND version=%s ORDER BY monster_index",
        key,
    ).fetchall()
    if (
        not rows
        or any(
            type(r["monster_index"]) is not int
            or r["monster_index"] < 0
            or r["planned_role"]
            not in (
                ("boss", "monster", "unknown")
                if kind == "daily"
                else ("monster", "unknown")
            )
            or type(r["count"]) is not int
            or r["count"] <= 0
            for r in rows
        )
        or len({r["monster_index"] for r in rows}) != len(rows)
    ):
        raise ValueError("Invalid exact Modulox native boss occurrences")
    return tuple((r["monster_index"], r["planned_role"], r["count"]) for r in rows)


def attest_authority(db, authority, *, attest, kind="modulox"):
    occurrences = _native_boss_authority(db, authority, kind=kind)
    if kind == "daily" and occurrences is None:
        raise ValueError("Native daily source requires its exact typed authority")
    options = (
        {}
        if occurrences is None
        else dict(native_property_id=43, target_occurrences=occurrences)
    )
    return attest(
        authority["native_catalog_revision"],
        authority["monsters_path"],
        authority["monsters_sha256"],
        authority["boss_reference"],
        authority["route_key"],
        authority["route_policy_version"],
        authority["plan_sha256"],
        authority["dungeon_definition_id"],
        authority["final_room_order"],
        **options,
    )


def native_boss_targets(
    db, fight, event, authority, room, *, room_order, kind="modulox"
):
    """Derive this contract's target from native43, never rewrite encounter roles."""
    _transaction(db)
    occurrences = _native_boss_authority(db, authority, kind=kind)
    if occurrences is None:
        if kind == "daily":
            raise ValueError("Native daily target requires its exact typed authority")
        return None
    from .environmental_recurring_storage import _daily_source

    attest_authority(db, authority, attest=_daily_source, kind=kind)
    boss = authority["boss_reference"]
    if (
        room is None
        or room_order != authority["final_room_order"]
        or room.get("order") != room_order
        or event.get("fight_id") != fight.id
        or event.get("completed_dungeon_id") != authority["dungeon_definition_id"]
    ):
        return frozenset()
    actual = tuple(
        (index, row["role"], row["count"])
        for index, row in enumerate(room["monsters"])
        if row["ref_id"] == boss
    )
    if actual != occurrences:
        return frozenset()
    actual_dead = sum(
        1 for identity, reference in event["original_monsters"] if reference == boss
    )
    if actual_dead != sum(count for _, _, count in occurrences):
        return frozenset()
    return frozenset((boss,))


def accept_category(db, character, authority, *, now_ms):
    """Evaluate original category running/reset gates after synchronization.

    The caller skips durable acceptance replays before invoking this gate. The
    normalized category inventory includes unsupported targets too; never reduce
    GetAchievementCategoryCount to the executable target subset.
    """
    _transaction(db)
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid Modulox category clock")
    from wakfu_server.achievements import storage

    state = storage.load_locked(db, character["id"])
    category_source = db.execute(
        "SELECT * FROM recurring_modulox_category_sources " "WHERE category_id=%s",
        (authority["category_id"],),
    ).fetchone()
    if category_source is None or any(
        category_source[k] != authority[k]
        for k in (
            "offer_node_id",
            "offer_choice_id",
            "offer_criterion",
            "offer_source_sha256",
        )
    ):
        raise ValueError(
            "Modulox category offer source differs from the accepted contract"
        )
    members = db.execute(
        "SELECT * FROM recurring_modulox_category_members "
        "WHERE category_id=%s ORDER BY definition_id",
        (authority["category_id"],),
    ).fetchall()
    if (
        not members
        or len(members) != category_source["expected_members"]
        or authority["definition_id"] not in {m["definition_id"] for m in members}
    ):
        raise ValueError("Incomplete original Modulox category inventory")
    running, completed = set(state["running"]), set(state["completed"])
    dates = state["completion_dates"]
    for member in members:
        identity, anchor, period = (
            member["definition_id"],
            member["anchor_ms"],
            member["period_ms"],
        )
        if (
            type(anchor) is not int
            or anchor < 0
            or period != 86400000
            or now_ms < anchor
        ):
            raise ValueError("Invalid original Modulox category recurrence")
        if identity in running:
            return False
        date = dates.get(str(identity))
        if identity in completed and (type(date) is not int or date <= 0):
            raise ValueError("Completed Modulox lacks its original completion date")
        if date is None or date == 0:
            continue  # Original never-activated completion date is zero.
        if type(date) is not int or date < anchor or date > now_ms:
            raise ValueError("Invalid durable Modulox completion date")
        if (date - anchor) // period == (now_ms - anchor) // period:
            return False
    return True


def victory(db, character, fight, authority):
    """Return eligibility and persist one immutable authentic modulation proof."""
    _transaction(db)
    actor = fight.actors.get(character["id"])
    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
        or actor is None
        or actor.controlled is not True
        or actor.owner_id != character["account_id"]
        or actor.team != fight.winner
        or getattr(actor, "pve_withdrawn", False)
    ):
        return False
    level = actor.effective_level
    if type(level) is not int or level <= 0:
        raise ValueError("Missing actual Modulox actor effective level")
    target = authority["target_effective_level"]
    if type(target) is not int or not 1 <= target <= 245:
        raise ValueError("Invalid Modulox target effective level")
    row = db.execute(
        """SELECT e.instance_id,e.room_order,e.status AS encounter_status,e.result,
        i.definition_id,p.team,f.status AS fight_status,f.fight_kind,
        d.selection_revision,d.snapshot
        FROM dungeon_room_encounters e JOIN dungeon_instances i USING(instance_id)
        JOIN dungeon_encounter_difficulties d ON d.fight_id=e.fight_id AND d.instance_id=e.instance_id
        JOIN combat_fights f ON f.id=e.fight_id
        JOIN combat_fight_participants p ON p.fight_id=f.id AND p.character_id=%s AND p.account_id=%s
        JOIN dungeon_instance_members m ON m.instance_id=e.instance_id AND m.party_id=i.party_id
          AND m.character_id=p.character_id
        WHERE e.fight_id=%s""",
        (character["id"], character["account_id"], fight.id),
    ).fetchone()
    if (
        row is None
        or row["fight_status"] != "finished"
        or row["fight_kind"] != "pve"
        or row["team"] != fight.winner
        or row["encounter_status"] != "victory"
        or not isinstance(row["result"], dict)
        or row["result"].get("completed") is not True
        or row["definition_id"] != authority["dungeon_definition_id"]
        or row["room_order"] != authority["final_room_order"]
    ):
        return False
    snapshot = row["snapshot"]
    if (
        type(snapshot) is not dict
        or snapshot.get("instance_id") != row["instance_id"]
        or snapshot.get("selection_revision") != row["selection_revision"]
    ):
        raise ValueError("Modulox immutable encounter difficulty identity changed")
    cap = snapshot.get("competitive_max_level")
    if (
        snapshot.get("competitive") is not True
        or type(cap) is not int
        or cap != target
        or level > target
    ):
        return False
    proof = dict(
        definition_id=authority["definition_id"],
        version=authority["version"],
        fight_id=fight.id,
        character_id=character["id"],
        account_id=character["account_id"],
        instance_id=row["instance_id"],
        dungeon_definition_id=row["definition_id"],
        effective_level=level,
        target_effective_level=target,
        selection_revision=row["selection_revision"],
        difficulty_snapshot=deepcopy(snapshot),
    )
    db.execute(
        """INSERT INTO recurring_modulox_victory_proofs
        (definition_id,version,fight_id,character_id,account_id,instance_id,dungeon_definition_id,
         effective_level,target_effective_level,selection_revision,difficulty_snapshot)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
        (
            *[
                proof[k]
                for k in (
                    "definition_id",
                    "version",
                    "fight_id",
                    "character_id",
                    "account_id",
                    "instance_id",
                    "dungeon_definition_id",
                    "effective_level",
                    "target_effective_level",
                    "selection_revision",
                )
            ],
            Jsonb(proof["difficulty_snapshot"]),
        ),
    )
    stored = db.execute(
        "SELECT * FROM recurring_modulox_victory_proofs "
        "WHERE definition_id=%s AND version=%s AND fight_id=%s AND character_id=%s",
        (authority["definition_id"], authority["version"], fight.id, character["id"]),
    ).fetchone()
    if stored is None or any(stored[k] != value for k, value in proof.items()):
        raise ValueError("Modulox victory evidence changed on replay")
    return True
