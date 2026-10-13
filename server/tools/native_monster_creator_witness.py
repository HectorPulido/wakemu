"""Source-bound NPC creators and genuine registered summon witnesses.

This tooling never grants resources or changes a summon descriptor level.
Class-only production is deliberately separate from NPC-owned production.
"""
from copy import deepcopy
from random import Random


def npc_creator_plans(index, native, reference, *, limit=4):
    if type(reference) is not int or type(limit) is not int or not 1 <= limit <= 8:
        raise ValueError("Invalid bounded native creator query")
    rows = [row for row in index["rows"] if row["ref"] == reference]
    if len(rows) != 1:
        raise ValueError("Missing unique native producer inventory target")
    plans = []
    seen = set()
    for edge in rows[0]["producers"]:
        if edge.get("source_kind") != "npc":
            continue
        source = native.get(edge.get("creator_ref"))
        if source is None:
            raise ValueError("Missing actual native NPC creator descriptor")
        owned = [
            a
            for a in source["native_abilities"]
            if a["spell_id"] == edge["creator_spell"]
        ]
        if len(owned) != 1:
            raise ValueError("Creator spell is absent from its actual native book")
        key = (source["ref"], edge["creator_spell"], edge["family307_effect"])
        if key in seen:
            continue
        seen.add(key)
        plans.append(
            dict(
                target_ref=reference,
                creator_ref=source["ref"],
                creator_level=source["min_level"],
                creator_native_levels=[source["min_level"], source["max_level"]],
                creator_spell=edge["creator_spell"],
                spell_level_parameter=owned[0]["level_parameter"],
                family307_effect=edge["family307_effect"],
                source_path=deepcopy(edge["source_path"]),
                source_kind="npc",
                summon_level_override=None,
            )
        )
        if len(plans) == limit:
            break
    return plans


