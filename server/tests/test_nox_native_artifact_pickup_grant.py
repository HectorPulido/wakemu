"""Declared initial Nox artifacts, actual paid12161 pickup and native649 UID."""
import json
from pathlib import Path
from random import Random
import struct
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxNativeArtifactPickupTests(PostgresCase):
    def test_initial_ebony_artifact_paid_pickup_grants_real_owned8460_and_rolls_back(
        self,
    ):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from test_ultimate_encounter_scene_recipes import (
            UltimateEncounterSceneRecipeTests,
        )
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.fight_checkpoint_store import snapshot

        scene = UltimateEncounterSceneRecipeTests().scene(5664)
        layout = resolve_supreme_scene(5664, scene)
        receipt = dict(
            scope="Initial scene and bounded paid pickup, not a complete Nox encounter",
            original_world_coordinates=False,
            direct_state_or_spell_grants=False,
        )
        output = Path(
            ".runtime/parallel-readiness-20261021/nox-native-artifact-pickup-evidence.json"
        )
        trace = []
        try:
            (
                fight,
                characters,
                monsters,
                decks,
                _,
                _,
                construction,
            ) = native_paid_party_fixture(
                self.store,
                scene,
                (native_endgame_iop_build(),),
                (layout["anchor"],),
                name_prefix="ebony-pickup",
                production_scene=True,
                encounter_layout=layout,
            )
            identity = next(iter(characters))
            self.assertEqual(fight.actors[identity].team, 1)
            self.assertEqual(fight.actors[-200].team, 0)
            self.assertEqual(monsters[-200]["team"], 1)
            self.assertNotIn(8460, granted_spells(fight, identity))
            initial = [
                dict(
                    uid=row["uid"],
                    reference=row["reference"],
                    cell=row["cell"],
                    owner_id=row["owner_id"],
                    source=row.get("native_environment_source"),
                )
                for row in fight.native_effect_areas.values()
                if 2057 <= row["reference"] <= 2067
            ]
            receipt.update(construction=construction, initial_artifacts=initial)
            self.assertEqual(
                sorted(row["reference"] for row in initial), list(range(2057, 2068))
            )
            self.assertTrue(all(row["owner_id"] is None for row in initial))
            rng = Random(7)
            common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

            def serialize(actor, current):
                if getattr(actor, "native_summon_source", None) is not None:
                    from wakfu_server.combat_summon_stats import registered_summon_stats

                    return registered_summon_stats(actor, current, scene["map_id"])
                values = dict(
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=current,
                )
                if actor.id in characters:
                    return actual_actor_stats(
                        characters[actor.id], actor, current.id, **values
                    )
                return actual_monster_actor_stats(
                    monsters[actor.id], actor, current.id, **values
                )

            runtime = RuntimeMessages(
                fight,
                stats_serializer=lambda actor: serialize(actor, fight),
                runtime_stats_serializer=serialize,
                turn_end_provider=lambda phase, **kwargs: prepare_server_turn_end(
                    characters[identity],
                    monsters,
                    phase,
                    decks[identity],
                    **common,
                    **kwargs
                ),
                turn_start_provider=lambda phase, **kwargs: prepare_server_turn_start(
                    characters[identity],
                    monsters,
                    phase,
                    decks[identity],
                    **common,
                    **kwargs
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    characters[identity],
                    monsters,
                    decks[identity],
                    action_id=action_id,
                    critical=False,
                    **common
                )[0],
            )
            boundaries = 0
            while runtime.fight.current.id != identity and boundaries < 4:
                advance_actual_turn(runtime)
                boundaries += 1
                for _ in range(32):
                    if runtime.awaiting_ack is None:
                        break
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                else:
                    self.fail("Nox opening exceeded32 genuine acknowledgments")
            self.assertEqual(runtime.fight.current.id, identity)
            self.assertIsNone(runtime.awaiting_ack)
            artifact = next(
                row
                for row in runtime.fight.native_effect_areas.values()
                if row["reference"] == 2067
            )
            path = [(-1, -8, 0), (-1, -9, 0), tuple(artifact["cell"])]
            self.assertEqual(path[-1], (-1, -10, 0))
            self.assertTrue(
                all(
                    (a, b) in runtime.fight.edges
                    for a, b in zip(
                        [runtime.fight.actors[identity].position, *path[:-1]], path
                    )
                )
            )
            before_mp = runtime.fight.actors[identity].mp
            self.assertGreaterEqual(before_mp, len(path))
            request = struct.pack(">q", identity) + b"".join(
                struct.pack(">iih", *cell) for cell in path
            )

            def area_provider(current, **kwargs):
                return prepare_area_movement(
                    characters[identity],
                    monsters,
                    current,
                    decks[identity],
                    **common,
                    **kwargs
                )

            execute = EffectDispatcher.execute

            def observe(dispatcher, invocation, **kwargs):
                result = execute(dispatcher, invocation, **kwargs)
                if invocation.reference in (401890, 401892, 401893, 402003, 401983):
                    trace.append(
                        dict(
                            reference=invocation.reference,
                            result=result,
                            caster_id=invocation.caster_id,
                            target_id=invocation.target_id,
                        )
                    )
                return result

            baseline = snapshot(runtime.fight, runtime=runtime)
            calls = 0

            def reject_after_callback(actor, current):
                nonlocal calls
                calls += 1
                if calls == 2:
                    self.assertIn(8460, granted_spells(current, identity))
                    raise RuntimeError("test-only post-pickup serializer failure")
                return serialize(actor, current)

            with patch.object(EffectDispatcher, "execute", observe):
                with self.assertRaisesRegex(
                    RuntimeError, "post-pickup serializer failure"
                ):
                    apply_client(
                        runtime,
                        characters[identity]["account_id"],
                        request,
                        lambda actor: serialize(actor, runtime.fight),
                        runtime_stats_serializer=reject_after_callback,
                        area_provider=area_provider,
                    )
                self.assertEqual(snapshot(runtime.fight, runtime=runtime), baseline)
                self.assertNotIn(8460, granted_spells(runtime.fight, identity))
                trace.clear()
                packets, event = apply_client(
                    runtime,
                    characters[identity]["account_id"],
                    request,
                    lambda actor: serialize(actor, runtime.fight),
                    runtime_stats_serializer=serialize,
                    area_provider=area_provider,
                )
            actor = runtime.fight.actors[identity]
            grant = granted_spells(runtime.fight, identity)[8460]
            self.assertEqual(grant["uid"], 8460)
            self.assertEqual(grant["reference"], 8460)
            self.assertTrue(
                any(row.reference == 9006 for row in actor.state_ledger.entries)
            )
            self.assertTrue(
                any(
                    row["reference"] == 401983 and row["result"] is True
                    for row in trace
                ),
                trace,
            )
            self.assertEqual(event["path"], path)
            self.assertEqual(actor.position, path[-1])
            # Ebano's original state also grants1MP; the movement still paid3.
            self.assertEqual(actor.mp, before_mp - len(path) + 1)
            self.assertTrue(packets)
            receipt.update(
                status="passed",
                trace=trace,
                grant=grant,
                original_mp=before_mp,
                final_mp=actor.mp,
                movement=event,
                opening_boundaries=boundaries,
                serializer_rollback=True,
            )
        except Exception as error:
            receipt.update(
                status="failed",
                error=str(error),
                error_type=type(error).__name__,
                trace=trace,
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
