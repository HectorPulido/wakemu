"""Compile reviewed standalone story/talk/payment declarations additively.

Placement, graph and opening events are explicit reconstructed evidence. Native
definitions, item quantities and objective criteria remain authoritative; an
NPC portrait/name or a translated verb never authorizes a quest completion.
"""

from copy import deepcopy
from dataclasses import asdict
import ast

from . import conversation
from .conversation_authoring import objective_predicates


def _native_active_objective_guard(expression, quest_id, objective_id):
    """Require native conjunctive quest and target authority before selection."""
    from wakfu_server.combat_local_criteria import parse_local_criterion

    tree = parse_local_criterion(" ".join(expression.split()))
    pending = [tree.body if isinstance(tree, ast.Expression) else tree]
    leaves = []
    while pending:
        node = pending.pop()
        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, ast.And):
                return False
            pending.extend(node.values)
        else:
            leaves.append(node)

    def call(node, name, identity):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
            and node.args[0].value == identity
        )

    return any(call(n, "IsAchievementActive", quest_id) for n in leaves) and any(
        isinstance(n, ast.UnaryOp)
        and isinstance(n.op, ast.Not)
        and call(n.operand, "IsAchievementObjectiveComplete", objective_id)
        for n in leaves
    )


def native_objective_authority(entry, node, choice, nodes, placement, declaration):
    """Qualify an opt-in native node guard through a reviewed dialogue path.

    A guard inherited from an earlier node must dominate the bound terminal
    choice from every published opening. Its unchanged expression is also
    rechecked on the terminal choice, so cached dialogue cannot retain stale
    quest authority after a state mutation.
    """
    expression = choice["criteria"]
    if entry.get("native_node_qualified", False) and "native_guard_path" in entry:
        raise ValueError("Choose one native objective qualification mode")
    if entry.get("native_node_qualified", False) is not False:
        if entry["native_node_qualified"] is not True:
            raise ValueError("Native node qualification must be explicit")
        guard = node["criteria"]
    elif "native_guard_path" in entry:
        path = entry["native_guard_path"]
        if not isinstance(path, list) or not path:
            raise ValueError("Missing native guarded dialogue path")
        if any(
            not isinstance(edge, list)
            or len(edge) != 3
            or any(type(value) is not int for value in edge)
            for edge in path
        ):
            raise ValueError("Invalid native guarded dialogue edge")
        graph = {(n, c): target for n, c, target in placement["graph"]}
        for n, c, target in declaration["graph"]:
            if (n, c) in graph and graph[n, c] != target:
                raise ValueError("Guarded path would replace an existing edge")
            graph[n, c] = target
        for index, edge in enumerate(path):
            if (
                not isinstance(edge, list)
                or len(edge) != 3
                or any(type(value) is not int for value in edge)
            ):
                raise ValueError("Invalid native guarded dialogue edge")
            n, c, target = edge
            if (
                n not in nodes
                or graph.get((n, c)) != target
                or not any(row["id"] == c for row in nodes[n]["choices"])
                or (index + 1 < len(path) and target != path[index + 1][0])
            ):
                raise ValueError("Guarded path differs from reviewed native graph")
        if path[-1] != [node["id"], choice["id"], 0]:
            raise ValueError("Guarded path must close at the bound acknowledgement")
        start = path[0][0]
        openings = set(placement.get("native_opening_roots", []))
        openings.update(declaration.get("native_opening_roots", []))
        openings.add(placement["row"]["dialogue_root"])
        openings.update(placement.get("running_roots", {}).values())
        if start not in openings:
            raise ValueError("Native guarded path must begin at a published opening")
        reachable, pending = set(), list(openings - {start})
        while pending:
            current = pending.pop()
            if current == start or current in reachable or not current:
                continue
            reachable.add(current)
            pending.extend(
                target for (source, _), target in graph.items() if source == current
            )
        if node["id"] in reachable:
            raise ValueError(
                "Native objective guard can be bypassed by another opening"
            )
        # Every step after the opening must have only the reviewed predecessor.
        # Otherwise a different choice from the same opening could bypass a
        # guarded choice even though the opening node itself dominates it.
        for previous, current in zip(path, path[1:]):
            incoming = {
                (n, c) for (n, c), target in graph.items() if target == current[0]
            }
            if incoming != {(previous[0], previous[1])}:
                raise ValueError(
                    "Native objective guard path has an alternate predecessor"
                )
        guards = []
        for n, c, _ in path:
            native_choice = next(row for row in nodes[n]["choices"] if row["id"] == c)
            for predicate in (nodes[n]["criteria"], native_choice["criteria"]):
                if predicate.strip() and predicate not in guards:
                    guards.append(predicate)
        guard = " && ".join(f"({predicate})" for predicate in guards)
    else:
        return expression, None
    if not isinstance(guard, str) or not guard.strip():
        raise ValueError("Native objective qualification requires a native node guard")
    parts = (guard,) if "native_guard_path" in entry else (guard, expression)
    qualified = " && ".join(f"({part})" for part in parts if part.strip())
    return qualified, guard


