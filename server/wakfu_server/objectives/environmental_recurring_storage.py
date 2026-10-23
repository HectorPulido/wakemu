"""Owned recurring hunter acceptance, durable victories and native rewards.

All operations share the caller's transaction. Source contracts never activate
quests: acceptance requires a stored, source-qualified original NPC/share event.
Original story, Almanax and guild daily quests are outside this module.
"""
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import struct

from wakfu_server.achievements import storage, wire
from wakfu_server.achievements.service import _owner, drain_rewards
from .environmental_recurring_contracts import (
    HunterContract,
    NativeReward,
    accept_hunter,
)

DAILY_POLICY = "wakemu.daily-hunter-public-final-room-v1"
DAILY_NATIVE_POLICY = "wakemu.daily-hunter-native-objective-final-room-v1"
MODULOX_POLICY = "wakemu.modulox-native-adjusted-final-room-v1"


@lru_cache(maxsize=256)
def _daily_source(
    revision,
    path,
    source_sha,
    boss,
    route,
    version,
    plan_sha,
    dungeon,
    final_order,
    *,
    native_property_id=None,
    target_occurrences=()
):
    """Attest immutable published records without loading a monster catalog."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.dungeon_runtime_config import canonical_hash

    monster = native_catalog.record(DATA_ROOT / path, "monsters", boss)
    with native_catalog._database().connection() as db:
        document = db.execute(
            "SELECT sha256 FROM native_catalog_documents "
            "WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()
        configuration = db.execute(
            "SELECT configuration FROM dungeon_runtime_configurations "
            "WHERE route_key=%s AND policy_version=%s",
            (route, version),
        ).fetchone()
    if (
        monster is None
        or monster.get("ref") != boss
        or document is None
        or document["sha256"] != source_sha
        or configuration is None
    ):
        raise ValueError("Daily hunter original target source is unavailable")
    plan = configuration["configuration"]["compiled_plan"]
    rooms = plan["rooms"]
    final = max(rooms, key=lambda row: row["order"]) if rooms else None
    if (
        canonical_hash(plan) != plan_sha
        or plan["definition_id"] != dungeon
        or final is None
        or final["order"] != final_order
    ):
        raise ValueError("Daily hunter final-room authority changed")
    if native_property_id is None:
        if target_occurrences or {
            row["ref_id"] for row in final["monsters"] if row["role"] == "boss"
        } != {boss}:
            raise ValueError("Daily hunter final-room boss authority changed")
    else:
        actual = tuple(
            (index, row["role"], row["count"])
            for index, row in enumerate(final["monsters"])
            if row["ref_id"] == boss
        )
        properties = monster.get("raw_visual_arrays", {}).get("csc", [])
        if (
            type(native_property_id) is not int
            or native_property_id != 43
            or not isinstance(properties, (list, tuple))
            or 43 not in properties
            or not target_occurrences
            or actual != target_occurrences
        ):
            raise ValueError(
                "Modulox native boss property or target occurrences changed"
            )
    return True


def _milliseconds(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Recurring receipt requires an authoritative timestamp")
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000


def _now(db):
    return db.execute(
        "SELECT floor(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000)::bigint AS now_ms"
    ).fetchone()["now_ms"]


def _positive(value, name):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("Invalid recurring " + name)
    return value


def _load(db, definition_id, version=None):
    _positive(definition_id, "definition")
    if version is None:
        row = db.execute(
            "SELECT * FROM recurring_hunter_contracts WHERE definition_id=%s "
            "ORDER BY version DESC LIMIT 1",
            (definition_id,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT * FROM recurring_hunter_contracts WHERE definition_id=%s AND version=%s",
            (definition_id, version),
        ).fetchone()
    if row is None:
        raise ValueError("Missing qualified recurring hunter contract")
    key = (row["definition_id"], row["version"])
    targets = db.execute(
        "SELECT * FROM recurring_hunter_targets WHERE definition_id=%s AND version=%s "
        "ORDER BY boss_reference",
        key,
    ).fetchall()
    rewards = db.execute(
        "SELECT * FROM recurring_hunter_rewards WHERE definition_id=%s AND version=%s "
        "ORDER BY reward_id",
        key,
    ).fetchall()
    if (
        len(targets) < row["required_distinct"]
        or not rewards
        or type(row["period_ms"]) is not int
        or row["period_ms"] not in (86400000, 604800000)
        or row["cooldown_ms"] != 0
    ):
        raise ValueError("Incomplete immutable recurring hunter contract")
    if row["period_ms"] == 86400000:
        if row["interpretation_policy"] == MODULOX_POLICY:
            from .environmental_modulox_contracts import load

            authority = load(db, row, targets, rewards, attest=_daily_source)
        elif row["interpretation_policy"] == DAILY_NATIVE_POLICY:
            from .environmental_modulox_contracts import attest_authority

            authority = db.execute(
                "SELECT * FROM recurring_hunter_native_target_authority "
                "WHERE definition_id=%s AND version=%s",
                key,
            ).fetchone()
            if (
                authority is None
                or authority["interpretation_policy"] != DAILY_NATIVE_POLICY
                or authority["reward_policy"] != "fixed-native-parameter-no-booster"
                or authority["minimum_level_authority"]
                != "wakemu-reconstruction:original-native-category-bracket-minimum"
                or authority["minimum_level"] != row["minimum_level"]
                or len(targets) != 1
                or authority["boss_reference"] != targets[0]["boss_reference"]
                or row["required_distinct"] != 1
                or len(rewards) != 2
                or {r["native_type"] for r in rewards} != {5, 6}
                or len(authority["native_reward_order"]) != 2
                or len(set(authority["native_reward_order"])) != 2
                or set(authority["native_reward_order"])
                != {r["reward_id"] for r in rewards}
            ):
                raise ValueError(
                    "Daily hunter lacks its exact original native objective authority"
                )
            attest_authority(db, authority, attest=_daily_source, kind="daily")
        else:
            authority = db.execute(
                "SELECT * FROM recurring_hunter_target_authority "
                "WHERE definition_id=%s AND version=%s",
                key,
            ).fetchone()
            if (
                authority is None
                or len(targets) != 1
                or row["required_distinct"] != 1
                or row["interpretation_policy"] != DAILY_POLICY
                or authority["interpretation_policy"] != DAILY_POLICY
                or authority["reward_policy"] != "fixed-native-parameter-no-booster"
                or authority["minimum_level"] != row["minimum_level"]
                or authority["boss_reference"] != targets[0]["boss_reference"]
                or len(rewards) != 2
                or set(authority["native_reward_order"])
                != {r["reward_id"] for r in rewards}
            ):
                raise ValueError(
                    "Daily hunter lacks its source-derived target authority"
                )
        from wakfu_server import native_catalog

        # This mutable publication check must run even when the immutable
        # record/configuration attestation below is already cached.
        if native_catalog.release() != authority["native_catalog_revision"]:
            raise ValueError("Daily hunter source differs from the published catalog")
        if row["interpretation_policy"] not in (MODULOX_POLICY, DAILY_NATIVE_POLICY):
            _daily_source(
                authority["native_catalog_revision"],
                authority["monsters_path"],
                authority["monsters_sha256"],
                authority["boss_reference"],
                authority["route_key"],
                authority["route_policy_version"],
                authority["plan_sha256"],
                authority["dungeon_definition_id"],
                authority["final_room_order"],
            )
        row = dict(row, daily_target_authority=dict(authority))
        by_id = {r["reward_id"]: r for r in rewards}
        rewards = [by_id[identity] for identity in authority["native_reward_order"]]
    contract = HunterContract(
        row["definition_id"],
        row["objective_id"],
        row["minimum_level"],
        tuple(t["boss_reference"] for t in targets),
        tuple(t["variable_name"] for t in targets),
        row["required_distinct"],
        row["anchor_ms"],
        row["period_ms"],
        row["cooldown_ms"],
        tuple(
            NativeReward(
                {5: "item", 6: "player_xp", 17: "player_xp_per_mob_xp"}[
                    r["native_type"]
                ],
                r["reference"],
                r["amount"],
                r["native_flag"],
            )
            for r in rewards
        ),
        row["interpretation_policy"],
    )
    return row, contract, rewards


def _remove_current(state, contract):
    identity = contract.definition_id
    for key in ("running", "completed", "tracking"):
        state[key] = [i for i in state[key] if i != identity]
    state["objectives"] = [i for i in state["objectives"] if i != contract.objective_id]
    state["completion_dates"].pop(str(identity), None)


def synchronize(db, store, character):
    """Reset only this family's expired journal projections; keep all receipts."""
    _owner(db, character)
    now_ms = _now(db)
    rows = db.execute(
        "SELECT a.* FROM recurring_hunter_acceptances a JOIN recurring_hunter_contracts c "
        "USING(definition_id,version) WHERE a.character_id=%s AND a.expired_at_ms IS NULL "
        "AND c.anchor_ms+(a.period_index+1)*c.period_ms<=%s FOR UPDATE OF a",
        (character["id"], now_ms),
    ).fetchall()
    if not rows:
        return []
    before = storage.load_locked(db, character["id"])
    after = deepcopy(before)
    resets = []
    for row in rows:
        _, contract, _ = _load(db, row["definition_id"], row["version"])
        _remove_current(after, contract)
        resets.append(
            (13205, struct.pack(">qi", character["id"], contract.definition_id))
        )
        db.execute(
            "UPDATE recurring_hunter_acceptances SET expired_at_ms=%s WHERE character_id=%s "
            "AND definition_id=%s AND period_index=%s",
            (now_ms, character["id"], row["definition_id"], row["period_index"]),
        )
    if after != before:
        storage.store(db, character["id"], after)
    return resets + wire.changes(character["id"], before, after, [], [], now_ms)


