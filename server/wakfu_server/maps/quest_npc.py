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

from wakfu_server.achievements import (
    conversation,
    storage,
    wire,
    native_effective_eligibility,
)
from wakfu_server.achievements.service import _owner
from wakfu_server import dungeon_criteria, npc_dialogue
from wakfu_server.dungeon_achievement_authority import queries_from_state, queries

PREFIX = "wakemu.qualified-quest-conversation.v1:"
SETTING = "native_quest_conversation_contracts"
SOURCE_SHA256 = "75ba1098589649bfcbdf2c4f4930dbfb42bf7f5a5d3736dca087aada11af8f70"


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


class ConditionalBindings(dict):
    """Keep ordinary lookup compatibility while publishing explicit alternatives."""

    def __init__(self, values):
        super().__init__(values)
        self.alternatives = {}


def select_binding(bindings, key, state, *, placement_sha256=None):
    binding = bindings.get(key)
    alternatives = getattr(bindings, "alternatives", {}).get(key)
    if alternatives is None:
        return binding
    authority = queries_from_state(state)
    active = [
        row
        for row in (binding, *alternatives)
        if (placement_sha256 is None or row.placement_sha256 == placement_sha256)
        and authority["IsAchievementRunning"](row.quest_id)
    ]
    if len(active) != 1:
        raise ValueError("Native dialogue requires exactly one running quest branch")
    return active[0]


