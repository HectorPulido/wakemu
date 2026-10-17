"""Actual paid equipment lifecycle probes over the private v1 fixture.

Typed recovery is an offline engine reconstruction, not live socket takeover.
The inherited v1 positive remains separately selected by its canonical ID.
"""
import struct

from test_equipment_reactive_damage_pipeline import ReactiveEquipmentDamagePipelineTests
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from combat_audit_turns import advance_actual_turn


class ReactiveEquipmentDamageLifecycleTests(ReactiveEquipmentDamagePipelineTests):
    def _complete(self, values):
        self._cast(values)
        self._move(values, (-7, -7, -1))
        self._cast(values)
        owner, runtime = values[0]["id"], values[4]
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8788)), 1)
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8787)), 1)

    def test_repeated_paid_hit_cooldown_and_real_turn_expiration(self):
        values = self._fixture("distance-first")
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        self._complete(values)
        buff = self._states(runtime.fight.actors[owner], 8787)[0]
        cooldown = self._states(runtime.fight.actors[owner], 8788)[0]
        # A third real paid hit must keep the existing buff/cooldown identities.
        self._cast(values)
        self.assertEqual(self._states(runtime.fight.actors[owner], 8787), [buff])
        self.assertEqual(self._states(runtime.fight.actors[owner], 8788), [cooldown])
        self.assertFalse(self._states(runtime.fight.actors[-200], 8785))
        self.assertFalse(self._states(runtime.fight.actors[-200], 8786))
        for _ in range(2 * len(runtime.fight.actors)):
            advance_actual_turn(runtime)
            if runtime.fight.current.id == owner:
                break
        self.assertEqual(runtime.fight.current.id, owner)
        self.assertFalse(self._states(runtime.fight.actors[owner], 8787))
        self.assertFalse(self._states(runtime.fight.actors[owner], 8788))
        # Earn another complete cycle after production clocks released the first.
        self._cast(values)
        self._move(values, (-8, -7, -1))
        self._cast(values)
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8788)), 1)
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8787)), 1)
        self.assertNotEqual(
            self._states(runtime.fight.actors[owner], 8788)[0], cooldown
        )

    def _bind_recovered(self, values):
        from wakfu_server.combat_reproduction_actions import (
            bind_runtime,
            AUTHORITY_RECIPE,
        )

        char, monster, deck, rng, runtime, stats = values
        before = snapshot(runtime.fight)
        # Typed reproduction omits callable services. Restore the production
        # ordinary-server-runtime-v1 authority before movement or real turns.
        inputs = dict(
            authority_recipe=AUTHORITY_RECIPE,
            character=char,
            monsters={-200: monster},
            deck_blob=deck,
            player_characters={char["id"]: char},
            deck_blobs={char["id"]: deck},
            map_id=char["map_id"],
            native_events=True,
            area_callbacks=True,
        )
        bind_runtime(runtime, inputs, rng, runtime.clock)
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertTrue(callable(runtime.fight.native_rail_movement_authority))

    def test_typed_engine_recovery_preserves_earned_sources_and_completion_once(self):
        from wakfu_server.combat_reproduction_state import encode_state, decode_state

        values = self._fixture("distance-first")
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        self._cast(values)
        before = snapshot(runtime.fight)
        source = self._states(runtime.fight.actors[-200], 8785)[0].caster_id
        recovered = decode_state(encode_state(runtime.fight))
        self.assertIsNot(recovered, runtime.fight)
        self.assertEqual(snapshot(recovered), before)
        runtime.fight = recovered
        self._bind_recovered(values)
        self.assertEqual(
            self._states(runtime.fight.actors[-200], 8785)[0].caster_id, source
        )
        self._move(values, (-7, -7, -1))
        self._cast(values)
        self.assertFalse(self._states(runtime.fight.actors[-200], 8785))
        self.assertFalse(self._states(runtime.fight.actors[-200], 8786))
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8788)), 1)
        self.assertEqual(len(self._states(runtime.fight.actors[owner], 8787)), 1)
        second = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(second), snapshot(runtime.fight))
        runtime.fight = second
        self._bind_recovered(values)
        for _ in range(2 * len(runtime.fight.actors)):
            advance_actual_turn(runtime)
            if runtime.fight.current.id == owner:
                break
        self.assertFalse(self._states(runtime.fight.actors[owner], 8788))
        self.assertFalse(self._states(runtime.fight.actors[owner], 8787))

    def test_foreign_spell_uid_and_late_serializer_failure_preserve_canonical_state(
        self,
    ):
        values = self._fixture("distance-first")
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        self._cast(values)
        self._move(values, (-7, -7, -1))
        target = runtime.fight.actors[-200]

        def los(origin, destination, current):
            return authoritative_visible(
                char["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        before, rng_before = snapshot(runtime.fight), rng.getstate()
        with self.assertRaises(ValueError):
            prepare_server_spell(
                struct.pack(
                    ">qqiih", owner, ((owner + 100) << 32) | 4780, *target.position
                ),
                char,
                {-200: monster},
                runtime.fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), rng_before)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", owner, (owner << 32) | 4780, *target.position),
            char,
            {-200: monster},
            runtime.fight,
            char["account_id"],
            deck,
            action_id=runtime.action_id + 1,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(len(self._states(transaction.fight.actors[owner], 8788)), 1)
        self.assertEqual(snapshot(runtime.fight), before)
        # Commit itself consumes no RNG. Its canonical publication must remain
        # atomic when a late serializer fails after the complete reactive preview.
        commit_rng = rng.getstate()

        def reject_serializer(actor, preview):
            raise RuntimeError("late equipment serialization failure")

        with self.assertRaisesRegex(RuntimeError, "late equipment serialization"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=reject_serializer
            )
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual(rng.getstate(), commit_rng)
        self.assertTrue(self._states(runtime.fight.actors[-200], 8785))
        self.assertFalse(self._states(runtime.fight.actors[owner], 8788))


def load_tests(loader, tests, pattern):
    """Discover only owned lifecycle methods, excluding imported/inherited positives."""
    import unittest

    return unittest.TestSuite(
        ReactiveEquipmentDamageLifecycleTests(name)
        for name in (
            "test_repeated_paid_hit_cooldown_and_real_turn_expiration",
            "test_typed_engine_recovery_preserves_earned_sources_and_completion_once",
            "test_foreign_spell_uid_and_late_serializer_failure_preserve_canonical_state",
        )
    )
