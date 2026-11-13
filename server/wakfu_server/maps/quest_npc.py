"""Source-bound, explicitly reconstructed quest conversations.

Ordinary unqualified NPC dialogue remains disabled. Published native quest
markers may establish reconstructed placements, but never a client-authored
objective/completion endpoint or an inferred edge from numerical ordering.
"""
from copy import deepcopy
import struct
import ast
import hashlib
import json
from pathlib import Path
from functools import lru_cache

from wakfu_server.achievements import conversation, storage, wire
from wakfu_server.achievements.service import _owner
from wakfu_server import dungeon_criteria, npc_dialogue
from wakfu_server.dungeon_achievement_authority import queries_from_snapshot, queries

PREFIX = "wakemu.qualified-quest-conversation.v1:"
SETTING = "native_quest_conversation_contracts"
SOURCE_SHA256 = "b188ec25db8dba1e5d7c6cc8859db455d92b915f3fa6adaa065afed843a8d3b4"


@lru_cache(maxsize=1)
def source_contract_digest():
    raw = (
        Path(__file__)
        .with_name("native_quest_conversation_contracts.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Quest conversation source attestation changed")
    return conversation._digest(json.loads(raw))


def publication(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return None
    value = row["value"]
    if conversation._digest(value) != source_contract_digest():
        raise ValueError(
            "Published quest conversation differs from its reviewed source"
        )
    definitions, bindings = conversation.validate_rules(value)
    native = npc_dialogue.catalog()
    nodes = native["node_index"]
    speakers = {s["ref"]: s for s in native["speakers"]}
    identities = set()
    for item in value["placements"]:
        row = item["row"]
        identity = row["actor_id"]
        if (
            identity in identities
            or item["quest_id"] not in definitions
            or not row["provenance"].startswith(PREFIX)
            or item["activation_policy"]
            not in (
                "qualified_native_availability",
                "already_running",
                "explicit_choice",
            )
            or row["reference_id"] not in speakers
        ):
            raise ValueError("Invalid reconstructed quest NPC publication")
        identities.add(identity)
        anchor = item.get("interaction_anchor")
        if anchor is not None and (
            type(anchor) is not dict
            or set(anchor) != {"x", "y", "z"}
            or any(type(anchor[key]) is not int for key in ("x", "y", "z"))
            or abs(anchor["x"] - row["x"]) + abs(anchor["y"] - row["y"])
            > row["interaction_range"]
        ):
            raise ValueError("Invalid quest NPC interaction anchor")
        actions = {a["id"] for a in speakers[row["reference_id"]]["actions"]}
        if not set(row["action_ids"]) <= actions:
            raise ValueError("Quest NPC publication contains a nonnative action")
        edges = {}
        for node, choice, target in item["graph"]:
            if (
                node not in nodes
                or target != 0
                and target not in nodes
                or choice not in {c["id"] for c in nodes[node]["choices"]}
                or (node, choice) in edges
            ):
                raise ValueError("Invalid reconstructed native conversation edge")
            edges[node, choice] = target
        running_roots = item.get("running_roots", {})
        if type(running_roots) is not dict or any(
            not str(identity).isdigit()
            or int(identity) not in definitions
            or root not in nodes
            for identity, root in running_roots.items()
        ):
            raise ValueError("Invalid quest NPC running roots")
        reached = {row["dialogue_root"]} | set(running_roots.values())
        while True:
            following = {t for (n, _), t in edges.items() if n in reached and t}
            if following <= reached:
                break
            reached.update(following)
        if any(n not in reached for n, _ in edges):
            raise ValueError("Quest conversation contains a disconnected edge")
        if not any(
            b.reference_id == row["reference_id"]
            and b.quest_id == item["quest_id"]
            and b.placement_sha256 == conversation.placement_signature(row)
            for b in bindings.values()
        ):
            raise ValueError("Quest NPC has no qualified native objective edge")
    # Published periodic delivery edges are explicit local reconstructions.
    for config in value.get("recurring_deliveries", []):
        definition = definitions.get(config.get("quest_id"))
        matches = [
            p
            for p in value["placements"]
            if p["row"]["reference_id"] == config.get("reference_id")
            and config.get("action_id") in p["row"]["action_ids"]
        ]
        if (
            len(matches) != 1
            or definition is None
            or definition.get("cjU", 0) <= 0
            or config.get("cycle_policy") != "fixed_native_anchor_v1"
            or config.get("objective_id") not in {o["d"] for o in definition["cjJ"]}
            or type(config.get("item_reference")) is not int
            or config["item_reference"] <= 0
            or type(config.get("item_quantity")) is not int
            or config["item_quantity"] <= 0
            or not config.get("evidence")
        ):
            raise ValueError("Invalid reconstructed recurring delivery")
        graph = matches[0]["graph"]
        for edge in (
            [config["offer_node"], config["offer_choice"], config["accept_node"]],
            [config["accept_node"], config["accept_choice"], 0],
            [config["delivery_node"], config["delivery_choice"], 0],
        ):
            if edge not in graph:
                raise ValueError("Missing recurring dialogue edge")
        from wakfu_server.achievements.rewards import validate as validate_reward

        for reward in definition["cjK"]:
            validate_reward(reward)
    turnin_keys = set()
    for entry in value.get("turnins", []):
        fields = {
            "reference_id",
            "action_id",
            "node_id",
            "choice_id",
            "item_reference",
            "quantity",
        }
        if (
            type(entry) is not dict
            or set(entry) != fields
            or any(type(entry[key]) is not int or entry[key] <= 0 for key in fields)
        ):
            raise ValueError("Malformed reconstructed item turn-in")
        key = tuple(
            entry[key] for key in ("reference_id", "action_id", "node_id", "choice_id")
        )
        if key not in bindings or key in turnin_keys:
            raise ValueError("Missing or duplicate item turn-in conversation binding")
        turnin_keys.add(key)
    for link in value.get("activation_links", []):
        source, target = link["after_quest"], link["start_quest"]
        if (
            source not in definitions
            or target not in definitions
            or (
                link.get("policy") == "reconstructed_narrative"
                and (
                    not isinstance(link.get("evidence"), str)
                    or not link["evidence"].strip()
                    or target == source
                )
            )
            or (
                link.get("policy") != "reconstructed_narrative"
                and definitions[target]["cjI"].replace(" ", "")
                != f"IsAchievementComplete({source})"
            )
        ):
            raise ValueError(
                "Quest activation link differs from its native prerequisite"
            )
    return value, definitions, bindings


def qualified_placement(row, *, db=None, published=None):
    if row.get("enabled") is not True or not row.get("provenance", "").startswith(
        PREFIX
    ):
        return False
    if published is None:
        if db is None:
            return False
        published = publication(db)
    if published is None:
        return False
    signature = conversation.placement_signature(row)
    return any(
        item["row"]["actor_id"] == row["actor_id"]
        and conversation.placement_signature(item["row"]) == signature
        for item in published[0]["placements"]
    )


def _row(db, actor_id, published):
    row = db.execute(
        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled FOR SHARE",
        (actor_id,),
    ).fetchone()
    if row is None or not qualified_placement(row, published=published):
        raise ValueError("Unavailable qualified quest NPC")
    item = next(
        i for i in published[0]["placements"] if i["row"]["actor_id"] == actor_id
    )
    return row, item


def recognizes(store, opcode, body, session=None):
    if (
        opcode == npc_dialogue.CHOICE_REQUEST
        and session is not None
        and getattr(session, "quest_conversation_actor_id", None) is not None
    ):
        return True
    if opcode == 13222 and len(body) == 16:
        actor_id = struct.unpack_from(">q", body)[0]
    elif opcode == npc_dialogue.OPEN_REQUEST and len(body) == 13:
        actor_id = npc_dialogue.decode_request(opcode, body)["speaker_id"]
    else:
        return False
    with store.connection() as db:
        row = db.execute(
            "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled",
            (actor_id,),
        ).fetchone()
        return row is not None and qualified_placement(row, db=db)


def _criterion(store, character, criterion, authority, *, reset_allowed=None):
    """Bind original exploration-only queries before the shared safe evaluator."""
    from wakfu_server.combat_local_criteria import parse_local_criterion

    class ExplorationQueries(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "CanResetAchievement"
            ):
                if (
                    len(node.args) != 1
                    or node.keywords
                    or not isinstance(node.args[0], ast.Constant)
                    or type(node.args[0].value) is not int
                    or reset_allowed is None
                ):
                    raise ValueError("Missing recurring mission reset authority")
                return ast.copy_location(
                    ast.Constant(bool(reset_allowed(node.args[0].value))), node
                )
            if isinstance(node.func, ast.Name) and node.func.id == "GetInstanceId":
                if (
                    node.args
                    or node.keywords
                    or type(character.get("map_id")) is not int
                ):
                    raise ValueError("Missing native exploration world identity")
                return ast.copy_location(ast.Constant(character["map_id"]), node)
            if isinstance(node.func, ast.Name) and node.func.id == "IsSex":
                if (
                    len(node.args) != 1
                    or node.keywords
                    or not isinstance(node.args[0], ast.Constant)
                    or node.args[0].value not in ("male", "female")
                    or type(character.get("sex")) is not int
                ):
                    raise ValueError("Missing native exploration sex authority")
                expected = 0 if node.args[0].value == "male" else 1
                return ast.copy_location(
                    ast.Constant(character["sex"] == expected), node
                )
            return node

    tree = ExplorationQueries().visit(parse_local_criterion(criterion or "True"))
    return dungeon_criteria.evaluate(
        store,
        ast.unparse(ast.fix_missing_locations(tree)),
        character=character,
        queries=authority,
    )


def _activate(db, store, character, row, definition):
    """Reconstructed producer; the original native availability is preserved."""
    before = storage.load_locked(db, character["id"])
    identity = definition["d"]
    if identity in before["running"] or identity in before["completed"]:
        return []
    authority = queries_from_snapshot(
        {k: before[k] for k in ("running", "completed", "objectives")}
    )
    if not _criterion(store, character, definition["cjI"], authority):
        raise ValueError("Native quest availability is not met")
    fact = dict(
        kind="qualified_native_conversation_activation_v1",
        quest_id=identity,
        speaker_id=row["actor_id"],
        native_definition_sha256=conversation._digest(definition),
    )
    if not storage.record_event(
        db, character["id"], f"native-quest-conversation-activation:{identity}", fact
    ):
        raise ValueError("Quest activation receipt lacks its running state")
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {identity})
    from wakfu_server.achievements.mission_progress import auto_track

    auto_track(after, identity)
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"], before, after, [], [], int(store.now().timestamp() * 1000)
    )


