"""Reviewed eligibility over exact native complex quest-loot rows.

The client exposes only ``hasComplexCriteria``; original server expressions
are absent. Contracts therefore declare reconstruction explicitly. Each grant
requires its actual owner-only encounter, native roster and native consumer.
Native chances, quantities and the ordinary drop/delivery engine stay intact.
"""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "reviewed-owned-quest-complex-loot-v1"
SOURCE = Path(__file__).with_name("native_quest_complex_loot.json")


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def contracts():
    value = json.loads(SOURCE.read_text())
    if value.get("schema") != SCHEMA or not isinstance(value.get("contracts"), list):
        raise ValueError("Unqualified native quest loot contracts")
    seen = set()
    for row in value["contracts"]:
        if (
            set(row)
            != {
                "id",
                "quest_id",
                "map_id",
                "monster_reference",
                "item_reference",
                "native_row_sha256",
                "consumer",
                "evidence",
            }
            or not isinstance(row["id"], str)
            or not row["id"]
            or row["id"] in seen
            or any(
                type(row[k]) is not int or row[k] <= 0
                for k in ("quest_id", "map_id", "monster_reference", "item_reference")
            )
            or not isinstance(row["native_row_sha256"], str)
            or len(row["native_row_sha256"]) != 64
            or not row["evidence"]
        ):
            raise ValueError("Invalid reviewed native quest loot contract")
        seen.add(row["id"])
    return value["contracts"]


@lru_cache(maxsize=1)
def monster_references():
    """Cheap producer index; ordinary fights never read quest loot authority."""
    return frozenset(row["monster_reference"] for row in contracts())


def validate_native(row, native_rows):
    from wakfu_server import generic_transports

    selected = [
        r for r in native_rows if r.get("reference_id") == row["item_reference"]
    ]
    if (
        len(selected) != 1
        or digest(selected[0]) != row["native_row_sha256"]
        or selected[0].get("complex_criteria") is not True
        or selected[0].get("is_loot_table") is not False
        or selected[0].get("conditions") != []
    ):
        raise ValueError("Reviewed quest loot differs from its exact native row")
    consumer = row["consumer"]
    if consumer.get("kind") == "native_dialogue_payment":
        validate_dialogue_consumer(row)
        return
    if consumer.get("kind") == "native_item_merge":
        validate_merge_consumer(row)
        return
    if set(consumer) != {"object_id", "destination_id", "quantity"}:
        raise ValueError("Malformed native quest loot consumer")
    if any(type(value) is not int or value <= 0 for value in consumer.values()):
        raise ValueError("Invalid native quest loot consumer identity")
    source = generic_transports.source(row["map_id"], consumer["object_id"])
    targets = (
        []
        if source is None
        else [
            d
            for d in source["destinations"]
            if d["destination_id"] == consumer["destination_id"]
        ]
    )
    if (
        len(targets) != 1
        or targets[0].get("item_reference") != row["item_reference"]
        or targets[0].get("cyW") != consumer["quantity"]
    ):
        raise ValueError("Reviewed quest key lost its actual native payment consumer")


def validate_merge_consumer(row, contexts=None):
    """Pin an existing native merge; never grant its output from combat loot."""
    from wakfu_server.simple_item_actions import native_use_contexts

    consumer = row["consumer"]
    if (
        set(consumer)
        != {
            "kind",
            "action_id",
            "quantity",
            "output_reference",
            "output_quantity",
            "unfinished_objective_id",
            "native_source_sha256",
        }
        or consumer.get("kind") != "native_item_merge"
        or any(
            type(consumer[k]) is not int or consumer[k] <= 0
            for k in (
                "action_id",
                "quantity",
                "output_reference",
                "output_quantity",
                "unfinished_objective_id",
            )
        )
    ):
        raise ValueError("Malformed native merge quest loot consumer")
    source = (native_use_contexts() if contexts is None else contexts).get(
        consumer["action_id"]
    )
    if (
        not isinstance(source, dict)
        or digest(source) != consumer["native_source_sha256"]
        or source.get("action_id") != consumer["action_id"]
        or source.get("item_ref") != row["item_reference"]
        or source.get("native_class") != "bHS"
        or source.get("type") != "MERGE_ITEMS"
        or source.get("action_parameters")
        != [str(consumer["quantity"]), str(consumer["output_reference"])]
        or consumer["output_quantity"] != 1
    ):
        raise ValueError("Native merge quest loot consumer source changed")
    # This consumer grammar proves both original literal input and world gates.
    # More complex native merge predicates need their own reviewed adapter.
    import ast

    try:
        expression = ast.parse(source["action_criterion"], mode="eval").body
    except (KeyError, TypeError, SyntaxError):
        raise ValueError("Native merge consumer lacks its original criterion") from None
    expected = ast.parse(
        f'GetItemQuantity({row["item_reference"]}) >= {consumer["quantity"]} '
        f'and GetInstanceId() == {row["map_id"]}',
        mode="eval",
    ).body
    if ast.dump(expression) != ast.dump(expected):
        raise ValueError("Native merge consumer item or map criterion changed")
    return source


