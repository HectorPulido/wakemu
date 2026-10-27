"""Same-source old/current NativeOracle fork timings with full Ready correctness.

The principal pairs are uninstrumented and include memo construction. Small
copy-shape and copied-PA controls are separate declared constructor components.
No result here is a whole-World latency or RSS claim.
"""
import argparse
import ast
from contextlib import ExitStack
from copy import deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import struct
import time
from unittest.mock import patch

BEFORE_SHA = "d9f9b73611558051c52b4942846ef50a9ab3e497fd2bd838cf3f5f2f458d0e81"


def _before_fork(path, current):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != BEFORE_SHA:
        raise ValueError("Exact captured pre-memo Oracle source required")
    tree = ast.parse(raw)
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "NativeOracle"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "fork"
    )
    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
            str(path),
            "exec",
        ),
        current.__globals__,
        namespace,
    )
    return namespace["fork"]


def _shape_controls():
    from wakfu_server.combat_preview_copy import scalar_actor_memo
    from wakfu_server.combat_state import Actor, Fight

    actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
    enemy = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
    fight = Fight(
        505,
        (actor, enemy),
        {(0, 0, 0), (1, 0, 0)},
        {0: {actor.position}, 1: {enemy.position}},
    )
    shared = {1: 0, 2: 1.5, 3: True, 4: "value", 5: None}
    actor.effect_minima = actor.effect_base_minima = fight.future_pa_alias = shared
    nested = {1: {"values": [1]}}
    actor.effect_percentages = nested

    class CustomDict(dict):
        calls = 0

        def __deepcopy__(self, memo):
            type(self).calls += 1
            result = type(self)()
            memo[id(self)] = result
            result.update(deepcopy(dict(self), memo))
            return result

    actor.effect_maxima = CustomDict({1: 60})
    memo = scalar_actor_memo(fight)
    assert id(shared) in memo and memo[id(shared)] is not shared
    assert id(nested) not in memo and id(actor.effect_maxima) not in memo
    assert any(value is shared for value in memo[id(memo)])
    clone = deepcopy(fight, memo)
    assert (
        clone.actors[7].effect_minima
        is clone.actors[7].effect_base_minima
        is clone.future_pa_alias
    )
    clone.future_pa_alias[1] = 77
    clone.actors[7].effect_percentages[1]["values"].append(2)
    assert shared[1] == 0 and nested[1]["values"] == [1]
    assert type(clone.actors[7].effect_maxima) is CustomDict and CustomDict.calls == 1
    from types import SimpleNamespace

    assert scalar_actor_memo(SimpleNamespace(actors=fight.actors)) == {}
    return True


def _copied_pa_control():
    from test_combat_copied_pa import CopiedPATests
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_copied_pa import (
        install_copied_pa_pool,
        copied_raw_current,
        shift_copied_current,
        set_copied_maximum,
    )
    from wakfu_server.combat_character_copy_metadata import native_copy_characteristics
    from wakfu_server.combat_preview_copy import scalar_actor_memo

    _, source_actor, rows, source = CopiedPATests().fixture()
    actor = Actor(7, 0, (0, 0, 0), 82, 6, 3, 10, 1, 3, True)
    actor.effect_frozen = source_actor.effect_frozen
    install_copied_pa_pool(
        actor, rows, metadata=native_copy_characteristics(), source_record=source
    )
    enemy = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
    fight = Fight(
        506,
        (actor, enemy),
        {(0, 0, 0), (1, 0, 0)},
        {0: {actor.position}, 1: {enemy.position}},
    )
    private = deepcopy(fight, scalar_actor_memo(fight))
    copied = private.actors[7]
    assert copied_raw_current(copied, 1) == copied_raw_current(actor, 1) == 125
    shift_copied_current(private, copied, 1, 10, subtract=True)
    set_copied_maximum(private, copied, 1, 90)
    assert copied_raw_current(actor, 1) == 125 and actor.hp == actor.max_hp == 82
    assert copied_raw_current(copied, 1) == 115 and copied.max_hp == 90
    assert (
        copied.effect_characteristic_raw_currents
        is not actor.effect_characteristic_raw_currents
    )
    return True