def _nearby_placement(character, row, item):
    """Use the published interaction approach while retaining the actor position."""
    from wakfu_server.npc_world import nearby

    anchor = item.get("interaction_anchor")
    return nearby(character, dict(row, **anchor) if anchor is not None else row)


def begin(
    store,
    account_id,
    generation,
    character,
    actor_id,
    action_id,
    *,
    character_provider,
    rows_provider,
):
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        _owner(db, character)
        current = store.character(account_id, character["id"], db)
        published = publication(db)
        if published is None:
            raise ValueError("No qualified quest NPC publication")
        row, item = _row(db, actor_id, published)
        if action_id not in row["action_ids"] or not _nearby_placement(
            current, row, item
        ):
            raise ValueError(
                "Acércate al personaje y comprueba que estés a su misma altura."
            )
        root = row["dialogue_root"]
        if item["activation_policy"] == "explicit_choice":
            before = storage.load_locked(db, current["id"])
            roots = item.get(
                "running_roots", {str(item["quest_id"]): item["running_root"]}
            )
            active_roots = [
                root_id
                for identity, root_id in roots.items()
                if int(identity) in before["running"]
            ]
            if len(active_roots) > 1:
                raise ValueError("Conflicting active quest chain")
            if active_roots:
                root = active_roots[0]
            packets = []
        elif item["activation_policy"] == "already_running":
            # This policy controls quest activation, not access to the NPC's
            # native greeting. Choice criteria and completion authorization
            # continue to require the player's real mission state.
            packets = []
        else:
            packets = _activate(db, store, current, row, published[1][item["quest_id"]])
    native = npc_dialogue.catalog()
    graph = {(n, c): t for n, c, t in item["graph"]}
    allowed = (
        {row["dialogue_root"]}
        | {t for t in graph.values() if t}
        | set(item.get("running_roots", {}).values())
    )
    owner = current["id"], current["account_id"]
    digest = conversation._digest(published[0])

    def available(criterion):
        value = character_provider()
        if (value["id"], value["account_id"]) != owner:
            return False

        # Resolve only explicitly published recurring definitions; transform
        # their reset predicate without bypassing the rest of a compound rule.
        def reset_allowed(identity):
            from wakfu_server.achievements import recurring_turnin

            config = next(
                (
                    c
                    for c in published[0].get("recurring_deliveries", [])
                    if c["quest_id"] == identity
                ),
                None,
            )
            if config is None:
                return False
            with store.connection() as db:
                return recurring_turnin.can_offer(
                    db,
                    value,
                    published[1][identity],
                    config,
                    now_ms=int(store.now().timestamp() * 1000),
                )

        return _criterion(
            store,
            value,
            criterion or "",
            queries(store, value["id"]),
            reset_allowed=reset_allowed,
        )

    def authorize(speaker_id, node_id):
        value = character_provider()
        actual = next((r for r in rows_provider() if r["actor_id"] == actor_id), None)
        return (
            actual is not None
            and qualified_placement(actual, published=actual.get("_quest_publication"))
            and conversation.placement_signature(actual)
            == conversation.placement_signature(row)
            and speaker_id == actor_id
            and node_id in allowed
            and _nearby_placement(value, actual, item)
            and (value["id"], value["account_id"]) == owner
        )

    session = npc_dialogue.DialogueSession(
        native["node_index"],
        graph,
        authorize_node=lambda node: available(node.get("criteria")),
        authorize_choice=lambda choice: available(choice.get("criteria")),
    )
    packet = session.open(root, actor_id, authorize)
    session.quest_nearby = lambda character, actual: (
        conversation.placement_signature(actual)
        == conversation.placement_signature(row)
        and _nearby_placement(character, actual, item)
    )
    session.quest_conversation_actor_id = actor_id
    session.quest_publication_sha256 = digest
    return session, packets + [packet]