def contract_eligible(row, state):
    """Only the declared merge consumer adds an earning quest-state gate.

    Existing keys and dialogue deliveries retain their ordinary content-visitor
    policy. The native merge still owns the actual item debit and output.
    """
    if row["consumer"].get("kind") != "native_item_merge":
        return True
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    authority = queries_from_state(state)
    return authority["IsAchievementRunning"](row["quest_id"]) and not authority[
        "IsAchievementObjectiveComplete"
    ](row["consumer"]["unfinished_objective_id"])


def dialogue_consumer_source(consumer, native):
    """Select literal native source records, without inferring dialogue edges."""
    speakers = [s for s in native["speakers"] if s["ref"] == consumer["reference_id"]]
    nodes = [n for n in native["nodes"] if n["id"] == consumer["node_id"]]
    if len(speakers) != 1 or len(nodes) != 1:
        raise ValueError("Quest loot dialogue consumer lost its native speaker/node")
    actions = [a for a in speakers[0]["actions"] if a["id"] == consumer["action_id"]]
    choices = [c for c in nodes[0]["choices"] if c["id"] == consumer["choice_id"]]
    if len(actions) != 1 or len(choices) != 1:
        raise ValueError("Quest loot dialogue consumer lost its native action/choice")
    return dict(reference_id=speakers[0]["ref"], action=actions[0], node=nodes[0])


def validate_dialogue_consumer(row, native=None):
    """Qualify an explicit native running-quest and real item-payment branch.

    This establishes a physical loot consumer, not a reconstructed conversation
    graph or permission to complete an objective. The NPC payment adapter still
    owns admission, actual inventory debit and objective settlement.
    """
    from wakfu_server import npc_dialogue
    from wakfu_server.achievements.conversation_authoring import objective_predicates

    consumer = row["consumer"]
    if (
        set(consumer)
        != {
            "kind",
            "reference_id",
            "action_id",
            "node_id",
            "choice_id",
            "objective_id",
            "quantity",
            "native_source_sha256",
        }
        or consumer["kind"] != "native_dialogue_payment"
    ):
        raise ValueError("Malformed native dialogue quest loot consumer")
    if any(
        type(consumer[k]) is not int or consumer[k] <= 0
        for k in (
            "reference_id",
            "action_id",
            "node_id",
            "choice_id",
            "objective_id",
            "quantity",
        )
    ):
        raise ValueError("Invalid native dialogue quest loot consumer identity")
    source = dialogue_consumer_source(
        consumer, npc_dialogue.catalog() if native is None else native
    )
    node = source["node"]
    choice = next(c for c in node["choices"] if c["id"] == consumer["choice_id"])
    if digest(source) != consumer["native_source_sha256"] or choice["type"] not in (
        7,
        8,
    ):
        raise ValueError("Native dialogue quest loot consumer source changed")
    expression = " && ".join(
        f"({value})"
        for value in (node.get("criteria", ""), choice.get("criteria", ""))
        if value.strip()
    )
    _, payment = objective_predicates(
        expression,
        row["quest_id"],
        {consumer["objective_id"]},
        payment=True,
        single_objective=True,
    )
    if payment != (row["item_reference"], consumer["quantity"]):
        raise ValueError("Native dialogue quest loot consumer payment changed")


def encounter_policy(configuration):
    """Reuse either actual owned archetype without inventing quest objectives."""
    from wakfu_server.achievements import owned_quest_encounters
    from wakfu_server import owned_story_controller

    selected = owned_quest_encounters.policy(configuration)
    if selected is not None:
        return selected
    story = owned_story_controller.policy(configuration)
    if story is None:
        return None
    identity = story.get("admission", {}).get("quest_id")
    if type(identity) is not int or identity <= 0:
        return None
    if any(
        configuration.get(key, {}).get("asset_map_id") != story["map_id"]
        for key in ("topology", "compiled_plan")
    ):
        raise ValueError("Owned story loot asset differs from its pinned controller")
    rooms = configuration.get("compiled_plan", {}).get("rooms", [])
    if len(rooms) != 1 or rooms[0].get("order") != 1:
        return None
    roster = []
    for monster in rooms[0].get("monsters", []):
        if monster.get("role") != "monster" or any(
            type(monster.get(key)) is not int or monster[key] <= 0
            for key in ("ref_id", "count")
        ):
            return None
        roster.append(dict(reference=monster["ref_id"], count=monster["count"]))
    if not roster:
        return None
    return dict(quest_id=identity, roster=roster)