def validate_reviewed_site_placement(declaration, placement, site_sources, site_floors):
    """Require explicit reconstruction provenance and supplied native site/floor proof."""
    row = placement["row"]
    proof = declaration["reviewed_site_placement"]
    source = (site_sources or {}).get(proof.get("source_id"))
    floor = (site_floors or {}).get(row["map_id"])
    if (
        type(proof.get("source_id")) is not int
        or proof["source_id"] <= 0
        or source is None
        or source.get("id") != proof["source_id"]
        or source.get("map_id") != row["map_id"]
        or floor is None
        or not isinstance(proof.get("geometry_sha256"), str)
        or len(proof["geometry_sha256"]) != 64
        or any(char not in "0123456789abcdef" for char in proof["geometry_sha256"])
        or floor.get("source_sha256") != proof["geometry_sha256"]
        or not isinstance(proof.get("evidence"), str)
        or not proof["evidence"].strip()
        or "REVIEWED SITE-DERIVED RECONSTRUCTION" not in row["provenance"]
    ):
        raise ValueError(
            "Reviewed site placement lacks qualified native source/floor context"
        )
    cells = {tuple(cell) for cell in floor["cells"]}
    edges = {(tuple(a), tuple(b)) for a, b in floor["edges"]}
    position = row["x"], row["y"], row["z"]
    anchor = placement.get("interaction_anchor", {})
    approach = anchor.get("x"), anchor.get("y"), anchor.get("z")
    if (
        position not in cells
        or approach not in cells
        or max(abs(position[i] - approach[i]) for i in (0, 1)) > 1
        or not any(a == approach and a != b and (b, a) in edges for a, b in edges)
    ):
        raise ValueError(
            "Reviewed site placement lacks a connected native floor approach"
        )