def _free_quest_arrival(source, destination_id):
    """Qualify an earned script arrival without bypassing a native toll.

    The NPC scene is not a physical activation of the remote teleporter. Only
    its original unconditional, free public arrival may be reused here.
    """
    destinations = (
        []
        if source is None
        else [
            row
            for row in source["destinations"]
            if row["destination_id"] == destination_id
        ]
    )
    if len(destinations) != 1:
        raise ValueError("Missing or ambiguous native quest boat arrival")
    destination = destinations[0]
    if (
        destination.get("cyZ") != -1
        or destination.get("native_altitude_walkable") is not True
        or type(destination.get("criterion")) is not str
        or destination["criterion"].strip()
        or destination.get("cyW") != 0
        or destination.get("cyX") != 0
        or destination.get("item_reference") != 0
        or destination.get("cof") is not False
    ):
        raise ValueError("Quest boat arrival is not a free native public route")
    return destination


def choose(store, account_id, generation, character, session, body):
    request = npc_dialogue.decode_request(npc_dialogue.CHOICE_REQUEST, body)
    previous = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            _owner(db, character)
            current = store.character(account_id, character["id"], db)
            published = publication(db)
            if (
                published is None
                or conversation._digest(published[0])
                != session.quest_publication_sha256
            ):
                raise ValueError("Quest conversation publication changed")
            row, item = _row(db, session.quest_conversation_actor_id, published)
            key = (
                row["reference_id"],
                row["action_ids"][0],
                request["node_id"],
                request["choice_id"],
            )
            binding = published[2].get(key)
            outcome = dict(applied=False, packets=[])
            recurring = next(
                (
                    c
                    for c in published[0].get("recurring_deliveries", [])
                    if c["reference_id"] == row["reference_id"]
                    and c["action_id"] in row["action_ids"]
                    and (request["node_id"], request["choice_id"])
                    in (
                        (c["accept_node"], c["accept_choice"]),
                        (c["delivery_node"], c["delivery_choice"]),
                    )
                ),
                None,
            )
            # Validate and advance the native session before any payment/state
            # changes; exception handling restores it if the transaction fails.
            if recurring is not None:
                packet = session.choose(**request)
                from wakfu_server.achievements import recurring_turnin

                definition = published[1][recurring["quest_id"]]
                if request["choice_id"] == recurring["accept_choice"]:
                    outcome["packets"].extend(
                        recurring_turnin.accept(
                            db, store, current, definition, recurring
                        )
                    )
                else:
                    outcome = recurring_turnin.deliver(
                        db, store, current, definition, recurring
                    )
                if packet is not None:
                    outcome["packets"].append(packet)
                return outcome
            if item["activation_policy"] == "explicit_choice" and (
                request["node_id"],
                request["choice_id"],
            ) == tuple(item["start_on_choice"]):
                # Only an offered native choice may activate this quest.
                node = session._node(request["node_id"])
                choice = next(
                    (c for c in node["choices"] if c["id"] == request["choice_id"]),
                    None,
                )
                if (
                    choice is None
                    or not session.authorize_choice(choice)
                    or not session.authorize_speaker(
                        row["actor_id"], request["node_id"]
                    )
                ):
                    raise ValueError("Quest start choice was not offered")
                outcome["packets"].extend(
                    _activate(db, store, current, row, published[1][item["quest_id"]])
                )
            if binding is not None:
                delivery = next(
                    (
                        entry
                        for entry in published[0].get("turnins", [])
                        if (
                            entry["reference_id"],
                            entry["action_id"],
                            entry["node_id"],
                            entry["choice_id"],
                        )
                        == key
                    ),
                    None,
                )
                if delivery is None:
                    outcome = conversation.settle(
                        db,
                        store,
                        current,
                        session,
                        binding,
                        published[1][binding.quest_id],
                        **request,
                    )
                else:
                    from wakfu_server.achievements import conversation_turnin

                    requirement = conversation_turnin.TurnInRequirement(
                        delivery["item_reference"], delivery["quantity"]
                    )
                    outcome = conversation_turnin.settle(
                        db,
                        store,
                        current,
                        session,
                        binding,
                        published[1][binding.quest_id],
                        requirement,
                        **request,
                    )
            for link in published[0].get("activation_links", []):
                if link["after_quest"] in outcome.get("completed", []):
                    outcome["packets"].extend(
                        _activate(
                            db, store, current, row, published[1][link["start_quest"]]
                        )
                    )
            packet = session.choose(**request)
            if packet is not None:
                outcome["packets"].append(packet)
            if outcome["applied"] and item.get("on_completion_transport") is not None:
                from wakfu_server import generic_transports

                source_map, source_id, destination_id = item["on_completion_transport"]
                source = generic_transports.source(source_map, source_id)
                destination = _free_quest_arrival(source, destination_id)
                target = {k: destination[k] for k in ("map_id", "x", "y", "z")}
                target["instance_id"] = 0
                outcome["saved"] = store.transition_map_in_transaction(
                    db, account_id, generation, current["id"], current, target
                )
                outcome["transport"] = dict(
                    direction=destination["direction"], destination=target
                )
            return outcome
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = previous
        raise


