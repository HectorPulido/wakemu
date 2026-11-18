"""Compile reviewed dialogue archetypes from native predicates and placements.

The manifest chooses an existing speaker and exact native dialogue roots. This
compiler never creates an NPC, guesses numeric graph edges, or grants progress.
It reconstructs the common list-of-deliveries archetype: each native type-eight
choice naming one running quest, one unfinished objective and one item payment
becomes a transaction-scoped turn-in using the existing conversation engine.
"""

import ast
from copy import deepcopy
from dataclasses import asdict

from . import conversation


def _call(node, name):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        and not node.keywords
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and type(node.args[0].value) is int
        and node.args[0].value > 0
    )


def objective_predicates(
    expression,
    quest_id,
    objective_ids,
    *,
    payment,
    payment_basket=False,
    single_objective=False,
    item_absence_guard=False,
    running_branch=None,
    remaining_objective=None,
    required_objectives=(),
):
    """Require exact conjunctive native authority, never regex or OR inference."""
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if running_branch is not None and (
        type(running_branch) is not int or running_branch != quest_id
    ):
        raise ValueError("Invalid reviewed running quest branch")
    if remaining_objective is not None and (
        type(remaining_objective) is not int
        or remaining_objective not in objective_ids
        or any(
            type(identity) is not int or identity <= 0
            for identity in required_objectives
        )
    ):
        raise ValueError("Invalid reviewed remaining quest objective")
    tree = parse_local_criterion(" ".join(expression.split()))
    body = tree.body if isinstance(tree, ast.Expression) else tree
    leaves = []

    def flatten(node):
        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, ast.And):
                if (
                    isinstance(node.op, ast.Or)
                    and running_branch == quest_id
                    and all(
                        _call(value, "IsAchievementRunning") for value in node.values
                    )
                    and sum(value.args[0].value == quest_id for value in node.values)
                    == 1
                ):
                    leaves.append(
                        next(
                            value
                            for value in node.values
                            if value.args[0].value == quest_id
                        )
                    )
                    return
                raise ValueError("Ambiguous dialogue objective predicate")
            for value in node.values:
                flatten(value)
        else:
            leaves.append(node)

    flatten(body)
    running = [
        node.args[0].value for node in leaves if _call(node, "IsAchievementRunning")
    ]
    unfinished = [
        node.operand.args[0].value
        for node in leaves
        if isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.Not)
        and _call(node.operand, "IsAchievementObjectiveComplete")
    ]
    # Repeated native guards along a qualified dialogue path are conjunctive
    # confirmations of the same fact, not additional objective authority.
    running = list(dict.fromkeys(running))
    unfinished = list(dict.fromkeys(unfinished))
    if (
        running != [quest_id]
        or len(unfinished) != 1
        or unfinished[0] not in objective_ids
    ):
        active = [
            node.args[0].value for node in leaves if _call(node, "IsAchievementActive")
        ]
        incomplete = [
            node.operand.args[0].value
            for node in leaves
            if isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Not)
            and _call(node.operand, "IsAchievementComplete")
        ]
        active = list(dict.fromkeys(active))
        incomplete = list(dict.fromkeys(incomplete))
        required = set(required_objectives)
        positive_priors = {
            node.args[0].value
            for node in leaves
            if _call(node, "IsAchievementObjectiveComplete")
        }
        reviewed_remaining = (
            remaining_objective in objective_ids
            and required == set(objective_ids) - {remaining_objective}
            and bool(required)
            and not unfinished
            and (
                running == [quest_id]
                or (
                    not running
                    and incomplete == [quest_id]
                    and bool(positive_priors & required)
                )
            )
        )
        if reviewed_remaining:
            unfinished = [remaining_objective]
        elif (
            not single_objective
            or len(objective_ids) != 1
            or unfinished
            or not (
                (active == [quest_id] and incomplete == [quest_id] and not running)
                or (running == [quest_id] and not active)
            )
        ):
            raise ValueError("Missing unambiguous native running/objective predicates")
        else:
            unfinished = list(objective_ids)
    payments = []
    item_calls = [node for node in ast.walk(tree) if _call(node, "GetItemQuantity")]
    for node in leaves:
        if (
            isinstance(node, ast.Compare)
            and _call(node.left, "GetItemQuantity")
            and len(node.ops) == len(node.comparators) == 1
            and isinstance(node.ops[0], ast.GtE)
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
            and 0 < node.comparators[0].value <= 32767
        ):
            payments.append((node.left.args[0].value, node.comparators[0].value))
    if payment and remaining_objective is not None:
        payments.extend(
            (node.left.args[0].value, 1)
            for node in leaves
            if isinstance(node, ast.Compare)
            and _call(node.left, "GetItemQuantity")
            and len(node.ops) == len(node.comparators) == 1
            and isinstance(node.ops[0], ast.Gt)
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
            and node.comparators[0].value == 0
        )
    if type(payment_basket) is not bool or payment_basket and not payment:
        raise ValueError("Basket payment requires an explicit delivery archetype")
    if payment:
        if payment_basket:
            if (
                len(payments) < 2
                or len(item_calls) != len(payments)
                or len({reference for reference, _ in payments}) != len(payments)
            ):
                raise ValueError(
                    "Delivery requires distinct exact native item payments"
                )
            return unfinished[0], tuple(payments)
        if len(payments) != 1 or len(item_calls) != 1:
            raise ValueError("Delivery requires one exact native item payment")
        return unfinished[0], payments[0]
    absence = [
        node
        for node in leaves
        if isinstance(node, ast.Compare)
        and _call(node.left, "GetItemQuantity")
        and len(node.ops) == len(node.comparators) == 1
        and isinstance(node.ops[0], ast.Eq)
        and isinstance(node.comparators[0], ast.Constant)
        and type(node.comparators[0].value) is int
        and node.comparators[0].value == 0
    ]
    if item_calls and not (
        item_absence_guard and single_objective and len(item_calls) == len(absence) == 1
    ):
        raise ValueError("Talk archetype cannot consume or imply item payment")
    return unfinished[0], None


