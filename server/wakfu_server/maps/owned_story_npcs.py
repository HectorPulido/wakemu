"""Native noncombat NPCs inside authenticated, owner-scoped story instances.

Templates carry explicit reviewed placements and native dialogue edges. Rendering
never advances a quest; only an accepted scoped dialogue choice emits a trusted
npc_spoken event through the common mission toolkit.
"""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from wakfu_server import (
    npc_dialogue,
    npc_world,
    owned_story_controller,
    owned_story_refresh,
)
from wakfu_server.achievements import mission_toolkit, storage
from wakfu_server.dungeon_achievement_authority import queries_from_state

SOURCE_FILES = {
    "wild-temple-718-air.json": "a62cc9d68aeeeff2c1c6ef6284855dc6394173475bab65cb50dc5c7c98afc61d",
    "wild-temple-718-earth.json": "7143503f20ced9016caa40d94d76e2276e995d5b13c6a33ca78b89469288304f",
    "wild-temple-718-fire.json": "11451cfb00e46012ba4c03f9f03f84822c51dabe8024d6ce6d2b90a8b2bc7d45",
    "wild-temple-718-water.json": "b70bbcb8ce7aee119840955c9a741bbd0e52d2a1db47130a1608ac5aaf3d89a1",
    "wild-estate-chief-726-return.json": "03731284c46596c3da1a7b3be1dab87453a4c5247f413cee2392b2d8d0074e6b",
    "wild-estate-sufokia-715-wool.json": "8d775b246563ec4a5c44f9520c14e8cb1eea645d4a48e8bde6ce3abd438d3afd",
    "wild-estate-chief-726.json": "fe56693b188b37e4356343a8eefb23fc9ff07bfe07de5e28a6d48614a237bb82",
    "bilbyza-raft-557.dj-candidate.json": "2343e8e1bafc2d602f566b76592ae8609409f11fd34f56de3939fed83b08a87b",
    "kelba-cave-952-2547.json": "8e2d06e40e6c66582431df98358317a3a37046667e008cb37cbd661c7ec9bf53",
    "kelba-cave-952-2548.json": "a70c04e24aa4a8bba9b9286426770522cdb182fc187f04782fe9937931ea4da9",
    "wild-estate-sufokia-715-start.json": "e24a1bce02e8a7baee0cd90e0e33dba8cc3b08f4a0c459c609f655c115f16a23",
    "wild-estate-sufokia-715-debrief.json": "3ab971df13090994807d0cf601d8a50601e7f939fd5fb3e64f22051adf9f2600",
    "whisper-prison-1299.json": "7c9d35f29f37aadfacfd4add0c35c84b326c90519efc57a335fc576a09436558",
    "zinit-shore-980.json": "4a494224766d4ec62d3e1aa268ce1bd0d38c37228307d905f4303ae1bd3d49f8",
    "kelba-port-946.json": "d7696c464cee547e74a7eed5212b418be36495fd896bf4a342687718bb1f4803",
    "kelba-shop-945-late.json": "9d5fbb53d5bba55be5ff1bab738726880298a936c12a326a14dc4749779f6daf",
    "kelba-hideout-948.json": "873c89f2ebcaf723a67ebe316215d2a810db8310405ace05097ed4632ffc905e",
}
# 065_dungeon_instances.sql allocates monotonically after this namespace base.
# Strip the fixed namespace by subtraction, never modulo/hash the actual ID.
INSTANCE_NAMESPACE = 1 << 57