def run(manifest, before_path, *, repeats=7):
    from tools.sublimation_bounded_census import BoundedDataset

    dataset = BoundedDataset(manifest)
    dataset.install_catalog_backend()
    from wakfu_server import (
        combat_server_spell,
        combat_npc_attack,
        spell_audit,
        combat_casting_context,
    )
    from wakfu_server.combat_static_catalogs import CompiledEffects
    from wakfu_server.combat_effect_runtime import _merge_effects
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health import maximum
    from wakfu_server.spells import default_deck, validate_deck
    from wakfu_server.wire import proto_field
    from wakfu_server.combat_characteristic_link import bind_characteristic_stats
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_ai.native.native_oracle import NativeOracle
    from rift_native_flow_fixture import build_flow_fixture
    from test_rift_native_carrier_component import NativeRiftCarrierComponentTests

    effects = _merge_effects(
        dataset.closure["effects"],
        dataset.read(dataset.manifest["semantic"]["extra_effects"]),
    )
    states = {
        **dataset.states["states"],
        **dataset.read(dataset.manifest["semantic"]["extra_states"])["states"],
    }
    compiled = CompiledEffects(effects, dict(states=states, effects=effects))
    registry = {"effects": dataset.closure["registry"]}
    class_catalog = dataset.read(dataset.manifest["rift_player_class_catalog"])
    roots = dataset.read(dataset.manifest["rift_casting_root_catalog"])
    with ExitStack() as readers:
        for module, name, value in (
            (spell_audit, "states_catalog", compiled.source_states),
            (spell_audit, "catalog", class_catalog),
            (combat_server_spell, "catalog", class_catalog),
            (combat_server_spell, "states_catalog", compiled.source_states),
            (combat_server_spell, "compiled_runtime_catalog", compiled),
            (combat_npc_attack, "npc_runtime_catalog", compiled),
            (combat_casting_context, "casting_root_catalog", roots),
        ):
            readers.enter_context(patch.object(module, name, return_value=value))
        migration = next(
            (Path(__file__).resolve().parents[1] / "migrations").glob("090_*.sql")
        )
        catalogs = next(
            value
            for text in re.findall(r"'({.*})'::jsonb", migration.read_text())
            for value in [json.loads(text)]
            if "37" in value
        )
        catalog = deepcopy(catalogs["37"])
        catalog["species_refs"] = [
            5295
        ]  # Declared component pool, not full composition.
        run = dict(
            catalog=catalog,
            policy=NativeRiftCarrierComponentTests.policy(),
            seed="fork-full-ready",
            instance_id=37,
            wave=1,
        )
        aptitude = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, 20) + proto_field(16, 2)
        )
        character = effective_character(
            dict(
                id=7,
                account_id=3,
                breed=1,
                sex=False,
                level=100,
                real_level=100,
                map_id=catalog["map_id"],
                instance_id=37,
                x=0,
                y=0,
                z=0,
                hp=maximum(1, 100),
                inventory_items=[],
                active_build_index=0,
                builds={
                    0: dict(
                        equipment="",
                        sheet=proto_field(24, 0xFFFFFFFF).hex(),
                        aptitudes=aptitude.hex(),
                    )
                },
            )
        )
        character["hp"] = character["max_hp"]
        character["builds"][0]["deck"] = default_deck(character).hex()
        component = build_flow_fixture(
            character,
            run,
            5005,
            (-200, -201),
            (5295, 5295),
            compiled=compiled,
            registry=registry,
        )
        fight, _ = combat_server_spell.prepare_server_initialization(
            component.character,
            component.fight.rift_monsters,
            component.fight,
            3,
            component.decks[7],
            action_id=1,
            rng=component.rng,
            fight_start=True,
            player_characters=component.characters,
            deck_blobs=component.decks,
        )
        assert (
            fight.native_start_event_delivered
            and 7 in fight.native_class_initializations
        )
        bind_characteristic_stats(fight)
        runtime = RuntimeMessages(fight)
        active = validate_deck(
            component.decks[7],
            character["breed"],
            character["level"],
            character=component.character,
        )["active"]
        oracle = NativeOracle(
            runtime,
            characters=component.characters,
            monsters=fight.rift_monsters,
            decks={7: frozenset(active)},
            excluded_decks={7: frozenset()},
            viewer_id=7,
            flags={"native_start_events": True, "native_area_callbacks": True},
        )
        runtime.turn_start_provider, runtime.turn_end_provider = (
            oracle.start_boundary,
            oracle.end_boundary,
        )
        runtime.awaiting_ack = fight.turn_id
        runtime.pending = [(13078, struct.pack(">qI", 7, 0))]
        shared = fight.actors[7].effect_base_maxima
        runtime.future_pa_alias = fight.future_pa_alias = fight.actors[
            7
        ].future_pa_alias = shared
        source_before, rng_before = (
            snapshot(fight, runtime=runtime),
            component.rng.getstate(),
        )
        legacy = _before_fork(before_path, NativeOracle.fork)
        samples = {"before": [], "after": []}
        for index in range(repeats):
            variants = ("before", "after") if index % 2 == 0 else ("after", "before")
            for variant in variants:
                gc.collect()
                started, cpu_started = time.perf_counter_ns(), time.thread_time_ns()
                private = (
                    legacy(oracle, runtime=runtime)
                    if variant == "before"
                    else oracle.fork(runtime=runtime)
                )
                wall, cpu = (
                    time.perf_counter_ns() - started,
                    time.thread_time_ns() - cpu_started,
                )
                samples[variant].append(dict(wall_ns=wall, cpu_ns=cpu))
                assert private is not runtime and private.fight is not fight
                assert (
                    private.future_pa_alias
                    is private.fight.future_pa_alias
                    is private.fight.actors[7].effect_base_maxima
                )
                assert private.future_pa_alias is not shared
                assert (
                    private.pending == runtime.pending
                    and private.pending is not runtime.pending
                )
                assert (
                    private.turn_start_provider.__self__ is oracle
                    and private.turn_end_provider.__self__ is oracle
                )
                for identity, actor in private.fight.actors.items():
                    assert (
                        actor is not fight.actors[identity]
                        and actor.effect_stats._fight is private.fight
                    )
                    for field in (
                        "effect_stats",
                        "effect_minima",
                        "effect_maxima",
                        "effect_percentages",
                        "effect_base_minima",
                        "effect_base_maxima",
                    ):
                        assert getattr(actor, field) is not getattr(
                            fight.actors[identity], field
                        )
                if variant == "after" and index == repeats - 1:
                    actor = private.fight.actors[7]
                    from wakfu_server.combat_hp_raw import (
                        set_hp_raw_maximum,
                        set_hp_raw_minimum,
                    )
                    from wakfu_server.combat_maximum_resource import _write
                    from wakfu_server.combat_hupper_resource_binding import set_current

                    old_max, old_min = (
                        actor.effect_base_maxima[1],
                        actor.effect_base_minima[1],
                    )
                    set_hp_raw_maximum(actor, old_max + 5)
                    set_hp_raw_minimum(actor, old_min + 1)
                    before_breeze = actor.effect_base_maxima[111]
                    _write(
                        actor,
                        4,
                        actor.effect_stats[4],
                        actor.effect_base_maxima[4] + 1,
                        actor.effect_maxima[4] + 1,
                    )
                    assert actor.effect_base_maxima[111] == before_breeze + 75
                    set_current(actor, 100)
                    actor.effect_stats[48] += 1
                    private.pending.clear()
                    private.awaiting_ack = None
                    private.future_pa_alias[99999] = 17
                assert (
                    snapshot(fight, runtime=runtime) == source_before
                    and component.rng.getstate() == rng_before
                )
                del private
        partial = os.environ.get("WAKFU_FORK_PERFORMANCE_RECEIPT")
        if partial:
            path = Path(partial).with_suffix(".partial.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    dict(
                        status="PRINCIPAL_PAIRS_COMPLETE_CONTROLS_PENDING",
                        samples=samples,
                        source_before_sha256=BEFORE_SHA,
                        manifest_sha256=hashlib.sha256(
                            Path(manifest).read_bytes()
                        ).hexdigest(),
                    ),
                    indent=2,
                )
                + "\n"
            )
        shape = _shape_controls()
        copied_pa = _copied_pa_control()
        assert (
            snapshot(fight, runtime=runtime) == source_before
            and component.rng.getstate() == rng_before
        )
    summary = {
        name: dict(
            samples=rows,
            median_wall_ns=statistics.median(r["wall_ns"] for r in rows),
            min_wall_ns=min(r["wall_ns"] for r in rows),
            max_wall_ns=max(r["wall_ns"] for r in rows),
            median_cpu_ns=statistics.median(r["cpu_ns"] for r in rows),
        )
        for name, rows in samples.items()
    }
    return dict(
        schema="wakemu-native-oracle-pa-memo-paired-v1",
        status="PASS",
        full_class_ready_qualified=True,
        ready_players=1,
        actual_npcs=2,
        samples_per_variant=repeats,
        source_before_sha256=BEFORE_SHA,
        manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        measurements=summary,
        correctness=dict(
            source_snapshot_rng_unchanged=True,
            private_all_pa_maps=True,
            aliases_preserved=True,
            observable_callback_fight_rebound=True,
            hp_raw_and_hupper_private_writes=True,
            nested_subclass_fallback=shape,
            copied_pa_actual_constructor=copied_pa,
            transport_pending_ack_isolation=True,
        ),
        source_pins={
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__).resolve(),
                Path(__file__).resolve().parents[1]
                / "wakfu_server/combat/combat_preview_copy.py",
                Path(__file__).resolve().parents[1]
                / "ai-service/wakfu_ai/native/native_oracle.py",
            )
        },
        limits=[
            "Paired same-source14uninstrumentedforks including memo preseed cost; not World/actionthroughput",
            "CopiedPA/nestedshapecontrols are declared constructor/copy components, not additional classReady or paidcopyspell claims",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--before-source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.before_source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