def _construct_native_summon_scene(validator, plan, *, attempt_cap=6, scenario=None):
    """Call the original NPC transaction; retain the registered actor it creates."""
    from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
    from wakfu_server.combat_native_spell_casting import native_casting_table
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.combat_geometry_snapshot import source_snapshot
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.combat_summon_stats import registered_summon_stats

    if type(attempt_cap) is not int or not 1 <= attempt_cap <= 6:
        raise ValueError("Invalid bounded native creator attempt cap")
    fight, character, monsters, deck = validator.fixture(
        plan["creator_ref"],
        plan["creator_level"],
        (-10, -7, -1),
        scenario=scenario,
        native_lifecycle=True,
    )
    creator = fight.current
    if creator.id not in monsters or monsters[creator.id]["ref"] != plan["creator_ref"]:
        raise ValueError("Actual current actor is not the native NPC creator")
    spells = owned_spells(fight, monsters)
    if plan["creator_spell"] not in spells:
        raise ValueError("Actual creator no longer owns its source spell")
    spell_level = spells[plan["creator_spell"]]
    casting, index = native_casting_table(plan["creator_spell"], spell_level)
    minimum, maximum, _ = casting["levels"][index]
    occupied = {actor.position for actor in fight.actors.values() if actor.hp > 0}
    cells = sorted(
        published_geometry(character["map_id"]).cells,
        key=lambda cell: (
            abs(cell[0] - creator.position[0]) + abs(cell[1] - creator.position[1]),
            cell,
        ),
    )
    candidates = [
        cell
        for cell in cells
        if minimum
        <= abs(cell[0] - creator.position[0]) + abs(cell[1] - creator.position[1])
        <= maximum
    ]
    candidates.sort(
        key=lambda cell: (
            cell not in occupied,
            abs(cell[0] - creator.position[0]) + abs(cell[1] - creator.position[1]),
            cell,
        )
    )
    before = snapshot(fight)
    geometry = source_snapshot(fight)
    errors = []
    for cell in candidates[:attempt_cap]:
        action = dict(
            type="cast",
            spellId=plan["creator_spell"],
            level=spell_level,
            target=list(cell),
            targetId=next(
                (
                    a.id
                    for a in fight.actors.values()
                    if a.hp > 0 and a.position == cell
                ),
                None,
            ),
        )
        try:
            transaction = prepare_npc_spell(
                fight, action, character, monsters, deck, action_id=1, rng=Random(0)
            )
            if snapshot(fight) != before or source_snapshot(fight) != geometry:
                raise RuntimeError("Actual creator preview mutated its source")
            created = [
                actor
                for identity, actor in transaction.fight.actors.items()
                if identity not in fight.actors
                and getattr(actor, "native_summon_source", {}).get("ref")
                == plan["target_ref"]
            ]
            if len(created) != 1:
                raise ValueError(
                    "Creator cast did not produce one requested native actor"
                )
            actor = created[0]
            living_positions = {}
            for member in transaction.fight.actors.values():
                if member.hp > 0:
                    living_positions.setdefault(member.position, []).append(member.id)
            if any(len(identities) > 1 for identities in living_positions.values()):
                raise ValueError(
                    "Native creator anchor leaves overlapping living actors"
                )
            registered_summon_stats(actor, transaction.fight, character["map_id"])
            if actor.native_summon_source["caster_id"] != creator.id:
                raise ValueError("Registered summon has another actual caster")
            receipt = dict(
                status="actual_native_creator_constructed",
                creator_ref=plan["creator_ref"],
                creator_level=creator.effective_level,
                creator_spell=plan["creator_spell"],
                creator_spell_level=spell_level,
                action=action,
                actor_id=actor.id,
                native_created_source=deepcopy(actor.native_summon_source),
                native_action_book=deepcopy(actor.native_summon_action_book),
                resources={
                    str(stat): dict(
                        current=actor.effect_stats[stat],
                        maximum=actor.effect_maxima[stat],
                    )
                    for stat in (2, 3, 4)
                },
                native_controlled_by_ai=actor.native_controlled_by_ai,
                constructor_packets=len(transaction.packets),
                source_unchanged=True,
                prior_attempt_errors=errors,
                native_scene=deepcopy(scenario),
                resources_injected=False,
                wild_activation_supported=False,
            )
            return fight, transaction, character, monsters, deck, receipt
        except ValueError as error:
            if snapshot(fight) != before or source_snapshot(fight) != geometry:
                raise RuntimeError(
                    "Rejected native creator cast mutated source"
                ) from error
            errors.append(
                dict(action=action, error=type(error).__name__ + ": " + str(error))
            )
    raise ValueError("Bounded actual NPC creator failed: " + repr(errors))


def construct_native_summon(validator, plan, *, attempt_cap=6):
    """Use existing source-derived ally recipes within six total cast attempts."""
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_ai_capabilities import describe_spell
    from wakfu_server.combat_native_spell_casting import native_casting_table
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from monster_pending_scenarios import native_ally_recipe

    owned = next(
        a
        for a in native_abilities(plan["creator_ref"], plan["creator_level"])
        if a["spell_id"] == plan["creator_spell"]
    )
    casting, index = native_casting_table(plan["creator_spell"], owned["spell_level"])
    compiled = npc_runtime_catalog()
    roots = [compiled.effects[str(root)] for root in casting["levels"][index][2]]
    ally = native_ally_recipe(
        plan["creator_ref"],
        plan["creator_level"],
        describe_spell(plan["creator_spell"], owned["spell_level"]),
        criterion=casting.get("cast_criterion_raw"),
        root_effects=roots,
    )
    scenes = [None] + ([ally] if ally is not None else [])
    errors = []
    for scenario in scenes:
        try:
            return _construct_native_summon_scene(
                validator,
                plan,
                attempt_cap=attempt_cap // len(scenes),
                scenario=scenario,
            )
        except ValueError as error:
            errors.append(dict(scenario=scenario, error=str(error)))
    raise ValueError("Native creator bounded scene failures: " + repr(errors))