@lru_cache(maxsize=1)
def profiles():
    result = []
    for filename, digest in SOURCE_FILES.items():
        path = Path(__file__).with_name("owned_story_npc_profiles") / filename
        source = path.read_bytes()
        if sha256(source).hexdigest() != digest:
            raise ValueError("Owned story NPC source has not been reviewed")
        profile = json.loads(source)
        if (
            profile.get("schema") != "owned-story-npcs-v1"
            or type(profile.get("id")) is not str
            or not profile["id"]
            or type(profile.get("controller_id")) is not str
            or any(
                type(profile.get(k)) is not int or profile[k] <= 0
                for k in ("map_id", "quest_id", "policy_version")
            )
            or not isinstance(profile.get("requires"), list)
            or any(type(flag) is not str or not flag for flag in profile["requires"])
            or "until" in profile
            and (
                not isinstance(profile["until"], list)
                or any(type(flag) is not str or not flag for flag in profile["until"])
            )
            or "render_requires" in profile
            and (
                not isinstance(profile["render_requires"], list)
                or any(
                    type(flag) is not str or not flag
                    for flag in profile["render_requires"]
                )
            )
            or not isinstance(profile.get("npcs"), list)
            or not profile["npcs"]
            or "physical_visit" in profile
            and type(profile["physical_visit"]) is not bool
        ):
            raise ValueError("Invalid owned story NPC profile")
        seen = set()
        for row in profile["npcs"]:
            direct = row.get("controller_reference") is not None
            identities = (
                ("template_id", "reference_id", "controller_reference")
                if direct
                else (
                    "template_id",
                    "reference_id",
                    "dialogue_root",
                    "choice_id",
                    "objective_id",
                )
            )
            if (
                any(type(row.get(k)) is not int or row[k] <= 0 for k in identities)
                or direct
                and row.get("action_type") not in (1, 4)
                or direct
                and row["controller_reference"] != row["reference_id"]
                or row["template_id"] >= 1024
                or row["template_id"] in seen
                or not isinstance(row.get("action_ids"), list)
                or len(row["action_ids"]) != 1
                or type(row["action_ids"][0]) is not int
                or type(row.get("action_criterion")) is not str
                or not row.get("provenance")
            ):
                raise ValueError("Invalid owned story NPC template")
            seen.add(row["template_id"])
            _item_turn_in(row)
            if row.get("controller_target_id") is not None and (
                not direct
                or row.get("action_type") != 1
                or row["controller_target_id"] != row["template_id"]
            ):
                raise ValueError(
                    "Owned native target requires its exact type1 template"
                )
            if "controller_choice_reference" in row and (
                direct
                or type(row["controller_choice_reference"]) is not int
                or row["controller_choice_reference"] != row["choice_id"]
                or not row.get("graph")
                or not row.get("native_guard_path")
            ):
                raise ValueError(
                    "Owned story confirmation requires its exact guarded native choice"
                )
        if profile.get("native_action_source") is not None:
            from wakfu_server import owned_story_npc_sources

            owned_story_npc_sources.catalog(profile)
        result.append(profile)
    return tuple(result)


def _item_turn_in(row):
    declaration = row.get("item_turn_in")
    if declaration is None:
        return None
    if (
        not isinstance(declaration, dict)
        or set(declaration)
        != {
            "reference",
            "quantity",
            "output_reference",
            "output_quantity",
            "required_objectives",
            "evidence",
        }
        or any(
            type(declaration[key]) is not int or declaration[key] <= 0
            for key in ("reference", "quantity", "output_reference", "output_quantity")
        )
        or declaration["quantity"] > 32767
        or declaration["output_quantity"] > 32767
        or not isinstance(declaration["required_objectives"], list)
        or any(
            type(value) is not int or value <= 0
            for value in declaration["required_objectives"]
        )
        or len(set(declaration["required_objectives"]))
        != len(declaration["required_objectives"])
        or not isinstance(declaration["evidence"], str)
        or not declaration["evidence"].strip()
    ):
        raise ValueError("Owned dialogue item exchange lacks reviewed finite authority")
    return declaration


def actor_id(instance_id, template_id):
    if (
        type(instance_id) is not int
        or instance_id <= INSTANCE_NAMESPACE
        or type(template_id) is not int
        or not 0 < template_id < 1024
    ):
        raise ValueError("Invalid owned story NPC identity")
    ordinal = instance_id - INSTANCE_NAMESPACE
    identity = npc_world.MIN_ID + ordinal * 1024 + template_id
    if not npc_world.MIN_ID <= identity <= npc_world.MAX_ID:
        raise ValueError("Owned story NPC identity exceeds native range")
    return identity


def direct_action_placement(row):
    """Attest a source-declared native direct actor without inventing dialogue."""
    if row.get("controller_reference") is None:
        return False
    for profile in profiles():
        if profile["map_id"] != row.get("map_id"):
            continue
        for template in profile["npcs"]:
            if template.get("controller_reference") is None:
                continue
            if all(row.get(key) == value for key, value in template.items()):
                return row.get("actor_id") == actor_id(
                    row.get("instance_id"), template["template_id"]
                )
    return False