def accept_from_receipt(db, store, character, definition_id, *, receipt_key):
    """Consume an actual server acceptance after its native action is validated.

    There is deliberately no client packet decoder or automatic acceptance. The
    original producer writes the achievement event in this same transaction and
    its exact source must have a separately recovered immutable source binding.
    """
    _owner(db, character)
    if type(receipt_key) is not str or not 1 <= len(receipt_key) <= 200:
        raise ValueError("Missing native recurring acceptance receipt")
    _positive(definition_id, "definition")
    receipt = db.execute(
        "SELECT payload,created_at FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], receipt_key),
    ).fetchone()
    if receipt is None:
        raise ValueError("Missing durable owned native acceptance")
    fact = receipt["payload"]
    if (
        type(fact) is not dict
        or fact.get("kind") != "native_recurring_acceptance"
        or fact.get("definition_id") != definition_id
        or type(fact.get("definition_id")) is not int
        or fact.get("source_kind") not in ("npc_dialogue", "native_share")
    ):
        raise ValueError("Unqualified original recurring acceptance event")
    accepted_at = _milliseconds(receipt["created_at"])
    replay = db.execute(
        "SELECT definition_id,version,period_index FROM recurring_hunter_acceptances "
        "WHERE character_id=%s AND acceptance_event_key=%s",
        (character["id"], receipt_key),
    ).fetchone()
    if replay is not None and replay["definition_id"] != definition_id:
        raise ValueError("Recurring acceptance identity changed")
    choices = db.execute(
        "SELECT version FROM recurring_hunter_daily_choices "
        "WHERE definition_id=%s AND utc_day=%s",
        (definition_id, accepted_at // 86400000),
    ).fetchall()
    if len(choices) > 1:
        raise ValueError("Ambiguous daily hunter selected source version")
    # A newer published contract cannot replace today's issued offer or the
    # immutable version already consumed by this owner's acceptance receipt.
    pinned_version = (
        replay["version"]
        if replay is not None
        else choices[0]["version"]
        if choices
        else None
    )
    row, contract, _ = _load(db, definition_id, pinned_version)
    reference = _positive(fact.get("source_reference"), "acceptance source")
    action_id = _positive(fact.get("action_id"), "acceptance action")
    qualified = db.execute(
        "SELECT 1 FROM recurring_hunter_acceptance_sources WHERE definition_id=%s AND version=%s "
        "AND source_kind=%s AND source_reference=%s AND action_id=%s",
        (definition_id, row["version"], fact["source_kind"], reference, action_id),
    ).fetchone()
    if qualified is None:
        raise ValueError("Original hunter acceptance producer has not been recovered")
    owner = db.execute(
        "SELECT level FROM characters WHERE id=%s AND account_id=%s",
        (character["id"], character["account_id"]),
    ).fetchone()
    now_ms = _now(db)
    if accepted_at > now_ms or contract.period(accepted_at) != contract.period(now_ms):
        raise ValueError("Acceptance requires its current owned native period")
    if contract.period_ms == 86400000:
        from .environmental_daily_selection import chosen_for_receipt

        choice = chosen_for_receipt(
            db,
            category_id=row["daily_target_authority"]["category_id"],
            occurred_at_ms=accepted_at,
            definition_id=definition_id,
            version=row["version"],
        )
        if choice is None:
            raise ValueError("Daily hunter is not the selected server-wide offer")
    if replay is not None:
        if (
            replay["definition_id"] != definition_id
            or replay["version"] != row["version"]
        ):
            raise ValueError("Recurring acceptance identity changed")
        return dict(
            applied=False,
            definition_id=definition_id,
            period=replay["period_index"],
            packets=synchronize(db, store, character),
        )
    if (
        fact.get("real_level") != owner["level"]
        or type(fact.get("real_level")) is not int
    ):
        raise ValueError("Acceptance requires its authoritative real level")
    progress = accept_hunter(
        contract,
        character_id=character["id"],
        real_level=owner["level"],
        at_ms=accepted_at,
        acceptance_receipt_key=receipt_key,
    )
    period = progress.acceptance.period
    packets = synchronize(db, store, character)
    prior = db.execute(
        "SELECT * FROM recurring_hunter_acceptances WHERE character_id=%s AND definition_id=%s "
        "AND period_index=%s FOR UPDATE",
        (character["id"], definition_id, period),
    ).fetchone()
    if prior is not None:
        return dict(
            applied=False, definition_id=definition_id, period=period, packets=packets
        )
    if row["interpretation_policy"] == MODULOX_POLICY:
        from .environmental_modulox_contracts import accept_category

        if not accept_category(
            db, character, row["daily_target_authority"], now_ms=now_ms
        ):
            raise ValueError("Modulox category has an active or non-resettable quest")
    before = storage.load_locked(db, character["id"])
    if definition_id in before["running"] or definition_id in before["completed"]:
        raise ValueError(
            "Existing journal state lacks this recurring acceptance authority"
        )
    db.execute(
        "INSERT INTO recurring_hunter_acceptances(character_id,definition_id,version,period_index,"
        "account_id,accepted_at_ms,real_level,acceptance_event_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            character["id"],
            definition_id,
            row["version"],
            period,
            character["account_id"],
            accepted_at,
            owner["level"],
            receipt_key,
        ),
    )
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {definition_id})
    storage.store(db, character["id"], after)
    packets += wire.changes(character["id"], before, after, [], [], accepted_at)
    return dict(
        applied=True, definition_id=definition_id, period=period, packets=packets
    )