def witness_owned_actions(validator, plan, *, progress=None):
    """Commit the creator, reach its real child's turn and use actual AI actions."""
    from wakfu_server.combat_tactical_ai import NativeProvider, build_request
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.combat_summon_stats import registered_summon_stats
    from wakfu_server.combat_server_spell import prepare_server_turn_end
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.combat_summon_spellbook import actor_action_book
    import planner

    fight, transaction, character, monsters, deck, receipt = construct_native_summon(
        validator, plan
    )

    def serialize(actor, state):
        if getattr(actor, "native_summon_source", None) is not None:
            return registered_summon_stats(actor, state, character["map_id"])
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **values)
        return actual_monster_actor_stats(monsters[actor.id], actor, state.id, **values)

    runtime = RuntimeMessages(fight)
    provider = NativeProvider(character, monsters, deck)
    before = snapshot(fight, runtime=runtime)

    def broken(actor, state):
        raise ValueError("native creator witness serializer failure")

    try:
        provider.commit(runtime, receipt["action"], broken)
    except ValueError as error:
        if str(error) != "native creator witness serializer failure":
            raise
    else:
        raise ValueError("Creator serializer failure did not reject commit")
    if snapshot(fight, runtime=runtime) != before:
        raise ValueError("Creator serializer failure changed actual source")
    constructor_packets = provider.commit(runtime, receipt["action"], serialize)
    actor_id = receipt["actor_id"]
    fight = runtime.fight
    receipt.update(
        actual_constructor_commit_packets=len(constructor_packets),
        creator_serializer_failure_rolled_back=True,
        native_created_level=fight.actors[actor_id].effective_level,
    )
    if progress is not None:
        progress(deepcopy(receipt))
    if actor_id not in fight.actors:
        raise ValueError("Actual constructor commit omitted its registered child")
    turn_packets = 0
    for step in range(len(fight.actors) * 2 + 1):
        if fight.current is not None and fight.current.id == actor_id:
            break
        if fight.current is None:
            raise ValueError("Creator encounter ended before child turn")
        current = fight.current
        preview, packets = prepare_server_turn_end(
            character,
            monsters,
            fight,
            deck,
            actor_id=current.id,
            action_id=10 + step,
            rng=Random(0),
        )
        current = preview.actors[current.id]
        from wakfu_server.combat_effective_control import effective_server_controlled

        if effective_server_controlled(preview, current):
            preview.end_server_turn(current.id, preview.turn_id)
        else:
            preview.end_turn(current.owner_id, current.id, current.turn_count)
        RuntimeMessages(preview).turn_started()
        fight = preview
        turn_packets += len(packets)
    else:
        raise ValueError("Native child turn was not reached in bounded lifecycle")
    actor = fight.current
    book = actor_action_book(actor)
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_controller_registry import current_native_controller

    receipt["actual_current_controller_id"] = current_native_controller(fight, actor.id)
    receipt["raw_native_ai_flag_at_child_turn"] = actor.native_controlled_by_ai
    receipt["effective_server_actions"] = effective_server_controlled(fight, actor)
    receipt["ai_routing_policy"] = (
        "native.eGj.fqL"
        if actor.native_controlled_by_ai
        else "wakemu.registered-npc-controller-actions-v1"
    )
    receipt.update(
        creator_serializer_failure_rolled_back=True,
        actual_constructor_commit_packets=len(constructor_packets),
        native_created_level=actor.effective_level,
        actual_child_turn_reached=True,
        turn_boundary_packets=turn_packets,
    )
    if progress is not None:
        progress(deepcopy(receipt))
    provider = NativeProvider(character, monsters, deck)
    provider.capabilities(fight)  # Warm metadata before the unchanged search deadline.
    runtime = RuntimeMessages(fight)
    actions = []
    for step in range(3):
        before = snapshot(fight, runtime=runtime)
        request = build_request(
            runtime, provider, max_previews=48, budget_ms=5000, depth=2
        )
        if snapshot(fight, runtime=runtime) != before:
            raise ValueError("Actual child forecast mutated source")
        decision = planner.decide(request)
        action = decision["decision"]["actions"][0]
        receipt.setdefault("actual_child_ai_diagnostics", []).append(
            dict(
                decision=decision,
                producer_trace=request.get("producerTrace"),
                forecast_states=deepcopy(request.get("states", [])),
                forecast_root=request.get("rootState"),
                capabilities=provider.capabilities(fight),
                actor_position=list(fight.current.position),
                roster=provider.roster(fight),
            )
        )
        if progress is not None:
            progress(deepcopy(receipt))
        if action["type"] == "end_turn":
            raise ValueError("Actual child AI selected end turn before an owned cast")
        if action["type"] == "cast" and action["spellId"] not in {
            entry["reference"] for entry in book["actions"]
        }:
            raise ValueError("Actual child AI selected a foreign action")
        try:
            provider.commit(runtime, action, broken)
        except ValueError as error:
            if str(error) != "native creator witness serializer failure":
                raise
        else:
            raise ValueError("Child serializer failure did not reject commit")
        if snapshot(fight, runtime=runtime) != before:
            raise ValueError("Child serializer failure did not roll back")
        packets = provider.commit(runtime, action, serialize)
        if not packets or snapshot(fight, runtime=runtime) == before:
            raise ValueError("Actual child AI action had no committed state change")
        actions.append(
            dict(
                action=action,
                decision=decision,
                packets=len(packets),
                forecast_source_unchanged=True,
                serializer_failure_rolled_back=True,
                committed_state_changed=True,
            )
        )
        fight = runtime.fight
        if action["type"] == "cast":
            receipt.update(
                status="functional_owned_summon_at_native_levels",
                actual_child_ai_actions=actions,
                actual_owned_book=book,
                no_independent_wild_descriptor=True,
            )
            return receipt
    raise ValueError("No owned child cast within three actual AI decisions")