def permission(db, fight_id, character_id, *, fight=None, original_monsters=None):
    """Build authority from the pinned encounter, never from client loot input."""
    from wakfu_server import combat_drops, dungeon_runtime_config
    from wakfu_server.achievements import owned_quest_encounters

    encounter = db.execute(
        "SELECT e.*,i.context_route_key,i.context_policy_version,i.start_map_id,"
        "p.account_id,p.team FROM dungeon_room_encounters e JOIN dungeon_instances i USING(instance_id) "
        "JOIN combat_fight_participants p ON p.fight_id=e.fight_id AND p.character_id=%s "
        "WHERE e.fight_id=%s",
        (character_id, fight_id),
    ).fetchone()
    if encounter is None:
        return pool_permission(
            db, fight_id, character_id, fight=fight, original_monsters=original_monsters
        )
    if (
        encounter["encounter_scope"] != "main"
        or encounter["room_order"] != 1
        or encounter["team"] != encounter["player_team"]
    ):
        return None
    configuration = dungeon_runtime_config.pinned_configuration(
        db, encounter["context_route_key"], encounter["context_policy_version"]
    )
    selected = encounter_policy(configuration)
    if selected is None:
        return None
    candidates = [
        r
        for r in contracts()
        if r["quest_id"] == selected["quest_id"]
        and r["map_id"] == encounter["start_map_id"]
    ]
    if not candidates:
        return None
    participants = db.execute(
        "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s",
        (fight_id,),
    ).fetchall()
    membership = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active'",
        (encounter["instance_id"],),
    ).fetchall()
    if participants != [dict(character_id=character_id)] or membership != participants:
        raise ValueError("Quest loot requires its actual single owned encounter")
    # The quest ID identifies the reviewed encounter content, not an assignment
    # gate. A genuine content visitor earns its physical key even when the
    # associated mission is absent or already complete.
    group = db.execute(
        "SELECT g.members FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
        "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=%s",
        (encounter["instance_id"], encounter["room_order"]),
    ).fetchone()
    if group is None:
        raise ValueError("Quest loot has no original native spawn receipt")
    originals = group["members"]
    from collections import Counter

    expected = Counter()
    for member in selected["roster"]:
        expected[member["reference"]] += member["count"]
    if Counter(member["ref"] for member in originals) != expected:
        raise ValueError("Quest loot differs from its pinned original encounter roster")
    if fight is not None:
        deaths = {
            event.get("actor_id")
            for event in fight.events
            if event.get("kind") == "death"
        }
        if (
            fight.id != fight_id
            or fight.phase != "finished"
            or fight.winner != encounter["player_team"]
            or not owned_quest_encounters.qualified_roster(fight, originals, selected)
            or not {member["id"] for member in originals} <= deaths
        ):
            raise ValueError("Quest loot lacks its genuine original-enemy victory")
        if original_monsters is None or {
            (m["id"], m["ref"]) for m in original_monsters
        } != {(m["id"], m["ref"]) for m in originals}:
            raise ValueError(
                "Quest loot differs from the actual admitted original roster"
            )
    else:
        earned = db.execute(
            "SELECT snapshot FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s",
            (fight_id, character_id),
        ).fetchone()
        context = {} if earned is None else earned["snapshot"].get("context", {})
        if context.get("winner_team") != encounter["player_team"]:
            raise ValueError("Quest loot has no durable original winner reward context")
    permissions = []
    for row in candidates:
        if not any(m["ref"] == row["monster_reference"] for m in originals):
            continue
        native_rows = combat_drops.native_drop_catalog()["monsters"][
            row["monster_reference"]
        ]
        validate_native(row, native_rows)
        permissions.append(
            dict(
                contract=row["id"],
                contract_sha256=digest(row),
                monster_reference=row["monster_reference"],
                item_reference=row["item_reference"],
                native_row_sha256=row["native_row_sha256"],
            )
        )
    if not permissions:
        return None
    return dict(
        schema=SCHEMA,
        fight_id=fight_id,
        character_id=character_id,
        instance_id=encounter["instance_id"],
        route_key=encounter["context_route_key"],
        policy_version=encounter["context_policy_version"],
        rows=permissions,
    )