def dialogue_placement(row):
    """Attest a reviewed private dialogue template, never a public actor alias."""
    if row.get("controller_reference") is not None:
        return False
    for profile in profiles():
        if profile["map_id"] != row.get("map_id"):
            continue
        for template in profile["npcs"]:
            if template.get("controller_reference") is not None:
                continue
            if all(row.get(key) == value for key, value in template.items()):
                return row.get("actor_id") == actor_id(
                    row.get("instance_id"), template["template_id"]
                )
    return False


def _dialogue_contract(profile, row, native):
    """Compile a bounded native graph with one source-qualified terminal fact."""
    nodes = native["node_index"]
    root = row["dialogue_root"]
    edges = row.get("graph")
    if edges is None:
        allowed = [row["choice_id"]]
        if row.get("exit_choice_id") is not None:
            allowed.append(row["exit_choice_id"])
        return {(root, choice): None for choice in allowed}, [root], root, ""
    if (
        not isinstance(edges, list)
        or not edges
        or len(edges) > 128
        or any(
            not isinstance(edge, list)
            or len(edge) != 3
            or any(type(value) is not int for value in edge)
            for edge in edges
        )
    ):
        raise ValueError("Invalid owned native dialogue graph")
    graph = {}
    for node_id, choice_id, target in edges:
        if (
            node_id not in nodes
            or target != 0
            and target not in nodes
            or not any(c["id"] == choice_id for c in nodes[node_id]["choices"])
            or (node_id, choice_id) in graph
        ):
            raise ValueError("Owned dialogue edge differs from native source")
        graph[node_id, choice_id] = target or None
    from wakfu_server.native_npc_roots import validate
    from wakfu_server.achievements.conversation_story_authoring import (
        native_objective_authority,
    )
    from wakfu_server.achievements.conversation_authoring import objective_predicates

    roots = list(validate(row.get("native_opening_roots", [root]), nodes))
    if root not in roots:
        raise ValueError("Owned dialogue lacks its native default greeting")
    reachable, pending = set(), list(roots)
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(
            target
            for (source, _), target in graph.items()
            if source == current and target is not None
        )
    if any(node_id not in reachable for node_id, _ in graph):
        raise ValueError("Owned dialogue graph contains a disconnected edge")
    terminal = row.get("binding_node_id", root)
    choice = next(
        (
            c
            for c in nodes.get(terminal, {}).get("choices", [])
            if c["id"] == row["choice_id"]
        ),
        None,
    )
    if choice is None or graph.get((terminal, row["choice_id"]), -1) is not None:
        raise ValueError("Owned dialogue fact requires its exact terminal choice")
    expression, guard = native_objective_authority(
        {"native_guard_path": row.get("native_guard_path")},
        nodes[terminal],
        choice,
        nodes,
        {"row": {"dialogue_root": root}, "graph": edges, "native_opening_roots": roots},
        {"graph": []},
    )
    exchange = _item_turn_in(row)
    objective, payment = objective_predicates(
        expression,
        profile["quest_id"],
        {row["objective_id"]},
        payment=exchange is not None,
        single_objective=True,
    )
    expected_payment = (
        None if exchange is None else (exchange["reference"], exchange["quantity"])
    )
    if objective != row["objective_id"] or payment != expected_payment:
        raise ValueError("Owned dialogue terminal lacks native quest authority")
    return graph, roots, terminal, guard


def _rows(db, store, character, *, rendering=False):
    candidates = [p for p in profiles() if p["map_id"] == character.get("map_id")]
    if not candidates or not character.get("instance_id"):
        return []
    if not owned_story_controller.recognizes_instance(db, character["instance_id"]):
        return []
    selected, completed = owned_story_controller._scope(
        db, store, character, check_position=not rendering
    )
    version = db.execute(
        "SELECT context_policy_version FROM dungeon_instances WHERE instance_id=%s",
        (character["instance_id"],),
    ).fetchone()
    if version is None or (
        not rendering and owned_story_refresh.pending(db, store, character) is not None
    ):
        return []
    state = storage.load_locked(db, character["id"])
    result = []
    for profile in candidates:
        if (
            selected["id"] != profile["controller_id"]
            or version["context_policy_version"] != profile["policy_version"]
            or not set(
                profile.get("render_requires", profile["requires"])
                if rendering
                else profile["requires"]
            )
            <= completed
            or set(profile.get("until", ())) & completed
            or not profile.get("physical_visit", False)
            and profile["quest_id"]
            not in set(state["running"]) | set(state["completed"])
        ):
            continue
        for template in profile["npcs"]:
            row = dict(
                template,
                actor_id=actor_id(character["instance_id"], template["template_id"]),
                map_id=character["map_id"],
                instance_id=character["instance_id"],
                enabled=True,
            )
            result.append((profile, row, state))
    # One real actor can serve successive native quest branches. Publish and
    # dispatch the running branch before its completed physical-visit provider.
    result.sort(key=lambda item: item[0]["quest_id"] not in item[2]["running"])
    unique = {}
    for item in result:
        unique.setdefault(item[1]["actor_id"], item)
    return list(unique.values())