def initialize_native_creator_lifecycle(fight, character, monsters, deck):
    """Initialize the real player opponent and native start before any turns."""
    from wakfu_server.combat_server_spell import (
        prepare_server_initialization,
        prepare_server_turn_end,
    )
    from wakfu_server.combat_effective_control import effective_server_controlled
    from wakfu_server.combat_runtime_messages import RuntimeMessages

    fight, packets = prepare_server_initialization(
        character,
        monsters,
        fight,
        character["account_id"],
        deck,
        action_id=1,
        rng=Random(0),
        fight_start=True,
        player_characters={character["id"]: character},
        deck_blobs={character["id"]: deck},
    )
    count = len(packets)
    for step in range(len(fight.actors) * 2 + 1):
        if fight.current is not None and fight.current.id == -200:
            fight.validation_creator_lifecycle_start = dict(
                native_start_delivered=fight.native_start_event_delivered, packets=count
            )
            return fight
        if fight.current is None:
            break
        identity = fight.current.id
        preview, packets = prepare_server_turn_end(
            character,
            monsters,
            fight,
            deck,
            actor_id=identity,
            action_id=2 + step,
            rng=Random(0),
        )
        actor = preview.actors[identity]
        if effective_server_controlled(preview, actor):
            preview.end_server_turn(identity, preview.turn_id)
        else:
            preview.end_turn(actor.owner_id, identity, actor.turn_count)
        RuntimeMessages(preview).turn_started()
        fight = preview
        count += len(packets)
    raise ValueError(
        "Actual initialized encounter did not reach its native creator turn"
    )