def extend_delivery_chain(document, definitions, nodes, manifest):
    """Add a reviewed multi-quest delivery chain without replacing old data.

    Existing placement signatures and existing edges remain unchanged. Native
    delivery choices close after atomic payment; native type-ten choices close
    without side effects. Other choices need explicit reviewed edges.
    """
    result = deepcopy(document)
    placements = [
        p for p in result["placements"] if p["row"]["actor_id"] == manifest["actor_id"]
    ]
    if len(placements) != 1:
        raise ValueError("Delivery chain requires one reviewed existing placement")
    placement = placements[0]
    row = placement["row"]
    action = manifest["action_id"]
    if action != row["action_ids"][0]:
        raise ValueError("Delivery chain action differs from placement binding")
    published = {d["d"]: d for d in result["definitions"]}
    graph = {(node, choice): target for node, choice, target in placement["graph"]}
    binding_keys = {
        (b["reference_id"], b["action_id"], b["node_id"], b["choice_id"])
        for b in result["bindings"]
    }
    roots = placement.setdefault("running_roots", {})

    def edge(node, choice, target):
        if (node, choice) in graph and graph[node, choice] != target:
            raise ValueError("Reconstruction would replace a reviewed dialogue edge")
        graph[node, choice] = target

    def binding(quest, node_id, choice, *, payment):
        definition = definitions[quest]
        identity, item = objective_predicates(
            choice["criteria"],
            quest,
            {o["d"] for o in definition["cjJ"]},
            payment=payment,
        )
        key = row["reference_id"], action, node_id, choice["id"]
        compiled = asdict(
            conversation.QualifiedConversation(
                quest,
                identity,
                row["reference_id"],
                action,
                node_id,
                choice["id"],
                conversation.placement_signature(row),
                conversation._digest(definition),
            )
        )
        if key in binding_keys:
            previous = next(
                b
                for b in result["bindings"]
                if (b["reference_id"], b["action_id"], b["node_id"], b["choice_id"])
                == key
            )
            if previous != compiled:
                raise ValueError("Delivery chain would replace an objective binding")
        else:
            result["bindings"].append(compiled)
        binding_keys.add(key)
        if item:
            turnin = dict(
                reference_id=row["reference_id"],
                action_id=action,
                node_id=node_id,
                choice_id=choice["id"],
                item_reference=item[0],
                quantity=item[1],
            )
            previous = [
                entry
                for entry in result.setdefault("turnins", [])
                if (
                    entry["reference_id"],
                    entry["action_id"],
                    entry["node_id"],
                    entry["choice_id"],
                )
                == key
            ]
            if previous and previous != [turnin]:
                raise ValueError("Delivery chain would replace an item payment")
            if not previous:
                result["turnins"].append(turnin)

    for entry in manifest["quests"]:
        quest, root = entry["quest_id"], entry["running_root"]
        definition = definitions[quest]
        if (
            definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or any(definition.get(key) != 0 for key in ("cjU", "cjL", "getDuration"))
        ):
            raise ValueError(
                "Delivery archetype requires a nonrecurring native mission"
            )
        if quest in published and published[quest] != definition:
            raise ValueError("Delivery chain would replace a native quest definition")
        if quest not in published:
            result["definitions"].append(deepcopy(definition))
        published[quest] = definition
        if str(quest) in roots and roots[str(quest)] != root:
            raise ValueError("Delivery chain would replace a reviewed running root")
        roots[str(quest)] = root
        matched = 0
        for choice in nodes[root]["choices"]:
            if choice["type"] == 10:
                edge(root, choice["id"], 0)
            elif choice["type"] == 8:
                binding(quest, root, choice, payment=True)
                edge(root, choice["id"], 0)
                matched += 1
        if not matched:
            raise ValueError("Delivery root has no exact native payments")
        previous = entry["after_quest"]
        link = {"after_quest": previous, "start_quest": quest}
        if definition["cjI"].replace(" ", "") != f"IsAchievementComplete({previous})":
            link.update(policy="reconstructed_narrative", evidence=entry["evidence"])
        if link not in result.setdefault("activation_links", []):
            result["activation_links"].append(link)
        if entry.get("root_branches"):
            placement.setdefault("running_root_branches", {})[str(quest)] = deepcopy(
                entry["root_branches"]
            )
        for talk in entry.get("talk_edges", []):
            node = nodes[talk["node_id"]]
            choice = next(c for c in node["choices"] if c["id"] == talk["choice_id"])
            binding(quest, node["id"], choice, payment=False)
            edge(node["id"], choice["id"], talk["target_node_id"])
            for option in node["choices"]:
                if option["type"] == 10:
                    edge(node["id"], option["id"], 0)
    for node, choice, target in manifest.get("edges", []):
        if node not in nodes or not any(
            c["id"] == choice for c in nodes[node]["choices"]
        ):
            raise ValueError("Reviewed dialogue edge is not native")
        edge(node, choice, target)
    placement["graph"] = [
        [node, choice, target] for (node, choice), target in graph.items()
    ]
    conversation.validate_rules(result)
    return result