def rows(db, store, character, *, rendering=False):
    """Return genuine current instance rows for ordinary scene publication."""
    return [row for _, row, _ in _rows(db, store, character, rendering=rendering)]


def spawn_packets(
    db, store, character, *, native=None, language="es", context_bootstrap=False
):
    """Publish actors before the existing owned bootstrap acknowledgment.

    Only the generation-authenticated World bootstrap may request rendering
    during a pending refresh. Talk and cinematic argument resolution retain
    their refresh acknowledgment requirement.
    """
    from wakfu_server import owned_story_npc_sources

    return [
        npc_world.spawn(
            row,
            owned_story_npc_sources.catalog(profile, native),
            language,
            enabled_actions=row["action_ids"],
        )
        for profile, row, _ in _rows(db, store, character, rendering=context_bootstrap)
    ]


def _nearby(character, row):
    return npc_world.nearby(character, row)


def _locked(store, db, account_id, generation, character, identity, action_id=None):
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    store.lock_character(db, account_id, generation, character["id"], selected=True)
    current = store.character(account_id, character["id"], db)
    if current is None or current.get("account_id") != account_id:
        raise ValueError("Owned story NPC lost its selected owner")
    from wakfu_server.environment_interactions import _guard

    _guard(db, current["id"])
    selected = next(
        (item for item in _rows(db, store, current) if item[1]["actor_id"] == identity),
        None,
    )
    if selected is None or not _nearby(current, selected[1]):
        raise ValueError("Owned story NPC is unavailable or outside interaction range")
    if action_id is not None and action_id not in selected[1]["action_ids"]:
        raise ValueError("Unavailable owned story NPC action")
    return current, *selected


def _criterion(store, character, state, text):
    from wakfu_server import quest_npc

    authority = queries_from_state(state)
    return quest_npc._criterion(store, character, text, authority)