def main():
    import argparse, gzip, hashlib, json, os, sys, traceback
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument(
        "--catalog-fallback-root", type=Path, action="append", default=[]
    )
    parser.add_argument("--only-ref", type=int, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.output.exists():
        raise ValueError("Use a fresh output; preserve historical actual witnesses")
    sys.path[:0] = [
        str(root / folder)
        for folder in ("server", "server/tools", "server/tests", "server/ai-service")
    ]
    os.environ["WAKFU_NATIVE_GRANTED_CAST"] = "1"
    os.environ["WAKFU_NATIVE_AREA_CALLBACKS"] = "1"
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    seals = lambda: {
        str(p.relative_to(root)): sha(p) for p in (root / "server").rglob("*.py")
    }
    before = seals()
    index = json.loads(args.index.read_text())
    with gzip.open(args.native_monsters, "rt") as stream:
        native = {row["ref"]: row for row in json.load(stream)["monsters"]}
    references = args.only_ref or [
        row["ref"]
        for row in index["rows"]
        if row.get("remaining87")
        and any(edge.get("source_kind") == "npc" for edge in row["producers"])
    ]
    if len(set(references)) != len(references):
        raise ValueError("Duplicate native producer target scope")
    result = dict(
        schema="actual-monster-created-summon-batch-v1",
        selected_references=references,
        status="running",
        source_before=before,
        rows=[],
        admission=False,
        wild_activation_supported=False,
        resources_injected=False,
        input_sha256={
            str(p.resolve()): sha(p)
            for p in [
                args.index,
                args.native_monsters,
                args.candidate / "manifest.json",
            ]
        },
    )
    from offline_monster_catalog import OfflineMonsterCatalog

    catalog = OfflineMonsterCatalog(args.candidate, args.catalog_fallback_root)
    with catalog.install():
        import validate_monster_spell_activation as validator

        validator.NATIVE_SOURCE_MONSTERS = native
        validator.install_overlay(args.candidate)
        # Warm and freeze static catalogs before creating any mutable encounter.
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_summon_spellbook import profile_abilities
        from wakfu_server.combat_summon_initial_states import native_initial_states
        from wakfu_server.combat_geometry import published_geometry

        npc_runtime_catalog()
        native_actor_catalog()
        profile_abilities()
        native_initial_states()
        published_geometry(1134)
        import gc

        gc.collect()
        gc.freeze()
        for reference in references:
            row = dict(ref=reference, status="pending", attempts=[])
            result["rows"].append(row)
            try:
                plans = npc_creator_plans(index, native, reference)
                if not plans:
                    raise ValueError("No genuine monster-owned creator route")
                for plan in plans:
                    try:

                        def progress(receipt):
                            row["witness_progress"] = receipt
                            args.output.parent.mkdir(parents=True, exist_ok=True)
                            args.output.write_text(json.dumps(result, indent=2) + "\n")

                        receipt = witness_owned_actions(
                            validator, plan, progress=progress
                        )
                        row.update(
                            status="functional_owned_summon_at_native_levels",
                            witness=receipt,
                        )
                        break
                    except Exception as error:
                        row["attempts"].append(
                            dict(
                                plan=plan,
                                error=type(error).__name__ + ": " + str(error),
                            )
                        )
                        traceback.print_exc()
            except Exception as error:
                row["error"] = type(error).__name__ + ": " + str(error)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
    result.update(status="completed", catalog=catalog.receipt(), source_after=seals())
    result["global_all_python_sources_stable"] = (
        result["source_before"] == result["source_after"]
    )
    actual_files = set()
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not isinstance(name, str):
            continue
        path = Path(name).resolve()
        try:
            key = str(path.relative_to(root))
        except ValueError:
            continue
        if key.startswith("server/") and path.suffix == ".py":
            actual_files.add(key)
    actual_files.add(str(Path(__file__).resolve().relative_to(root)))
    result["executed_source_before"] = {
        key: result["source_before"].get(key) for key in sorted(actual_files)
    }
    result["executed_source_after"] = {
        key: result["source_after"].get(key) for key in sorted(actual_files)
    }
    result["sources_stable"] = (
        all(value is not None for value in result["executed_source_before"].values())
        and result["executed_source_before"] == result["executed_source_after"]
    )
    result["inputs_stable"] = all(
        sha(Path(path)) == checksum for path, checksum in result["input_sha256"].items()
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                output=str(args.output),
                statuses=[(r["ref"], r["status"]) for r in result["rows"]],
                sources_stable=result["sources_stable"],
            )
        )
    )
    return (
        0
        if result["sources_stable"]
        and result["inputs_stable"]
        and all(
            r["status"] == "functional_owned_summon_at_native_levels"
            for r in result["rows"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