def install(db, document, *, actor_ids=None):
    """Publish reviewed data and nonoverlapping reconstructed NPC rows atomically.

    This is an operator/fixture installer, never an automatic startup seed.
    It does not mutate player progress, quests, inventory, instances or routes.
    """
    from psycopg.pq import TransactionStatus
    from psycopg.types.json import Jsonb

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Quest publication requires an active transaction")
    if conversation._digest(document) != source_contract_digest():
        raise ValueError("Quest installation differs from its reviewed source")
    conversation.validate_rules(document)
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if previous is not None and previous["value"] != document:
        raise ValueError("Quest publication already has a different reviewed contract")
    db.execute(
        "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO NOTHING",
        (SETTING, Jsonb(document)),
    )
    for item in document["placements"]:
        row = item["row"]
        if actor_ids is not None and row["actor_id"] not in actor_ids:
            continue
        existing = db.execute(
            "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s FOR UPDATE",
            (row["actor_id"],),
        ).fetchone()
        if existing is not None:
            if (
                conversation.placement_signature(existing)
                != conversation.placement_signature(row)
                or existing["enabled"] != row["enabled"]
                or existing["provenance"] != row["provenance"]
            ):
                raise ValueError("Reconstructed quest NPC identity is already occupied")
            continue
        fields = (
            "actor_id",
            "reference_id",
            "map_id",
            "instance_id",
            "x",
            "y",
            "z",
            "direction",
            "dialogue_root",
            "action_ids",
            "interaction_range",
            "enabled",
            "provenance",
        )
        values = [Jsonb(row[k]) if k == "action_ids" else row[k] for k in fields]
        db.execute(
            "INSERT INTO world_dialogue_npcs("
            + ",".join(fields)
            + ") VALUES("
            + ",".join(["%s"] * len(fields))
            + ")",
            values,
        )
    # Validate all native action/node identities before the caller commits.
    publication(db)