def begin(store, account_id, generation, character, identity, action_id):
    with store.connection() as db:
        current, profile, row, state = _locked(
            store, db, account_id, generation, character, identity, action_id
        )
        from wakfu_server import owned_story_npc_sources

        native = owned_story_npc_sources.catalog(profile)
        speaker = next(
            value for value in native["speakers"] if value["ref"] == row["reference_id"]
        )
        action = next(value for value in speaker["actions"] if value["id"] == action_id)
        if row.get("controller_reference") is not None:
            if (
                action["type"] != row.get("action_type", 4)
                or action["criteria"] != row["action_criterion"]
                or not _criterion(store, current, state, action["criteria"])
            ):
                raise ValueError(
                    "Owned story NPC action differs from its original native producer"
                )
            from wakfu_server import owned_story_mechanics

            selected, completed = owned_story_controller._scope(db, store, current)
            if (
                owned_story_controller.pending_scene(
                    db, store, current, selected, completed
                )
                is not None
            ):
                raise ValueError(
                    "Owned story NPC action is waiting for its native cinematic"
                )
            if row.get("controller_target_id") is not None:
                from wakfu_server import owned_story_npc_targets

                return None, owned_story_npc_targets.settle(
                    db,
                    store,
                    current,
                    selected,
                    completed,
                    profile,
                    row,
                    actor_id=identity,
                    action_id=action_id,
                    executor=owned_story_mechanics.executor(selected),
                )
            outcome = owned_story_controller._settle(
                db,
                store,
                current,
                selected,
                completed,
                kind="npc_spoken",
                reference=row["controller_reference"],
                evidence=dict(
                    actor_id=identity,
                    native_reference=row["reference_id"],
                    action_id=action_id,
                ),
                apply_effects=owned_story_mechanics.executor(selected),
            )
            return None, outcome["packets"]
        graph, roots, terminal, terminal_guard = _dialogue_contract(
            profile, row, native
        )
        node = native["node_index"][terminal]
        choice = next(
            value for value in node["choices"] if value["id"] == row["choice_id"]
        )
        if (
            action["criteria"] != row["action_criterion"]
            or choice["type"] != row["choice_type"]
            or not _criterion(store, current, state, action["criteria"])
        ):
            raise ValueError("Owned story dialogue differs from its native contract")
        exit_choice = next(
            (
                value
                for value in node["choices"]
                if value["id"] == row.get("exit_choice_id")
            ),
            None,
        )
        if row.get("exit_choice_id") is not None and (
            exit_choice is None
            or exit_choice["type"] != 10
            or exit_choice["criteria"] != row["exit_criterion"]
        ):
            raise ValueError("Owned story return choice differs from native source")
        allowed_nodes = (
            set(roots)
            | {n for n, _ in graph}
            | {n for n in graph.values() if n is not None}
        )
        context = [current, row, state]
        session = npc_dialogue.DialogueSession(
            native["node_index"],
            graph,
            authorize_node=lambda candidate: context[0] is not None
            and _criterion(
                store, context[0], context[2], candidate.get("criteria", "")
            ),
            authorize_choice=lambda candidate: context[0] is not None
            and any(choice == candidate["id"] for _, choice in graph)
            and _criterion(store, context[0], context[2], candidate.get("criteria", ""))
            and (
                candidate["id"] != row["choice_id"]
                or not terminal_guard
                or _criterion(store, context[0], context[2], terminal_guard)
            )
            and (
                candidate["id"] != row["choice_id"]
                or _item_turn_in(row) is None
                or set(_item_turn_in(row)["required_objectives"])
                <= set(context[2]["objectives"])
            ),
        )
        from wakfu_server.native_npc_roots import select

        opening = select(
            roots,
            native["node_index"],
            available=lambda text: _criterion(store, current, state, text),
        )
        packet = session.open(
            opening,
            identity,
            lambda speaker, root: context[0] is not None
            and speaker == identity
            and root in allowed_nodes
            and _nearby(context[0], context[1]),
        )
        session.owned_story_npc = dict(
            actor_id=identity,
            action_id=action_id,
            profile_id=profile["id"],
            owner_id=current["id"],
            account_id=account_id,
        )
        session.owned_story_npc_context = context
        context[0] = None
        return session, [packet]


