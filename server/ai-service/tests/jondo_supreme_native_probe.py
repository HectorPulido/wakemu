"""Opt-in native scene qualification through the real separate Jondo TCP service.

Configured scene coordinates are reconstructed server policy. These bounded
turns do not establish an encounter victory or an earned later phase.
"""
from pathlib import Path
import json
from random import Random
from types import SimpleNamespace
from unittest.mock import patch

SCENES = {
    1988: (110, 363),
    3582: (170, 959),
    2430: (125, 545),
    3433: (200, 1092),
    4770: (200, 1229),
}


def actor_facts(fight):
    return {
        str(identity): dict(
            hp=actor.hp,
            maxHp=actor.max_hp,
            ap=actor.ap,
            mp=actor.mp,
            position=list(actor.position),
            states=[
                dict(reference=e.reference, level=e.level)
                for e in actor.state_ledger.entries
            ],
            properties=dict(getattr(actor, "native_fight_property_counts", {})),
        )
        for identity, actor in fight.actors.items()
    }


def run_scene(*, reference, endpoint="tcp://ai-jondo:8091", max_actions=8):
    """Use native bootstrap, native callbacks, actual TCP choices and native ACK."""
    import validate_monster_spell_activation as validator
    import jondo_native_turn_probe
    from native_recorded_instance_fixture import original_bootstrap_publication
    from native_tank_witness_fixture import native_tank_fixture
    from ultimate_encounter_scene_recipes import encounter_fixture_factory
    from native_supreme_scene_turn_runtime import native_scene_turn_runtime
    from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_ai.native.native_oracle import NativeOracle
    from tools.combat_audit_turns import advance_actual_turn

    level, map_id = SCENES[reference]
    root = Path(__file__).resolve().parents[3]
    geometry = json.loads(
        (root / f".runtime/ultimate-scenes-20261021/map-{map_id}.json").read_bytes()
    )
    scene = resolve_supreme_scene(reference, geometry)
    context = {}

    def factory(**unused):
        tank, owner_facts = native_tank_fixture(validator, feca=True)
        construct, preparation = encounter_fixture_factory(
            validator,
            scene,
            caster_cell=scene["source"],
            player_level=200,
            player_breed=1,
            player_deck=[6972],
            character_constructor=tank.__globals__["_healthy_owned_character"],
            production_bootstrap=True,
        )
        with original_bootstrap_publication():
            fight, character, monsters, deck = construct(
                reference, level, scene["anchor"], native_lifecycle=False
            )
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=2,
            fight_start=True,
            rng=Random(0),
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        runtime, _ = native_scene_turn_runtime(
            fight, character, monsters, deck, map_id=map_id, rng=Random(0)
        )
        runtime.turn_started()
        for _ in range(16):
            if runtime.awaiting_ack is not None:
                import struct

                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                continue
            if runtime.fight.current is not None and runtime.fight.current.id == -200:
                break
            advance_actual_turn(runtime)
        else:
            raise AssertionError(
                "Native scene did not reach its boss within16 boundaries"
            )
        context.update(
            runtime=runtime,
            before=actor_facts(runtime.fight),
            setup=dict(
                mapId=map_id,
                scenePolicy=scene.get("policy"),
                preparation=dict(
                    source=list(scene["source"]),
                    anchor=list(scene["anchor"]),
                    cells=len(scene["cells"]),
                    edges=len(scene["edges"]),
                ),
                healthyOwner=owner_facts,
                areasBefore=list(runtime.fight.native_effect_areas.values()),
            ),
        )
        return (
            runtime,
            {7: character},
            monsters,
            {7: deck},
            {7: frozenset()},
            SimpleNamespace(pc=runtime.fight.actors[7], character=character),
        )

    original = NativeOracle.commit
    commits = []

    def commit(oracle, action, *args, **kwargs):
        before = actor_facts(oracle.runtime.fight)
        result = original(oracle, action, *args, **kwargs)
        commits.append(
            dict(action=action, before=before, after=actor_facts(oracle.runtime.fight))
        )
        return result

    with patch.object(NativeOracle, "commit", commit):
        result = jondo_native_turn_probe.run(
            endpoint,
            reference=reference,
            level=level,
            max_actions=max_actions,
            fixture_factory=factory,
        )
    runtime = context["runtime"]
    result.update(
        sceneQualification="Bounded actual configured scene opening; no victory or earned later phase claim",
        nativeSetup=context["setup"],
        beforeActors=context["before"],
        afterActors=actor_facts(runtime.fight),
        nativeCommits=commits,
        areasAfter=list(runtime.fight.native_effect_areas.values()),
        mechanismChecks=dict(
            actualConfiguredMap=context["setup"]["mapId"] == map_id,
            nativeSceneLayoutPresent=bool(
                getattr(runtime.fight, "native_encounter_scene_layout", None)
            ),
            phaseEarned=False,
            completeEncounterQualified=False,
        ),
    )
    return result
