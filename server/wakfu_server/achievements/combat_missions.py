"""Progress explicitly configured missions from authoritative combat results.

Bindings must be curated and published by an operator; no mappings are inferred
from names or packets during combat. This adapter only processes non-recurring
missions under an explicit reconstructed acceptance policy, and consumes the fight service's validated event.
"""

from . import native_effective_eligibility

from copy import deepcopy

SETTING = "combat_mission_bindings_v1"


def validate(document, definitions):
    if (
        not isinstance(document, dict)
        or document.get("schema") != SETTING
        or not isinstance(document.get("bindings"), list)
    ):
        raise ValueError("Invalid combat mission configuration")
    seen = set()
    for row in document["bindings"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid combat mission binding")
        expected = {
            "quest_id",
            "objective_id",
            "kind",
            "target_id",
            "count",
            "evidence",
        }
        if row.get("kind") == "victory":
            expected = (expected - {"target_id"}) | {"minimum_level"}
        if row.get("kind") == "boss":
            expected = expected | {"dungeon_id"}
        if "acceptance" in row:
            expected = expected | {"acceptance"}
        if (
            set(row) != expected
            or row.get("kind") not in ("monster", "dungeon", "boss", "victory")
            or row.get("acceptance", "on_matching_victory")
            not in ("on_matching_victory", "explicit")
            or any(
                type(row.get(k)) is not int or row[k] <= 0 or row[k] >= 2**31
                for k in ("quest_id", "objective_id", "count")
            )
            or (
                row.get("kind") != "victory"
                and (
                    type(row.get("target_id")) is not int
                    or not 0 < row["target_id"] < 2**31
                )
            )
            or (
                row.get("kind") == "victory"
                and (
                    type(row.get("minimum_level")) is not int
                    or not 1 <= row["minimum_level"] <= 2**15 - 1
                    or row.get("acceptance") != "explicit"
                    or row.get("count") != 1
                )
            )
            or (
                row.get("kind") == "boss"
                and (
                    type(row.get("dungeon_id")) is not int
                    or row["dungeon_id"] <= 0
                    or row["dungeon_id"] >= 2**31
                )
            )
            or not isinstance(row.get("evidence"), str)
            or not row["evidence"].strip()
            or row["objective_id"] in seen
        ):
            raise ValueError("Invalid or duplicate combat mission binding")
        seen.add(row["objective_id"])
        definition = definitions.get(row["quest_id"])
        if (
            not isinstance(definition, dict)
            or definition.get("d") != row["quest_id"]
            or definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or definition.get("cjU") != 0
            or definition.get("cjL") != 0
            or definition.get("getDuration") != 0
            or not isinstance(definition.get("cjJ"), list)
        ):
            raise ValueError("Combat mission is missing or recurring/timed")
        objectives = [o for o in definition["cjJ"] if o.get("d") == row["objective_id"]]
        if len(objectives) != 1 or objectives[0].get("ckf"):
            raise ValueError("Missing objective or unsupported native variable")
        if row["kind"] == "victory" and (
            type(definition.get("cjP")) is not int
            or row["minimum_level"] < definition["cjP"]
        ):
            raise ValueError("Victory objective level is below native quest level")
    return document["bindings"]


def advance(state, event, rules, definitions, *, character, store, now_ms, counts):
    """Plan updates for validated rules and a server-authenticated fight event."""
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server import dungeon_criteria
    from .mission_progress import advance_objective
    from .combat_mission_activation import _level_matches

    result = deepcopy(state)
    counter = dict(counts)
    if any(
        type(k) is not int or k <= 0 or type(v) is not int or v < 0
        for k, v in counter.items()
    ):
        raise ValueError("Invalid mission combat counts")
    breeds = event.get("original_breeds", ())
    if not isinstance(breeds, (tuple, list)) or any(
        type(x) is not int or x <= 0 for x in breeds
    ):
        raise ValueError("Invalid authoritative fight breeds")
    grants, completed_objectives, completed_quests = [], [], []
    for binding in rules:
        quest_id, objective_id = binding["quest_id"], binding["objective_id"]
        if quest_id not in result["running"] or objective_id in result["objectives"]:
            continue
        if not _level_matches(binding, character):
            continue
        definition = definitions[quest_id]
        objective = next(o for o in definition["cjJ"] if o["d"] == objective_id)
        queries = queries_from_state(result)
        try:
            eligible = all(
                dungeon_criteria.evaluate(
                    store, expr, character=character, queries=queries, now_ms=now_ms
                )
                for expr in (
                    native_effective_eligibility.criterion(definition),
                    objective["ckc"],
                    objective["cke"],
                )
            )
        except (ValueError, NotImplementedError, KeyError):
            # An unimplemented predicate must not prevent unrelated missions.
            continue
        if not eligible:
            continue
        if binding["kind"] == "victory":
            amount = int(bool(breeds))
        elif binding["kind"] == "monster":
            amount = breeds.count(binding["target_id"])
        elif binding["kind"] == "boss":
            amount = (
                breeds.count(binding["target_id"])
                if event.get("completed_dungeon_id") == binding["dungeon_id"]
                else 0
            )
        else:
            amount = int(event.get("completed_dungeon_id") == binding["target_id"])
        if not amount:
            continue
        old = counter.get(objective_id, 0)
        count = min(binding["count"], old + amount)
        counter[objective_id] = count
        if count < binding["count"]:
            continue
        result, intents, objectives, completed = advance_objective(
            result,
            definition,
            objective_id,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        grants.extend(intents)
        completed_objectives.extend(objectives)
        completed_quests.extend(completed)
    return result, grants, completed_objectives, completed_quests, counter


def load(db, *, event=None):
    """Load only matching published rules and pinned definitions, when given a fight."""
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return None
    document = row["value"]
    revision = document.get("revision") if isinstance(document, dict) else None
    if not isinstance(revision, str) or len(revision) != 64:
        raise ValueError("Invalid combat mission metadata revision")
    if document.get("schema") != SETTING or not isinstance(
        document.get("bindings"), list
    ):
        raise ValueError("Invalid combat mission configuration")
    if event is not None:
        from .combat_mission_activation import _matches

        # The publication was fully validated at install. Avoid reading every
        # definition for ordinary fights with no matching mission target.
        bindings = [row for row in document["bindings"] if _matches(row, event)]
        if not bindings:
            return [], {}
        document = {**document, "bindings": bindings}
    ids = sorted({x["quest_id"] for x in document["bindings"]})
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions "
        "WHERE revision=%s AND definition_id=ANY(%s)",
        (revision, ids),
    ).fetchall()
    definitions = {x["definition_id"]: x["data"]["native"] for x in rows}
    return validate(document, definitions), definitions


def stage(db, store, character, event):
    """Record an immutable eligible fight before isolated mission settlement.

    Call only on the original fresh authenticated fight. The caller commits
    this receipt with combat even if processing the receipt later fails.
    """
    from psycopg.types.json import Jsonb
    from . import storage
    from .combat_mission_activation import auto_accept, _matches, _level_matches

    publication = load(db, event=event)
    if publication is None:
        return False
    rules, definitions = publication
    matched = [r for r in rules if _matches(r, event)]
    if not matched:
        return False
    before = storage.load_locked(db, character["id"])
    now_ms = int(store.now().timestamp() * 1000)
    accepted, started = auto_accept(
        before,
        event,
        matched,
        definitions,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    queries = queries_from_state(accepted)
    eligible = []
    for rule in matched:
        if (
            rule["quest_id"] not in accepted["running"]
            or rule["objective_id"] in accepted["objectives"]
            or not _level_matches(rule, character)
        ):
            continue
        definition = definitions[rule["quest_id"]]
        objective = next(
            item for item in definition["cjJ"] if item["d"] == rule["objective_id"]
        )
        try:
            allowed = all(
                dungeon_criteria.evaluate(
                    store,
                    expression,
                    character=character,
                    queries=queries,
                    now_ms=now_ms,
                )
                for expression in (
                    native_effective_eligibility.criterion(definition),
                    objective["ckc"],
                    objective["cke"],
                )
            )
        except (ValueError, NotImplementedError, KeyError):
            continue
        if allowed:
            eligible.append(rule)
    if not eligible:
        return False
    quest_ids = {r["quest_id"] for r in eligible}
    payload = {
        "event": event,
        "rules": eligible,
        "definitions": {str(identity): definitions[identity] for identity in quest_ids},
        "started": [identity for identity in started if identity in quest_ids],
        "occurred_at_ms": now_ms,
    }
    row = db.execute(
        "INSERT INTO character_combat_mission_receipts(character_id,fight_id,payload) "
        "VALUES (%s,%s,%s) ON CONFLICT(character_id,fight_id) DO NOTHING RETURNING fight_id",
        (character["id"], event["fight_id"], Jsonb(payload)),
    ).fetchone()
    if row is None:
        raise ValueError("Duplicate fresh combat mission receipt")
    return True


def settle(db, store, character, event):
    """Process only an existing receipt; replay never creates retroactive work."""
    from . import rewards, storage, wire
    from .mission_progress import auto_track

    row = db.execute(
        "SELECT payload,completed_at FROM character_combat_mission_receipts "
        "WHERE character_id=%s AND fight_id=%s FOR UPDATE",
        (character["id"], event["fight_id"]),
    ).fetchone()
    if row is None or row["completed_at"] is not None:
        return []
    payload = row["payload"]
    if payload["event"] != event:
        raise ValueError("Combat mission receipt does not match the fight")
    definitions = {
        int(identity): value for identity, value in payload["definitions"].items()
    }
    rules = payload["rules"]
    before = storage.load_locked(db, character["id"])
    now_ms = payload["occurred_at_ms"]
    accepted = deepcopy(before)
    for identity in payload["started"]:
        if (
            identity not in accepted["running"]
            and identity not in accepted["completed"]
        ):
            accepted["running"] = sorted(set(accepted["running"]) | {identity})
            auto_track(accepted, identity)
    running_rules = [r for r in rules if r["quest_id"] in accepted["running"]]
    rows = db.execute(
        "SELECT objective_id,count FROM character_combat_mission_counts WHERE character_id=%s",
        (character["id"],),
    ).fetchall()
    counts = {r["objective_id"]: r["count"] for r in rows}
    after, intents, objectives, completed, updated = advance(
        accepted,
        event,
        running_rules,
        definitions,
        character=character,
        store=store,
        now_ms=now_ms,
        counts=counts,
    )
    for oid, count in updated.items():
        if counts.get(oid) == count:
            continue
        db.execute(
            "INSERT INTO character_combat_mission_counts(character_id,objective_id,count) "
            "VALUES (%s,%s,%s) ON CONFLICT(character_id,objective_id) "
            "DO UPDATE SET count=EXCLUDED.count",
            (character["id"], oid, count),
        )
    for identity, reward in intents:
        rewards.validate(reward)
        storage.claim_reward(db, character["id"], identity, "once", reward["d"], reward)
    if after != before:
        storage.store(db, character["id"], after)
    db.execute(
        "UPDATE character_combat_mission_receipts SET completed_at=CURRENT_TIMESTAMP "
        "WHERE character_id=%s AND fight_id=%s AND completed_at IS NULL",
        (character["id"], event["fight_id"]),
    )
    # Announce acceptance first even if the same fight finishes the quest.
    packets = wire.changes(
        character["id"], before, accepted, [], [], now_ms
    ) + wire.changes(character["id"], accepted, after, objectives, completed, now_ms)
    if completed:
        from . import mission_toolkit

        packets.extend(
            mission_toolkit.settle_completions(db, store, character, completed)
        )
    return packets