def activation_dates(db, character_id):
    """Native journal bootstrap dates for current actually accepted periods."""
    rows = db.execute(
        "SELECT a.definition_id,a.accepted_at_ms FROM recurring_hunter_acceptances a "
        "JOIN recurring_hunter_contracts c USING(definition_id,version) "
        "WHERE a.character_id=%s AND a.expired_at_ms IS NULL "
        "AND c.anchor_ms+a.period_index*c.period_ms<=floor(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000) "
        "AND c.anchor_ms+(a.period_index+1)*c.period_ms>floor(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)*1000)",
        (character_id,),
    ).fetchall()
    return {r["definition_id"]: r["accepted_at_ms"] for r in rows}


def settle_combat(db, store, character, fight, event):
    """Reuse the original winning final-room achievement receipt, never a kill request."""
    _owner(db, character)
    admitted = db.execute(
        "SELECT 1 FROM recurring_hunter_acceptances WHERE character_id=%s "
        "AND expired_at_ms IS NULL LIMIT 1",
        (character["id"],),
    ).fetchone()
    if admitted is None:
        return dict(packets=[], completed=[], credited=[])
    receipt = db.execute(
        "SELECT payload,created_at FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], "fight:" + str(fight.id)),
    ).fetchone()
    if receipt is None or receipt["payload"] != event:
        raise ValueError(
            "Recurring hunter requires its actual achievement settlement receipt"
        )
    from wakfu_server.achievements.service import _event

    # Revalidate durable participant, original dead roster and completed dungeon.
    original = [
        {"id": identity, "ref": reference}
        for identity, reference in event["original_monsters"]
    ]
    if _event(db, character, fight, original) != event:
        raise ValueError("Recurring hunter settlement source changed")
    packets = synchronize(db, store, character)
    if event["completed_dungeon_id"] is None:
        return dict(packets=packets, completed=[], credited=[])
    run = db.execute(
        "SELECT r.rooms,e.room_order FROM dungeon_room_encounters e "
        "JOIN dungeon_room_runs r ON r.instance_id=e.instance_id "
        "WHERE e.fight_id=%s AND e.status='victory' AND r.status='completed'",
        (fight.id,),
    ).fetchone()
    if run is None:
        return dict(packets=packets, completed=[], credited=[])
    room = next((r for r in run["rooms"] if r["order"] == run["room_order"]), None)
    bosses = (
        set()
        if room is None
        else {r["ref_id"] for r in room["monsters"] if r["role"] == "boss"}
    )
    defeated = bosses & {reference for _, reference in event["original_monsters"]}
    occurred = _milliseconds(receipt["created_at"])
    now_ms = _now(db)
    rows = db.execute(
        "SELECT * FROM recurring_hunter_acceptances WHERE character_id=%s "
        "AND expired_at_ms IS NULL AND completed_at_ms IS NULL FOR UPDATE",
        (character["id"],),
    ).fetchall()
    before = storage.load_locked(db, character["id"])
    after = deepcopy(before)
    completed, objectives, credited = [], [], []
    for accepted in rows:
        identity, period = accepted["definition_id"], accepted["period_index"]
        source, contract, rewards = _load(db, identity, accepted["version"])
        if (
            occurred < accepted["accepted_at_ms"]
            or contract.period(occurred) != period
            or contract.period(now_ms) != period
        ):
            continue
        if identity not in before["running"]:
            raise ValueError("Accepted recurring hunter lacks its journal state")
        if (
            contract.period_ms == 86400000
            and event["completed_dungeon_id"]
            != source["daily_target_authority"]["dungeon_definition_id"]
        ):
            continue
        contract_defeated = defeated
        if source["interpretation_policy"] in (MODULOX_POLICY, DAILY_NATIVE_POLICY):
            from .environmental_modulox_contracts import native_boss_targets

            native_kind = (
                "daily"
                if source["interpretation_policy"] == DAILY_NATIVE_POLICY
                else "modulox"
            )
            native_targets = native_boss_targets(
                db,
                fight,
                event,
                source["daily_target_authority"],
                room,
                room_order=run["room_order"],
                kind=native_kind,
            )
            if native_targets is not None:
                contract_defeated = native_targets
        if source["interpretation_policy"] == MODULOX_POLICY:
            from .environmental_modulox_contracts import victory

            if not contract_defeated.intersection(contract.boss_references):
                continue
            if not victory(db, character, fight, source["daily_target_authority"]):
                continue
        for boss in sorted(contract_defeated & set(contract.boss_references)):
            inserted = db.execute(
                "INSERT INTO recurring_hunter_victories(character_id,definition_id,period_index,version,"
                "fight_id,boss_reference,occurred_at_ms,source_event_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING boss_reference",
                (
                    character["id"],
                    identity,
                    period,
                    accepted["version"],
                    fight.id,
                    boss,
                    occurred,
                    "fight:" + str(fight.id),
                ),
            ).fetchone()
            if inserted is not None:
                credited.append(
                    dict(definition_id=identity, boss_reference=boss, fight_id=fight.id)
                )
        count = db.execute(
            "SELECT COUNT(DISTINCT boss_reference)::integer AS total FROM recurring_hunter_victories "
            "WHERE character_id=%s AND definition_id=%s AND period_index=%s",
            (character["id"], identity, period),
        ).fetchone()["total"]
        if count < contract.required_distinct:
            continue
        db.execute(
            "UPDATE recurring_hunter_acceptances SET completed_at_ms=%s WHERE character_id=%s "
            "AND definition_id=%s AND period_index=%s",
            (occurred, character["id"], identity, period),
        )
        after["running"] = [i for i in after["running"] if i != identity]
        after["completed"] = sorted(set(after["completed"]) | {identity})
        after["objectives"] = sorted(set(after["objectives"]) | {contract.objective_id})
        after["completion_dates"][str(identity)] = occurred
        after["recent"].append(dict(id=identity, date_ms=occurred))
        completed.append(identity)
        objectives.append(contract.objective_id)
        for reward in rewards:
            payload = dict(
                d=reward["reward_id"],
                aeV=reward["native_type"],
                ckk=reward["native_flag"],
                ckl=(
                    [reward["reference"], reward["amount"]]
                    if reward["native_type"] == 5
                    else [reward["amount"]]
                ),
            )
            prefix = (
                "modulox-daily:"
                if source["interpretation_policy"] == MODULOX_POLICY
                else "hunter-daily:"
                if contract.period_ms == 86400000
                else "hunter-weekly:"
            )
            cycle = prefix + str(period)
            storage.enqueue_reward(
                db, character["id"], identity, cycle, str(reward["reward_id"]), payload
            )
    if completed:
        after["recent"] = after["recent"][-255:]
        after["tracking"] = [i for i in after["tracking"] if i not in completed]
        storage.store(db, character["id"], after)
        packets += wire.changes(
            character["id"], before, after, objectives, completed, now_ms
        )
    packets += drain_rewards(db, store, character)
    return dict(packets=packets, completed=completed, credited=credited)