def choose(store, account_id, generation, character, session, body):
    request = npc_dialogue.decode_request(12058, body)
    proof = session.owned_story_npc
    if (proof["owner_id"], proof["account_id"]) != (character["id"], account_id):
        raise ValueError("Owned story dialogue changed owner")
    previous = (
        session.node_id,
        session.speaker_id,
        session.authorize_speaker,
        session.previous_choice_id,
    )
    context = session.owned_story_npc_context
    try:
        with store.connection() as db:
            current, profile, row, state = _locked(
                store,
                db,
                account_id,
                generation,
                character,
                proof["actor_id"],
                proof["action_id"],
            )
            if profile["id"] != proof["profile_id"]:
                raise ValueError("Owned story NPC profile changed")
            context[:] = [current, row, state]
            exchange = _item_turn_in(row)
            paid = exchange is not None and (
                request["node_id"] == row.get("binding_node_id", row["dialogue_root"])
                and request["choice_id"] == row["choice_id"]
            )
            paid_packets = []
            if paid:
                from wakfu_server.achievements import (
                    conversation,
                    conversation_turnin,
                    service,
                )

                if not set(exchange["required_objectives"]) <= set(state["objectives"]):
                    raise ValueError(
                        "Owned dialogue exchange requires its earned prerequisites"
                    )
                definition = mission_toolkit.definitions(
                    db, {"activations": [{"quest_id": profile["quest_id"]}]}
                )[profile["quest_id"]]
                if not set(exchange["required_objectives"]) <= {
                    objective["d"] for objective in definition["cjJ"]
                }:
                    raise ValueError(
                        "Owned dialogue exchange prerequisites are not native"
                    )
                binding = conversation.QualifiedConversation(
                    profile["quest_id"],
                    row["objective_id"],
                    row["reference_id"],
                    proof["action_id"],
                    request["node_id"],
                    request["choice_id"],
                    conversation.placement_signature(row),
                    conversation._digest(definition),
                )
                outcome = conversation_turnin.settle(
                    db,
                    store,
                    current,
                    session,
                    binding,
                    definition,
                    conversation_turnin.TurnInRequirement(
                        exchange["reference"], exchange["quantity"]
                    ),
                    node_id=request["node_id"],
                    choice_id=request["choice_id"],
                    speaker_row=row,
                )
                paid_packets.extend(outcome["packets"])
                if outcome["applied"]:
                    storage.enqueue_reward(
                        db,
                        current["id"],
                        profile["quest_id"],
                        "owned-dialogue-exchange:" + profile["id"],
                        "item",
                        {
                            "aeV": 5,
                            "ckl": [
                                exchange["output_reference"],
                                exchange["output_quantity"],
                            ],
                            "reviewed_dialogue_source": profile["id"],
                        },
                    )
                    paid_packets.extend(service.drain_rewards(db, store, current))
            packet = session.choose(request["node_id"], request["choice_id"])
            packets = paid_packets + ([] if packet is None else [packet])
            story_confirmed = False
            if (
                packet is not None
                and request["node_id"]
                == row.get("binding_node_id", row["dialogue_root"])
                and request["choice_id"] == row["choice_id"]
                and profile["quest_id"] in state["running"]
            ):
                if row.get("controller_choice_reference") is not None:
                    # The guarded confirmation starts a mechanic; its native
                    # objective remains unearned until that mechanic succeeds.
                    from wakfu_server import owned_story_mechanics

                    selected, completed = owned_story_controller._scope(
                        db, store, current
                    )
                    outcome = owned_story_controller._settle(
                        db,
                        store,
                        current,
                        selected,
                        completed,
                        kind="npc_spoken",
                        reference=row["controller_choice_reference"],
                        evidence=dict(
                            actor_id=proof["actor_id"],
                            action_id=proof["action_id"],
                            node_id=request["node_id"],
                            choice_id=request["choice_id"],
                        ),
                        apply_effects=owned_story_mechanics.executor(selected),
                    )
                    packets += outcome["packets"]
                    # A newly accepted confirmation can retry the same genuine
                    # available group after a loss without repeating its step.
                    story_confirmed = True
                elif not paid:
                    packets += mission_toolkit.settle(
                        db,
                        store,
                        current,
                        f"owned-story-npc:{current['instance_id']}:{profile['id']}:{row['template_id']}:{row['choice_id']}",
                        "npc_spoken",
                        row["objective_id"],
                    )
            if packet is not None and request["choice_id"] == row.get("exit_choice_id"):
                from wakfu_server.ecology_feedback import information

                packets.append(information("You can leave through the return portal."))
            return dict(
                packets=packets,
                story_confirmed=story_confirmed,
                character=store.character(account_id, character["id"], db),
            )
    except Exception:
        (
            session.node_id,
            session.speaker_id,
            session.authorize_speaker,
            session.previous_choice_id,
        ) = previous
        raise
    finally:
        context[0] = None


def recognizes(store, opcode, body, session, character):
    if opcode == 12058:
        return session is not None and hasattr(session, "owned_story_npc")
    if opcode != 13222 or len(body) != 16:
        return False
    identity, action = npc_world.decode_interaction(body)
    if type(character.get("instance_id")) is not int or character["instance_id"] <= 0:
        return False
    # Recognition is syntactic only; the handler flushes pending movement before
    # authenticating the lease, membership, flags and current interaction range.
    return any(
        profile["map_id"] == character.get("map_id")
        and any(
            identity == actor_id(character["instance_id"], row["template_id"])
            and action in row["action_ids"]
            for row in profile["npcs"]
        )
        for profile in profiles()
    )


def argument_actor(db, store, character, reference):
    selected = [
        row for row in rows(db, store, character) if row["reference_id"] == reference
    ]
    if len(selected) != 1:
        raise ValueError("Owned story argument lacks its actual scoped NPC")
    return selected[0]["actor_id"]


def argument_target(db, store, character, target):
    selected = [
        row
        for row in rows(db, store, character)
        if row.get("controller_target_id") == target
    ]
    if len(selected) != 1:
        raise ValueError("Owned story target argument lacks its unique scoped NPC")
    return selected[0]["actor_id"]