def extend(
    document,
    definitions,
    nodes,
    speakers,
    manifest,
    *,
    site_sources=None,
    site_floors=None,
):
    if manifest.get("schema") != "native-story-conversations-v1":
        raise ValueError("Unsupported native story reconstruction manifest")
    result = deepcopy(document)
    by_id = {entry["d"]: entry for entry in result["definitions"]}
    for declaration in manifest["speakers"]:
        quest_ids = declaration["quest_ids"]
        for identity in quest_ids:
            definition = definitions[identity]
            if (
                definition.get("native_class") != "aJM"
                or definition.get("aqb") is not False
                or any(
                    definition.get(field) != 0
                    for field in ("cjU", "cjL", "getDuration")
                )
            ):
                raise ValueError(
                    "Story archetype requires an untimed nonrecurring native quest"
                )
            if identity in by_id and by_id[identity] != definition:
                raise ValueError(
                    "Story reconstruction would replace a native definition"
                )
            if identity not in by_id:
                result["definitions"].append(deepcopy(definition))
                by_id[identity] = definition
        actor = declaration["actor_id"]
        matches = [
            item for item in result["placements"] if item["row"]["actor_id"] == actor
        ]
        if len(matches) > 1:
            raise ValueError("Ambiguous story speaker placement")
        if matches:
            placement = matches[0]
            if "placement" in declaration and placement != declaration["placement"]:
                # A replay may already contain the additive graph/starts below.
                if placement["row"] != declaration["placement"]["row"]:
                    raise ValueError(
                        "Story reconstruction would move an existing speaker"
                    )
        else:
            placement = deepcopy(declaration["placement"])
            if placement["row"]["actor_id"] != actor:
                raise ValueError("Story actor differs from its reviewed placement")
            row = placement["row"]
            if "reviewed_site_placement" in declaration:
                validate_reviewed_site_placement(
                    declaration, placement, site_sources, site_floors
                )
            else:
                anchor = declaration["native_marker"]
                objective = next(
                    o
                    for o in definitions[anchor["quest_id"]]["cjJ"]
                    if o["d"] == anchor["objective_id"]
                )
                if not any(
                    (mark["ckj"], mark["ckg"], mark["ckh"], mark["cki"])
                    == (row["map_id"], row["x"], row["y"], row["z"])
                    for mark in objective["ckd"]
                ):
                    raise ValueError(
                        "Reconstructed placement differs from its declared native marker"
                    )
            if (
                not row["provenance"].startswith(
                    "wakemu.qualified-quest-conversation.v1:"
                )
                or row["reference_id"] not in speakers
                or not set(row["action_ids"])
                <= {action["id"] for action in speakers[row["reference_id"]]["actions"]}
            ):
                raise ValueError("Story placement lacks a native speaker/action")
            result["placements"].append(placement)
        reviewed = declaration.get("placement", {})
        if "interaction_anchor" in reviewed:
            anchor = reviewed["interaction_anchor"]
            if (
                "interaction_anchor" in placement
                and placement["interaction_anchor"] != anchor
            ):
                raise ValueError(
                    "Story reconstruction would replace an interaction anchor"
                )
            placement["interaction_anchor"] = deepcopy(anchor)
            placement["interaction_anchor_evidence"] = reviewed[
                "interaction_anchor_evidence"
            ]
        for field in ("choice_starts", "choice_criteria"):
            for admission in reviewed.get(field, []):
                if (
                    field == "choice_starts"
                    and admission.get("quest_id") not in quest_ids
                ):
                    raise ValueError("Reviewed quest start is outside declared story")
                entries = placement.setdefault(field, [])
                key = admission["node_id"], admission["choice_id"]
                existing = [
                    entry
                    for entry in entries
                    if (entry["node_id"], entry["choice_id"]) == key
                ]
                if existing and existing != [admission]:
                    raise ValueError(
                        "Story reconstruction would replace reviewed admission"
                    )
                if not existing:
                    entries.append(deepcopy(admission))
        for identity, guard in reviewed.get("opening_quest_criteria", {}).items():
            guards = placement.setdefault("opening_quest_criteria", {})
            if identity in guards and guards[identity] != guard:
                raise ValueError("Story reconstruction would replace opening admission")
            guards[identity] = guard
        for identity, root in declaration.get("running_roots", {}).items():
            if (
                not isinstance(identity, str)
                or not identity.isdigit()
                or int(identity) not in quest_ids
                or root not in nodes
            ):
                raise ValueError("Invalid reviewed story stage root")
            roots = placement.setdefault("running_roots", {})
            if identity in roots and roots[identity] != root:
                raise ValueError("Story reconstruction would replace a stage root")
            roots[identity] = root
        if "native_opening_roots" in declaration:
            from wakfu_server.native_npc_roots import validate as validate_roots

            opening_roots = declaration["native_opening_roots"]
            validate_roots(opening_roots, nodes)
            if (
                placement["activation_policy"] != "already_running"
                or placement["row"]["dialogue_root"] not in opening_roots
                or any(
                    root not in opening_roots
                    for root in placement.get("native_opening_roots", [])
                )
            ):
                raise ValueError(
                    "Story reconstruction would replace native opening roots"
                )
            placement["native_opening_roots"] = deepcopy(opening_roots)
        row = placement["row"]
        if declaration["action_id"] != row["action_ids"][0]:
            raise ValueError("Story action differs from its placement binding")
        starts = placement.setdefault("available_quests_on_open", [])
        for identity in declaration.get("available_quests_on_open", []):
            if identity not in quest_ids:
                raise ValueError("Opening activation is outside the declared story")
            if identity not in starts:
                starts.append(identity)
        graph = {(node, choice): target for node, choice, target in placement["graph"]}
        for arrival in declaration.get("choice_approach_arrivals", []):
            from wakfu_server.quest_npc import qualify_approach_arrival

            candidate = deepcopy(arrival)
            path = candidate.pop("native_guard_path")
            node = nodes[candidate["node_id"]]
            choice = next(
                c for c in node["choices"] if c["id"] == candidate["choice_id"]
            )
            _, guard = native_objective_authority(
                {"native_guard_path": path}, node, choice, nodes, placement, declaration
            )
            qualify_approach_arrival(
                (site_sources or {}).get(candidate["source_object_id"]), candidate
            )
            arrivals = placement.setdefault("choice_approach_arrivals", [])
            if candidate not in arrivals:
                if any(
                    (a["node_id"], a["choice_id"])
                    == (candidate["node_id"], candidate["choice_id"])
                    for a in arrivals
                ):
                    raise ValueError(
                        "Story reconstruction would replace an exterior approach"
                    )
                arrivals.append(candidate)
            criteria = dict(
                node_id=candidate["node_id"],
                choice_id=candidate["choice_id"],
                criterion=guard,
                evidence="Original native guarded travel path is rechecked on the final actual script departure; this reaches only the public exterior approach and never admits or completes the remote entrance.",
            )
            if criteria not in placement.setdefault("choice_criteria", []):
                placement["choice_criteria"].append(criteria)
        for destination in declaration.get("choice_routes", []):
            if (
                not isinstance(destination, dict)
                or set(destination) != {"node_id", "choice_id", "route", "evidence"}
                or not isinstance(destination["route"], str)
                or not destination["route"].strip()
                or not isinstance(destination["evidence"], str)
                or not destination["evidence"].strip()
                or not any(
                    (n, c) == (destination["node_id"], destination["choice_id"])
                    for n, c, _ in declaration["graph"]
                )
                or destination["node_id"] not in nodes
                or not any(
                    c["id"] == destination["choice_id"]
                    for c in nodes[destination["node_id"]]["choices"]
                )
            ):
                raise ValueError("Invalid reviewed native NPC choice route")
            routes = placement.setdefault("choice_routes", [])
            if destination not in routes:
                if any(
                    (r["node_id"], r["choice_id"])
                    == (destination["node_id"], destination["choice_id"])
                    for r in routes
                ):
                    raise ValueError(
                        "Story reconstruction would replace a choice route"
                    )
                routes.append(deepcopy(destination))
        for arrival in declaration.get("choice_paired_arrivals", []):
            from wakfu_server.npc_paired_travel import validate_paired_arrival

            source = deepcopy(placement)
            source["graph"] = placement["graph"] + declaration["graph"]
            validate_paired_arrival(result["placements"], source, arrival)
            node = nodes[arrival["node_id"]]
            if not any(c["id"] == arrival["choice_id"] for c in node["choices"]):
                raise ValueError("Paired journey requires an original native choice")
            arrivals = placement.setdefault("choice_paired_arrivals", [])
            if arrival not in arrivals:
                if any(
                    (a["node_id"], a["choice_id"])
                    == (arrival["node_id"], arrival["choice_id"])
                    for a in arrivals
                ):
                    raise ValueError(
                        "Story reconstruction would replace a paired NPC journey"
                    )
                arrivals.append(deepcopy(arrival))
        for spoken in declaration.get("spoken_objectives", []):
            if (
                not isinstance(spoken, dict)
                or set(spoken) != {"quest_id", "objective_id", "action_ids", "evidence"}
                or spoken["quest_id"] not in quest_ids
                or spoken["objective_id"]
                not in {o["d"] for o in definitions[spoken["quest_id"]]["cjJ"]}
                or not isinstance(spoken["action_ids"], list)
                or not spoken["action_ids"]
                or any(type(action) is not int for action in spoken["action_ids"])
                or len(set(spoken["action_ids"])) != len(spoken["action_ids"])
                or not set(spoken["action_ids"]) <= set(placement["row"]["action_ids"])
                or not isinstance(spoken["evidence"], str)
                or not spoken["evidence"].strip()
            ):
                raise ValueError("Invalid reviewed native NPC spoken source")
            declarations = placement.setdefault("spoken_objectives", [])
            if spoken not in declarations:
                if any(
                    (d["quest_id"], d["objective_id"])
                    == (spoken["quest_id"], spoken["objective_id"])
                    for d in declarations
                ):
                    raise ValueError(
                        "Story reconstruction would replace an NPC spoken source"
                    )
                declarations.append(deepcopy(spoken))
        for entry in declaration["objectives"]:
            identity, objective = entry["quest_id"], entry["objective_id"]
            if identity not in quest_ids:
                raise ValueError("Objective is outside the reviewed story")
            node = nodes[entry["node_id"]]
            choice = next(c for c in node["choices"] if c["id"] == entry["choice_id"])
            definition = definitions[identity]
            mode = entry["archetype"]
            if mode not in ("talk", "deliver"):
                raise ValueError("Unsupported native conversation archetype")
            expression, native_guard = native_objective_authority(
                entry, node, choice, nodes, placement, declaration
            )
            if (
                entry.get("running_branch") is not None
                and not entry.get("branch_binding")
                and _native_active_objective_guard(expression, identity, objective)
            ):
                # The explicit reviewed selector is also rechecked on the
                # terminal choice below. Qualify Active-only native branches
                # against that same running state during source compilation.
                expression = (
                    f"({expression}) && "
                    f"IsAchievementRunning({entry['running_branch']})"
                )
            found, item = objective_predicates(
                expression,
                identity,
                {o["d"] for o in definition["cjJ"]},
                payment=mode == "deliver",
                payment_basket=entry.get("payment_basket", False),
                single_objective=entry.get("single_objective", False),
                item_absence_guard=entry.get("item_absence_guard", False),
                running_branch=entry.get("running_branch"),
                remaining_objective=objective
                if entry.get("remaining_objective")
                else None,
                required_objectives=entry.get("required_objectives", ()),
            )
            if found != objective:
                raise ValueError(
                    "Reconstructed objective differs from the native offered predicate"
                )
            extra_guard = None
            if (
                entry.get("branch_binding") is not None
                and entry["branch_binding"] is not True
            ):
                raise ValueError("Conditional native binding must be explicit")
            if entry.get("branch_binding") and entry.get("running_branch") != identity:
                raise ValueError(
                    "Conditional binding requires its exact native running branch"
                )
            if entry.get("running_branch") is not None and not entry.get(
                "branch_binding"
            ):
                extra_guard = f"IsAchievementRunning({identity})"
            if entry.get("remaining_objective"):
                extra_guard = " && ".join(
                    [
                        f"IsAchievementRunning({identity})",
                        *(
                            f"IsAchievementObjectiveComplete({prior})"
                            for prior in entry["required_objectives"]
                        ),
                    ]
                )
            if native_guard:
                extra_guard = " && ".join(
                    f"({part})" for part in (native_guard, extra_guard) if part
                )
            if extra_guard:
                guard = dict(
                    node_id=node["id"],
                    choice_id=choice["id"],
                    criterion=extra_guard,
                    evidence="Reviewed selected native quest branch / final objective requires this owned running quest and earned preceding objectives.",
                )
                guards = placement.setdefault("choice_criteria", [])
                if guard not in guards:
                    guards.append(guard)
            compiled = asdict(
                conversation.QualifiedConversation(
                    identity,
                    objective,
                    row["reference_id"],
                    declaration["action_id"],
                    node["id"],
                    choice["id"],
                    conversation.placement_signature(row),
                    conversation._digest(definition),
                )
            )
            key = (
                compiled["reference_id"],
                compiled["action_id"],
                node["id"],
                choice["id"],
            )
            previous = [
                binding
                for binding in result["bindings"]
                if (
                    binding["reference_id"],
                    binding["action_id"],
                    binding["node_id"],
                    binding["choice_id"],
                )
                == key
            ]
            if previous and previous != [compiled]:
                if not entry.get("branch_binding") or (
                    previous[0]["quest_id"] == identity
                    and previous[0]["placement_sha256"] == compiled["placement_sha256"]
                ):
                    raise ValueError(
                        "Story reconstruction would replace a bound objective"
                    )
                alternatives = result.setdefault("alternative_bindings", [])
                existing = [
                    binding
                    for binding in alternatives
                    if (
                        binding["reference_id"],
                        binding["action_id"],
                        binding["node_id"],
                        binding["choice_id"],
                        binding["quest_id"],
                        binding["placement_sha256"],
                    )
                    == (*key, identity, compiled["placement_sha256"])
                ]
                if existing and existing != [compiled]:
                    raise ValueError(
                        "Story reconstruction would replace a conditional native binding"
                    )
                if not existing:
                    alternatives.append(compiled)
            elif not previous:
                result["bindings"].append(compiled)
            if item:
                payment = dict(
                    reference_id=row["reference_id"],
                    action_id=declaration["action_id"],
                    node_id=node["id"],
                    choice_id=choice["id"],
                )
                if entry.get("payment_basket", False):
                    payment["items"] = [
                        dict(item_reference=reference, quantity=quantity)
                        for reference, quantity in item
                    ]
                else:
                    payment.update(item_reference=item[0], quantity=item[1])
                existing = [
                    value
                    for value in result.setdefault("turnins", [])
                    if (
                        value["reference_id"],
                        value["action_id"],
                        value["node_id"],
                        value["choice_id"],
                    )
                    == key
                ]
                if existing and existing != [payment]:
                    raise ValueError(
                        "Story reconstruction would replace an item requirement"
                    )
                if not existing:
                    result["turnins"].append(payment)
        for node_id, choice_id, target in declaration["graph"]:
            if (
                node_id not in nodes
                or target != 0
                and target not in nodes
                or not any(c["id"] == choice_id for c in nodes[node_id]["choices"])
            ):
                raise ValueError("Story graph contains a nonnative node or choice")
            if (node_id, choice_id) in graph and graph[node_id, choice_id] != target:
                raise ValueError("Story reconstruction would replace an existing edge")
            graph[node_id, choice_id] = target
        for entry in declaration["objectives"]:
            if (entry["node_id"], entry["choice_id"]) not in graph:
                raise ValueError("Bound story objective has no reviewed native edge")
        placement["graph"] = [
            [node, choice, target] for (node, choice), target in graph.items()
        ]
    for link in manifest.get("activation_links", []):
        if (
            link["after_quest"] not in by_id
            or link["start_quest"] not in by_id
            or not isinstance(link.get("evidence"), str)
            or not link["evidence"].strip()
            or link.get("policy") != "reconstructed_narrative"
        ):
            raise ValueError("Missing reviewed story prerequisite link")
        if link not in result.setdefault("activation_links", []):
            result["activation_links"].append(deepcopy(link))
    conversation.validate_rules(result)
    return result