def pool_permission(db, fight_id, character_id, *, fight=None, original_monsters=None):
    """Independent owned groups retain their own actual source/winner receipts."""
    from wakfu_server import owned_quest_pools, combat_drops

    basis = owned_quest_pools.loot_basis(
        db, fight_id, character_id, fight=fight, original_monsters=original_monsters
    )
    if basis is None or not basis["eligible"]:
        return None
    declaration, proof = basis["declaration"], basis["proof"]
    selected = [row for row in contracts() if row["id"] == declaration["loot_contract"]]
    if len(selected) != 1:
        raise ValueError("Quest pool has no exact reviewed native loot contract")
    row = selected[0]
    consumer = row["consumer"]
    consumer_kind = consumer.get("kind")
    unfinished = (
        consumer.get("unfinished_objective_id")
        if consumer_kind == "native_item_merge"
        else consumer.get("objective_id")
    )
    if (
        consumer_kind not in ("native_item_merge", "native_dialogue_payment")
        or row["quest_id"] != declaration["quest_id"]
        or row["item_reference"] != declaration["item_reference"]
        or row["map_id"] != proof["map_id"]
        or unfinished != declaration["unfinished_objective_id"]
        or consumer["quantity"] != declaration["stop_quantity"]
        or not any(
            member["ref"] == row["monster_reference"] for member in proof["members"]
        )
    ):
        raise ValueError("Quest pool differs from its actual native merge consumer")
    rows = [row]
    if consumer_kind == "native_dialogue_payment":
        references = {member["ref"] for member in proof["members"]}
        rows = [
            candidate
            for candidate in contracts()
            if candidate["quest_id"] == row["quest_id"]
            and candidate["map_id"] == row["map_id"]
            and candidate["item_reference"] == row["item_reference"]
            and candidate["consumer"] == consumer
            and candidate["monster_reference"] in references
        ]
        if {candidate["monster_reference"] for candidate in rows} != references or len(
            rows
        ) != len(references):
            raise ValueError(
                "Quest pool lacks each original native dialogue-loot source"
            )
    for candidate in rows:
        validate_native(
            candidate,
            combat_drops.native_drop_catalog()["monsters"][
                candidate["monster_reference"]
            ],
        )
    return dict(
        schema=SCHEMA,
        fight_id=fight_id,
        character_id=character_id,
        instance_id=proof["instance_id"],
        route_key=proof["route_key"],
        policy_version=proof["policy_version"],
        rows=[
            dict(
                contract=candidate["id"],
                contract_sha256=digest(candidate),
                monster_reference=candidate["monster_reference"],
                item_reference=candidate["item_reference"],
                native_row_sha256=candidate["native_row_sha256"],
            )
            for candidate in rows
        ],
    )


def validate_context(value):
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "fight_id",
            "character_id",
            "instance_id",
            "route_key",
            "policy_version",
            "rows",
        }
        or value["schema"] != SCHEMA
    ):
        raise ValueError("Malformed owned quest loot permission")
    if (
        any(
            type(value[k]) is not int or value[k] <= 0
            for k in ("fight_id", "character_id", "instance_id", "policy_version")
        )
        or not isinstance(value["route_key"], str)
        or not value["route_key"]
        or not isinstance(value["rows"], list)
        or not value["rows"]
    ):
        raise ValueError("Invalid owned quest loot permission")
    known = {r["id"]: r for r in contracts()}
    seen = set()
    for row in value["rows"]:
        if not isinstance(row, dict) or set(row) != {
            "contract",
            "contract_sha256",
            "monster_reference",
            "item_reference",
            "native_row_sha256",
        }:
            raise ValueError("Malformed owned quest loot row permission")
        declaration = known.get(row["contract"])
        if (
            declaration is None
            or row["contract"] in seen
            or row["contract_sha256"] != digest(declaration)
            or any(
                row[k] != declaration[k]
                for k in ("monster_reference", "item_reference", "native_row_sha256")
            )
        ):
            raise ValueError("Owned quest loot row is not a reviewed contract")
        seen.add(row["contract"])
    return value


def row_allowed(row, monster_reference, value):
    validate_context(value)
    return any(
        r["monster_reference"] == monster_reference
        and r["item_reference"] == row.get("reference_id")
        and r["native_row_sha256"] == digest(row)
        for r in value["rows"]
    )


def validate_durable(db, fight_id, character_id, value):
    validate_context(value)
    if (
        value["fight_id"] != fight_id
        or value["character_id"] != character_id
        or permission(db, fight_id, character_id) != value
    ):
        raise ValueError("Quest loot permission differs from the actual owned fight")