def all_bindings(bindings):
    yield from bindings.values()
    for alternatives in getattr(bindings, "alternatives", {}).values():
        yield from alternatives


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
    from wakfu_server.achievements import conversation_supplies

    conversation_supplies.validate(value, native)
    nodes = native["node_index"]
    speakers = {s["ref"]: s for s in native["speakers"]}
    if value.get("alternative_bindings"):
        from wakfu_server.achievements.conversation_authoring import (
            objective_predicates,
        )

        bindings = ConditionalBindings(bindings)
        for declaration in value["alternative_bindings"]:
            _, checked = conversation.validate_rules(
                dict(value, bindings=[declaration])
            )
            key, alternative = next(iter(checked.items()))
            base = bindings.get(key)
            if base is None:
                raise ValueError(
                    "Alternative dialogue binding lacks its canonical source"
                )
            branches = bindings.alternatives.setdefault(key, [])
            if (alternative.quest_id, alternative.placement_sha256) in {
                (row.quest_id, row.placement_sha256) for row in (base, *branches)
            }:
                raise ValueError("Duplicate conditional dialogue quest/source branch")
            if (
                alternative.quest_id == base.quest_id
                and alternative.objective_id != base.objective_id
            ):
                raise ValueError(
                    "A repeated NPC source cannot replace its native objective"
                )
            node = nodes[alternative.node_id]
            choice = next(
                c for c in node["choices"] if c["id"] == alternative.choice_id
            )
            payment = next(
                (
                    turnin
                    for turnin in value.get("turnins", [])
                    if tuple(
                        turnin[field]
                        for field in (
                            "reference_id",
                            "action_id",
                            "node_id",
                            "choice_id",
                        )
                    )
                    == key
                ),
                None,
            )
            for binding in (base, alternative):
                placements = [
                    p
                    for p in value["placements"]
                    if p["row"]["reference_id"] == binding.reference_id
                    and binding.action_id in p["row"]["action_ids"]
                    and conversation.placement_signature(p["row"])
                    == binding.placement_sha256
                ]
                if len(placements) != 1:
                    raise ValueError(
                        "Conditional binding lacks one exact published NPC source"
                    )
                guards = [
                    item["criterion"]
                    for item in placements[0].get("choice_criteria", [])
                    if (item["node_id"], item["choice_id"])
                    == (binding.node_id, binding.choice_id)
                ]
                expression = " && ".join(
                    f"({part})"
                    for part in (node["criteria"], choice["criteria"], *guards)
                    if part.strip()
                )
                objectives = {o["d"] for o in definitions[binding.quest_id]["cjJ"]}
                remaining = (
                    binding.objective_id if len(objectives) > 1 and guards else None
                )
                found, required_item = objective_predicates(
                    expression,
                    binding.quest_id,
                    objectives,
                    payment=payment is not None,
                    payment_basket=payment is not None and "items" in payment,
                    single_objective=len(objectives) == 1,
                    running_branch=binding.quest_id,
                    remaining_objective=remaining,
                    required_objectives=objectives - {binding.objective_id}
                    if remaining
                    else (),
                )
                expected_payment = None
                if payment is not None:
                    expected_payment = (
                        tuple(
                            (item["item_reference"], item["quantity"])
                            for item in payment["items"]
                        )
                        if "items" in payment
                        else (payment["item_reference"], payment["quantity"])
                    )
                if (
                    found != binding.objective_id
                    or payment is not None
                    and required_item != expected_payment
                ):
                    raise ValueError(
                        "Conditional binding differs from exact native branch authority"
                    )
            branches.append(alternative)
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
        if "native_opening_roots" in item:
            from wakfu_server.native_npc_roots import validate as validate_roots

            validate_roots(item["native_opening_roots"], nodes)
            if (
                item["activation_policy"] != "already_running"
                or row["dialogue_root"] not in item["native_opening_roots"]
            ):
                raise ValueError("Invalid qualified native opening roots")
        if "existing_native_actor" in item and "existing_dialogue_actor" in item:
            raise ValueError("Quest overlay has ambiguous physical providers")
        for provider_field in ("existing_native_actor", "existing_dialogue_actor"):
            if provider_field not in item:
                continue
            proof = item[provider_field]
            if provider_field == "existing_dialogue_actor" and (
                item["activation_policy"] != "already_running"
                or item.get("available_quests_on_open")
            ):
                raise ValueError(
                    "Captured dialogue overlay cannot activate quests on open"
                )
            if (
                not isinstance(proof, dict)
                or set(proof) != {"source_sha256", "quest_ids", "evidence"}
                or not isinstance(proof["source_sha256"], str)
                or len(proof["source_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in proof["source_sha256"])
                or not isinstance(proof["quest_ids"], list)
                or not proof["quest_ids"]
                or len(set(proof["quest_ids"])) != len(proof["quest_ids"])
                or any(
                    type(q) is not int or q not in definitions
                    for q in proof["quest_ids"]
                )
                or not isinstance(proof["evidence"], str)
                or not proof["evidence"].strip()
            ):
                raise ValueError("Invalid reviewed existing native actor overlay")
        if "provider_overlay_criterion" in item:
            criterion = item["provider_overlay_criterion"]
            if (
                "existing_dialogue_actor" not in item
                or not criterion
                or criterion
                not in {
                    choice.get("criteria")
                    for node_id, choice_id in edges
                    for choice in nodes[node_id]["choices"]
                    if choice["id"] == choice_id
                }
            ):
                raise ValueError(
                    "Provider overlay lacks its exact native choice predicate"
                )
        arrival_keys = set()
        for arrival in item.get("choice_paired_arrivals", []):
            from wakfu_server.npc_paired_travel import validate_paired_arrival

            validate_paired_arrival(
                value["placements"], item, arrival, check_floor=True
            )
            pair = (arrival["node_id"], arrival["choice_id"])
            if pair in arrival_keys:
                raise ValueError("Duplicate native paired NPC destination")
            arrival_keys.add(pair)
        for arrival in item.get("choice_approach_arrivals", []):
            if (
                not isinstance(arrival, dict)
                or set(arrival)
                != {
                    "node_id",
                    "choice_id",
                    "source_map_id",
                    "source_object_id",
                    "approach",
                    "direction",
                    "evidence",
                }
                or any(
                    type(arrival[k]) is not int or arrival[k] <= 0
                    for k in (
                        "node_id",
                        "choice_id",
                        "source_map_id",
                        "source_object_id",
                    )
                )
                or (arrival["node_id"], arrival["choice_id"]) not in edges
                or not isinstance(arrival["approach"], dict)
                or set(arrival["approach"]) != {"x", "y", "z"}
                or any(type(arrival["approach"][k]) is not int for k in ("x", "y", "z"))
                or type(arrival["direction"]) is not int
                or not 0 <= arrival["direction"] < 8
                or not isinstance(arrival["evidence"], str)
                or not arrival["evidence"].strip()
                or (arrival["node_id"], arrival["choice_id"]) in arrival_keys
            ):
                raise ValueError("Invalid reviewed NPC exterior approach")
            arrival_keys.add((arrival["node_id"], arrival["choice_id"]))
        route_keys = set()
        for destination in item.get("choice_routes", []):
            if (
                not isinstance(destination, dict)
                or set(destination) != {"node_id", "choice_id", "route", "evidence"}
                or type(destination["node_id"]) is not int
                or type(destination["choice_id"]) is not int
                or (destination["node_id"], destination["choice_id"]) not in edges
                or not isinstance(destination["route"], str)
                or not destination["route"].strip()
                or not isinstance(destination["evidence"], str)
                or not destination["evidence"].strip()
                or (destination["node_id"], destination["choice_id"]) in route_keys
            ):
                raise ValueError("Invalid reviewed native NPC choice destination")
            if (destination["node_id"], destination["choice_id"]) in arrival_keys:
                raise ValueError("Conflicting paired or native NPC destination")
            route_keys.add((destination["node_id"], destination["choice_id"]))
        spoken_keys = set()
        for spoken in item.get("spoken_objectives", []):
            if (
                not isinstance(spoken, dict)
                or set(spoken) != {"quest_id", "objective_id", "action_ids", "evidence"}
                or type(spoken["quest_id"]) is not int
                or spoken["quest_id"] not in definitions
                or type(spoken["objective_id"]) is not int
                or spoken["objective_id"]
                not in {o["d"] for o in definitions[spoken["quest_id"]]["cjJ"]}
                or not isinstance(spoken["action_ids"], list)
                or not spoken["action_ids"]
                or any(type(action) is not int for action in spoken["action_ids"])
                or len(set(spoken["action_ids"])) != len(spoken["action_ids"])
                or not set(spoken["action_ids"]) <= set(row["action_ids"])
                or not isinstance(spoken["evidence"], str)
                or not spoken["evidence"].strip()
                or (spoken["quest_id"], spoken["objective_id"]) in spoken_keys
            ):
                raise ValueError("Invalid qualified NPC spoken objective")
            spoken_keys.add((spoken["quest_id"], spoken["objective_id"]))
        running_roots = item.get("running_roots", {})
        if type(running_roots) is not dict or any(
            not str(identity).isdigit()
            or int(identity) not in definitions
            or root not in nodes
            for identity, root in running_roots.items()
        ):
            raise ValueError("Invalid quest NPC running roots")
        starts = item.get("available_quests_on_open", [])
        if (
            not isinstance(starts, list)
            or len(set(starts)) != len(starts)
            or any(
                type(identity) is not int
                or identity not in definitions
                or definitions[identity].get("aqb") is not False
                or any(
                    definitions[identity].get(field) != 0
                    for field in ("cjU", "cjL", "getDuration")
                )
                for identity in starts
            )
        ):
            raise ValueError("Invalid quest NPC opening activation")
        opening_criteria = item.get("opening_quest_criteria", {})
        if type(opening_criteria) is not dict or any(
            key not in {str(identity) for identity in starts}
            or type(criterion) is not str
            or not criterion.strip()
            for key, criterion in opening_criteria.items()
        ):
            raise ValueError("Invalid reviewed opening quest criterion")
        choice_starts = item.get("choice_starts", [])
        choice_criteria = item.get("choice_criteria", [])
        if type(choice_starts) is not list or type(choice_criteria) is not list:
            raise ValueError("Invalid reviewed choice declarations")
        declared_starts = set()
        for declaration in choice_starts + choice_criteria:
            key = declaration.get("node_id"), declaration.get("choice_id")
            if (
                any(type(value) is not int or value <= 0 for value in key)
                or key not in edges
                or type(declaration.get("criterion")) is not str
                or not declaration["criterion"].strip()
                or type(declaration.get("evidence")) is not str
                or not declaration["evidence"].strip()
            ):
                raise ValueError("Invalid reviewed choice criterion")
            if declaration in choice_starts:
                quest_id = declaration.get("quest_id")
                if (
                    type(quest_id) is not int
                    or quest_id not in definitions
                    or key in declared_starts
                ):
                    raise ValueError("Ambiguous reviewed quest start choice")
                declared_starts.add(key)
                definition = definitions[quest_id]
                if definition.get("aqb") is not False or any(
                    definition.get(field) != 0
                    for field in ("cjU", "cjL", "getDuration")
                ):
                    raise ValueError(
                        "Reviewed choice start requires a nonrecurring quest"
                    )
        from wakfu_server.combat_local_criteria import parse_local_criterion

        for criterion in list(opening_criteria.values()) + [
            declaration["criterion"] for declaration in choice_starts + choice_criteria
        ]:
            parse_local_criterion(criterion)
        branches = item.get("running_root_branches", {})
        if type(branches) is not dict or any(
            identity not in running_roots for identity in branches
        ):
            raise ValueError("Invalid quest NPC stage roots")
        branch_roots = set()
        for cases in branches.values():
            if not isinstance(cases, list) or not cases:
                raise ValueError("Quest NPC stage roots require reviewed cases")
            for case in cases:
                if (
                    type(case) is not dict
                    or set(case) != {"root", "criterion"}
                    or type(case["root"]) is not int
                    or case["root"] not in nodes
                    or type(case["criterion"]) is not str
                    or not case["criterion"].strip()
                ):
                    raise ValueError("Invalid quest NPC stage root case")
                from wakfu_server.combat_local_criteria import parse_local_criterion

                parse_local_criterion(case["criterion"])
                branch_roots.add(case["root"])
        reached = (
            {row["dialogue_root"]}
            | set(running_roots.values())
            | branch_roots
            | set(item.get("native_opening_roots", []))
        )
        while True:
            following = {t for (n, _), t in edges.items() if n in reached and t}
            if following <= reached:
                break
            reached.update(following)
        if any(n not in reached for n, _ in edges):
            raise ValueError("Quest conversation contains a disconnected edge")
        bound_objective = any(
            b.reference_id == row["reference_id"]
            and b.quest_id == item["quest_id"]
            and b.placement_sha256 == conversation.placement_signature(row)
            for b in all_bindings(bindings)
        )
        spoken_objective = any(
            declaration["quest_id"] == item["quest_id"]
            for declaration in item.get("spoken_objectives", [])
        )
        # These declarations were independently validated above. An actual
        # opening can produce a reviewed spoken fact, and an accepted choice
        # can enter its reviewed route without inventing an objective edge.
        if not (
            bound_objective
            or spoken_objective
            or item.get("choice_routes")
            or item.get("choice_paired_arrivals")
        ):
            raise ValueError(
                "Quest NPC has no qualified native objective or route source"
            )
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
        from wakfu_server.achievements.conversation_turnin import requirement_from_entry

        requirement_from_entry(entry)
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
    item = next(
        (
            item
            for item in published[0]["placements"]
            if item["row"]["actor_id"] == actor_id
        ),
        None,
    )
    if item is not None and any(
        field in item for field in ("existing_native_actor", "existing_dialogue_actor")
    ):
        # This is a conversation overlay, not a second physical actor. The
        # original provider continues to publish its accredited native model.
        _existing_actor(db, item)
        return dict(item["row"], _quest_publication=published), item
    row = db.execute(
        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled FOR SHARE",
        (actor_id,),
    ).fetchone()
    if row is None or not qualified_placement(row, published=published):
        raise ValueError("Unavailable qualified quest NPC")
    return row, item


def _existing_actor(db, item):
    if "existing_dialogue_actor" in item:
        from wakfu_server.npc_dialogue_source_overlay import validate

        return validate(db, item)
    return _existing_native_actor(db, item)


def _existing_native_actor(db, item):
    """Check an overlay against the unchanged accredited physical actor."""
    from wakfu_server import npc_placements

    proof = item["existing_native_actor"]
    native = db.execute(
        "SELECT * FROM world_native_npc_placements WHERE actor_id=%s AND enabled FOR SHARE",
        (item["row"]["actor_id"],),
    ).fetchone()
    if native is None:
        raise ValueError("Existing native quest actor is unavailable")
    npc_placements.validate(native)
    row = item["row"]
    if (
        native["source_sha256"] != proof["source_sha256"]
        or any(
            native[key] != row[key]
            for key in (
                "actor_id",
                "reference_id",
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "direction",
            )
        )
        or not set(row["action_ids"]) <= set(native["native_action_ids"])
    ):
        raise ValueError("Existing native quest actor source changed")
    return native


def try_native_overlay(
    store,
    account_id,
    generation,
    character,
    actor_id,
    action_id,
    *,
    character_provider,
    provider_field="existing_native_actor",
):
    """Prefer one published running story branch; otherwise leave its provider intact.

    The original physical actor remains accredited and keeps its actor ID.
    No quest is activated by this provider selector and no overlay is inferred
    from a translated name, an unoffered native root or a display level.
    """
    with store.connection() as db:
        published = publication(db)
        if published is None:
            return None
        candidates = [
            item
            for item in published[0]["placements"]
            if item["row"]["actor_id"] == actor_id
            and provider_field in item
            and action_id in item["row"]["action_ids"]
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ValueError("Ambiguous native quest actor overlay")
        item = candidates[0]
        _existing_actor(db, item)
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        actual = store.character(account_id, character["id"], db)
        _owner(db, actual)
        authority = queries_from_state(storage.load_locked(db, actual["id"]))
        running = []
        for identity in item[provider_field]["quest_ids"]:
            if authority["IsAchievementRunning"](identity):
                running.append(identity)
        if not running:
            return None
        if len(running) != 1:
            raise ValueError("Conflicting native quest actor overlay stages")
        criterion = item.get("provider_overlay_criterion", "")
        if criterion and not _criterion(store, actual, criterion, authority):
            return None

    def rows():
        with store.connection() as db:
            current_publication = publication(db)
            if current_publication is None:
                return []
            return [_row(db, actor_id, current_publication)[0]]

    return begin(
        store,
        account_id,
        generation,
        character,
        actor_id,
        action_id,
        character_provider=character_provider,
        rows_provider=rows,
    )


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


def _activate(db, store, character, row, definition, *, defer_unavailable=False):
    """Reconstructed producer; the original native availability is preserved."""
    before = storage.load_locked(db, character["id"])
    identity = definition["d"]
    if identity in before["running"] or identity in before["completed"]:
        return []
    authority = queries_from_state(before)
    if not _criterion(
        store, character, native_effective_eligibility.criterion(definition), authority
    ):
        if defer_unavailable:
            return []
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
    from wakfu_server.achievements.mission_progress import auto_track, seed_counters

    auto_track(after, identity)
    seed_counters(after, definition)
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"], before, after, [], [], int(store.now().timestamp() * 1000)
    )


def _nearby_placement(character, row, item):
    """Use the published interaction approach while retaining the actor position."""
    from wakfu_server.npc_world import nearby

    anchor = item.get("interaction_anchor")
    return nearby(character, dict(row, **anchor) if anchor is not None else row)


def _followups(db, store, character, row, published, *, completed=None):
    """Retry earned native prerequisites without rolling back a finished quest.

    A later external prerequisite may unlock the next entry in a chain. Only
    the reviewed links belonging to this placed speaker can start that entry.
    """
    supported = set()
    for placement in published[0]["placements"]:
        if placement["row"]["actor_id"] == row["actor_id"]:
            supported.add(placement["quest_id"])
            supported.update(map(int, placement.get("running_roots", {})))
    opening = completed is None
    if opening:
        completed = storage.load_locked(db, character["id"])["completed"]
    packets = []
    for link in published[0].get("activation_links", []):
        if link["after_quest"] in completed and (
            not opening or link["start_quest"] in supported
        ):
            packets.extend(
                _activate(
                    db,
                    store,
                    character,
                    row,
                    published[1][link["start_quest"]],
                    defer_unavailable=True,
                )
            )
    return packets


def _running_root(store, character, item, state):
    """Select one reviewed quest stage using actual objective state."""
    roots = item.get("running_roots")
    if roots is None:
        roots = {str(item["quest_id"]): item["running_root"]}
    authority = queries_from_state(state)
    active = []
    for identity in roots:
        try:
            running = authority["IsAchievementRunning"](int(identity))
        except ValueError:
            # An absent native period clock cannot select a mission stage.
            # The NPC's separately qualified default greeting remains usable.
            continue
        if running:
            active.append(identity)
    if not active:
        return item["row"]["dialogue_root"]
    resolved = []
    for identity in active:
        branches = item.get("running_root_branches", {}).get(identity, [])
        if not branches:
            resolved.append(roots[identity])
            continue
        matches = [
            branch["root"]
            for branch in branches
            if _criterion(store, character, branch["criterion"], authority)
        ]
        if len(matches) != 1:
            raise ValueError("Quest stage requires one matching native dialogue root")
        resolved.append(matches[0])
    if len(set(resolved)) != 1:
        raise ValueError("Conflicting active quest chain")
    return resolved[0]


def _native_opening_root(store, character, item, state):
    """Select reviewed alternatives using their unchanged native predicates."""
    from wakfu_server.native_npc_roots import select

    authority = queries_from_state(state)
    return select(
        item["native_opening_roots"],
        npc_dialogue.catalog()["node_index"],
        available=lambda criterion: _criterion(store, character, criterion, authority),
    )


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
        packets = []
        for identity in item.get("available_quests_on_open", []):
            guard = item.get("opening_quest_criteria", {}).get(str(identity), "True")
            if guard != "True":
                opening_state = storage.load_locked(db, current["id"])
                if not _criterion(
                    store,
                    current,
                    guard,
                    queries_from_state(opening_state),
                ):
                    continue
            packets.extend(
                _activate(
                    db,
                    store,
                    current,
                    row,
                    published[1][identity],
                    defer_unavailable=True,
                )
            )
        if item["activation_policy"] == "explicit_choice":
            from wakfu_server.achievements import completed_achievement_sets

            packets.extend(completed_achievement_sets.recover(db, store, current))
            packets.extend(_followups(db, store, current, row, published))
            before = storage.load_locked(db, current["id"])
            root = _running_root(store, current, item, before)
        elif item["activation_policy"] == "already_running":
            # This policy controls quest activation, not access to the NPC's
            # native greeting. Choice criteria and completion authorization
            # continue to require the player's real mission state.
            if item.get("running_roots"):
                root = _running_root(
                    store, current, item, storage.load_locked(db, current["id"])
                )
        else:
            packets.extend(
                _activate(
                    db,
                    store,
                    current,
                    row,
                    published[1][item["quest_id"]],
                    defer_unavailable=True,
                )
            )
        if "native_opening_roots" in item:
            root = _native_opening_root(
                store, current, item, storage.load_locked(db, current["id"])
            )
    native = npc_dialogue.catalog()
    graph = {(n, c): t for n, c, t in item["graph"]}
    allowed = (
        {row["dialogue_root"]}
        | {t for t in graph.values() if t}
        | set(item.get("running_roots", {}).values())
        | set(item.get("native_opening_roots", []))
        | {
            case["root"]
            for cases in item.get("running_root_branches", {}).values()
            for case in cases
        }
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
        authorize_choice=lambda choice: (
            any(identity == choice["id"] for _, identity in graph)
            and available(choice.get("criteria"))
            and all(
                available(declaration["criterion"])
                for declaration in item.get("choice_starts", [])
                + item.get("choice_criteria", [])
                if declaration["choice_id"] == choice["id"]
            )
        ),
    )
    packet = session.open(root, actor_id, authorize)
    session.quest_nearby = lambda character, actual: (
        conversation.placement_signature(actual)
        == conversation.placement_signature(row)
        and _nearby_placement(character, actual, item)
    )
    session.quest_conversation_actor_id = actor_id
    session.quest_publication_sha256 = digest
    if item.get("spoken_objectives"):
        from wakfu_server.achievements import npc_spoken_missions

        packets = (
            packets
            + [packet]
            + npc_spoken_missions.on_open(
                store, account_id, generation, current, row, action_id, session, digest
            )
        )
        return session, packets
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


def qualify_approach_arrival(source, declaration):
    """A reviewed script may approach a native entrance, never activate it."""
    if (
        source is None
        or source.get("id") != declaration.get("source_object_id")
        or source.get("map_id") != declaration.get("source_map_id")
        or type(declaration.get("direction")) is not int
        or not 0 <= declaration["direction"] < 8
        or declaration.get("approach") not in source.get("approach_positions", [])
    ):
        raise ValueError("NPC arrival differs from the actual native exterior approach")
    point = declaration["approach"]
    if any(type(point.get(k)) is not int for k in ("x", "y", "z")):
        raise ValueError("NPC exterior approach lacks native coordinates")
    return dict(map_id=source["map_id"], instance_id=0, **point)


def _offered_mutation_choice(session, request):
    """Freeze approval before a payment/start changes its own native criterion."""
    if session.node_id != request["node_id"]:
        raise ValueError("Stale or unsolicited dialogue choice")
    node = session._node(request["node_id"])
    choice = next(
        (row for row in node["choices"] if row["id"] == request["choice_id"]), None
    )
    if (
        choice is None
        or not session.authorize_choice(choice)
        or not session.authorize_speaker(session.speaker_id, request["node_id"])
    ):
        raise ValueError("Quest conversation choice was not offered")
    return choice


def _choose_after_mutation(session, request, offered):
    if offered is None:
        return session.choose(**request)
    authorize = session.authorize_choice
    authorize_node = session.authorize_node
    source_pending = True

    def current_then_live(node):
        nonlocal source_pending
        if source_pending and node is session.nodes.get(request["node_id"]):
            source_pending = False
            return True
        return authorize_node(node)

    # Both the current node and exact choice were approved before this same
    # transaction changed their native predicates. Freeze only that first
    # source-node check; destination nodes (including a loopback) remain live.
    # Speaker ownership/range is never bypassed.
    session.authorize_choice = lambda choice: choice == offered
    session.authorize_node = current_then_live
    try:
        return session.choose(**request)
    finally:
        session.authorize_choice = authorize
        session.authorize_node = authorize_node


def selected_choice_journey(store, session, body):
    """Read public/owned routing once; real choose still owns authorization."""
    if session is None or getattr(session, "quest_conversation_actor_id", None) is None:
        return None, None
    request = npc_dialogue.decode_request(npc_dialogue.CHOICE_REQUEST, body)
    with store.connection() as db:
        published = publication(db)
        if (
            published is None
            or conversation._digest(published[0]) != session.quest_publication_sha256
        ):
            raise ValueError("NPC choice destination publication changed")
        _, item = _row(db, session.quest_conversation_actor_id, published)

        def selected(field):
            return next(
                (
                    entry
                    for entry in item.get(field, ())
                    if (entry["node_id"], entry["choice_id"])
                    == (request["node_id"], request["choice_id"])
                ),
                None,
            )

        return selected("choice_routes"), selected("choice_paired_arrivals")


def selected_choice_route(store, session, body):
    """Read one declared route; authorization still belongs to real choose()."""
    return selected_choice_journey(store, session, body)[0]


def selected_paired_arrival(store, session, body):
    """Route only; the accepted choice transaction owns actual authorization."""
    return selected_choice_journey(store, session, body)[1]


def choose(
    store,
    account_id,
    generation,
    character,
    session,
    body,
    *,
    choice_entry=None,
    paired_position_accounts=None,
):
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
            if key in getattr(published[2], "alternatives", {}):
                binding = select_binding(
                    published[2],
                    key,
                    storage.load_locked(db, current["id"]),
                    placement_sha256=conversation.placement_signature(row),
                )
            else:
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
            start_quests = [
                declaration["quest_id"]
                for declaration in item.get("choice_starts", [])
                if (declaration["node_id"], declaration["choice_id"])
                == (request["node_id"], request["choice_id"])
            ]
            if item["activation_policy"] == "explicit_choice" and (
                request["node_id"],
                request["choice_id"],
            ) == tuple(item["start_on_choice"]):
                start_quests.append(item["quest_id"])
            if len(start_quests) > 1:
                raise ValueError("Ambiguous offered quest start")
            starts = bool(start_quests)
            routes = [
                declaration
                for declaration in item.get("choice_routes", [])
                if (declaration["node_id"], declaration["choice_id"])
                == (request["node_id"], request["choice_id"])
            ]
            if len(routes) > 1:
                raise ValueError("Ambiguous actual NPC choice destination")
            selected_route = routes[0] if routes else None
            pairs = [
                declaration
                for declaration in item.get("choice_paired_arrivals", ())
                if (declaration["node_id"], declaration["choice_id"])
                == (request["node_id"], request["choice_id"])
            ]
            if len(pairs) > 1 or pairs and selected_route is not None:
                raise ValueError("Conflicting actual NPC journey destinations")
            paired_target = None
            if pairs:
                from wakfu_server import npc_paired_travel

                if (
                    paired_position_accounts is None
                    or account_id not in paired_position_accounts
                ):
                    raise ValueError(
                        "Paired NPC journey requires its normal position fence"
                    )
                paired_target = npc_paired_travel.qualify(
                    db, store, current, published, row, item, pairs[0], action_id=key[1]
                )
            if selected_route is not None and not callable(choice_entry):
                raise ValueError(
                    "NPC choice destination requires the normal owned entry handler"
                )
            offered = (
                _offered_mutation_choice(session, request)
                if starts or binding is not None or selected_route is not None or pairs
                else None
            )
            entry_proof = None
            if selected_route is not None:
                entry_proof = dict(
                    route_key=selected_route["route"],
                    actor_id=row["actor_id"],
                    reference_id=row["reference_id"],
                    action_id=key[1],
                    node_id=request["node_id"],
                    choice_id=request["choice_id"],
                    publication_sha256=session.quest_publication_sha256,
                    placement_sha256=conversation.placement_signature(row),
                    account_id=account_id,
                    char_id=current["id"],
                    generation=generation,
                    source_position={
                        field: current[field]
                        for field in ("map_id", "instance_id", "x", "y", "z")
                    },
                )
            if starts:
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
                    _activate(db, store, current, row, published[1][start_quests[0]])
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
                        speaker_row=row,
                        **request,
                    )
                else:
                    from wakfu_server.achievements import conversation_turnin

                    requirement = conversation_turnin.requirement_from_entry(delivery)
                    outcome = conversation_turnin.settle(
                        db,
                        store,
                        current,
                        session,
                        binding,
                        published[1][binding.quest_id],
                        requirement,
                        speaker_row=row,
                        **request,
                    )
            outcome["packets"].extend(
                _followups(
                    db,
                    store,
                    current,
                    row,
                    published,
                    completed=outcome.get("completed", []),
                )
            )
            packet = _choose_after_mutation(session, request, offered)
            if packet is not None:
                outcome["packets"].append(packet)
            from wakfu_server.achievements import conversation_supplies

            outcome["packets"].extend(
                conversation_supplies.settle(
                    db, store, current, published[0], row, **request
                )
            )
            arrivals = [
                arrival
                for arrival in item.get("choice_approach_arrivals", [])
                if (arrival["node_id"], arrival["choice_id"])
                == (request["node_id"], request["choice_id"])
            ]
            if len(arrivals) > 1 or (arrivals and (entry_proof is not None or pairs)):
                raise ValueError("Conflicting native NPC destinations")
            if arrivals:
                from wakfu_server import generic_transports, mission_transport

                arrival = arrivals[0]
                target = qualify_approach_arrival(
                    generic_transports.source(
                        arrival["source_map_id"], arrival["source_object_id"]
                    ),
                    arrival,
                )
                (
                    outcome["saved"],
                    journey_packets,
                ) = mission_transport.public_transition_locked(
                    db, store, account_id, generation, current, target
                )
                outcome["packets"].extend(journey_packets)
                outcome["transport"] = dict(
                    direction=arrival["direction"], destination=target
                )
            if paired_target is not None:
                from wakfu_server import mission_transport

                (
                    outcome["saved"],
                    journey_packets,
                ) = mission_transport.public_transition_locked(
                    db, store, account_id, generation, current, paired_target
                )
                outcome["packets"].extend(journey_packets)
                outcome["transport"] = dict(
                    direction=pairs[0]["direction"], destination=paired_target
                )
            if entry_proof is not None:
                # This same transaction already accepted the real native
                # session choice. The normal owned-entry service rechecks its
                # source and queues durable movement/outbox delivery.
                outcome["owned_entry"] = choice_entry(db, store, current, entry_proof)
                if outcome["owned_entry"].get("public_arrival") is not None:
                    outcome["packets"].extend(outcome["owned_entry"].get("packets", ()))
            if outcome["applied"] and item.get("on_completion_transport") is not None:
                from wakfu_server import generic_transports, mission_transport

                if "saved" in outcome or "owned_entry" in outcome:
                    raise ValueError("Conflicting completion and accepted NPC journeys")

                source_map, source_id, destination_id = item["on_completion_transport"]
                source = generic_transports.source(source_map, source_id)
                destination = _free_quest_arrival(source, destination_id)
                target = {k: destination[k] for k in ("map_id", "x", "y", "z")}
                target["instance_id"] = 0
                (
                    outcome["saved"],
                    journey_packets,
                ) = mission_transport.public_transition_locked(
                    db, store, account_id, generation, current, target
                )
                outcome["packets"].extend(journey_packets)
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
        if any(
            field in item
            for field in ("existing_native_actor", "existing_dialogue_actor")
        ):
            _existing_actor(db, item)
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
