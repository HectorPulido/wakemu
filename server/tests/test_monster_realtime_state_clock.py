"""Realtime state clocks preserve the installed eZV combat exception."""
import json
import unittest
from wakfu_server.combat.combat_realtime_state_clock import (
    register_realtime_state,
    migrate_realtime_state,
    expire_realtime_states,
)


class RealtimeStateClockTests(unittest.TestCase):
    def test_actual_1697_and_1409_duration_expire_only_outside_combat(self):
        # Actual source witness: both fyW.guH=600000, cxj=true, cxn=false.
        for state in (1697, 1409):
            clocks, removed = {}, []
            register_realtime_state(
                clocks, uid=state, duration_ms=600000, now_ms=1000, in_combat=False
            )
            self.assertEqual(
                expire_realtime_states(clocks, now_ms=600999, remove=removed.append), ()
            )
            self.assertEqual(removed, [])
            self.assertEqual(
                expire_realtime_states(clocks, now_ms=601000, remove=removed.append),
                (state,),
            )
            self.assertEqual(removed, [state])
            self.assertEqual(clocks, {})

    def test_native_java_state310_combat_callback_keeps_state_and_children(self):
        clocks, removed = {}, []
        register_realtime_state(
            clocks, uid=1697, duration_ms=600000, now_ms=1000, in_combat=False
        )
        migrate_realtime_state(clocks, 1697, now_ms=1001, in_combat=True)
        before = json.dumps(clocks, sort_keys=True)
        for now in (1001, 601000, 1201000):
            self.assertEqual(
                expire_realtime_states(clocks, now_ms=now, remove=removed.append), ()
            )
        self.assertEqual(json.dumps(clocks, sort_keys=True), before)
        self.assertEqual(removed, [])

    def test_native_clone_uses_one_millisecond_when_old_deadline_passed(self):
        clocks = {}
        register_realtime_state(
            clocks, uid=1, duration_ms=1, now_ms=1000, in_combat=True
        )
        migrate_realtime_state(clocks, 1, now_ms=2000, in_combat=False)
        self.assertEqual(clocks[1]["deadline_ms"], 2001)
        removed = []
        expire_realtime_states(clocks, now_ms=2000, remove=removed.append)
        self.assertEqual(removed, [])
        expire_realtime_states(clocks, now_ms=2001, remove=removed.append)
        self.assertEqual(removed, [1])

    def test_bad_authority_and_failed_removal_preserve_owned_timer(self):
        clocks = {}
        with self.assertRaises(ValueError):
            register_realtime_state(
                clocks, uid=1, duration_ms=600000, now_ms=0, in_combat=None
            )
        register_realtime_state(clocks, uid=1, duration_ms=1, now_ms=0, in_combat=False)
        with self.assertRaises(ValueError):
            register_realtime_state(
                clocks, uid=1, duration_ms=1, now_ms=0, in_combat=False
            )

        def failed(uid):
            raise RuntimeError("Removal failed")

        with self.assertRaises(RuntimeError):
            expire_realtime_states(clocks, now_ms=1, remove=failed)
        self.assertIn(1, clocks)


class RealtimeInitialPipelineTests(unittest.TestCase):
    def fixture(self, state_id=1697):
        import test_combat_initial_state_finite_constructor as source_fixture

        base = source_fixture.FiniteInitialConstructorTests()
        base.setUp()
        definition = base.catalog["states"].pop("123")
        definition.update(
            duration_base=-1, realtime_duration_base=600000, skip_turn_timer=True
        )
        base.catalog["states"][str(state_id)] = definition
        return base

    def install(self, base, state_id, level=1, flag=0):
        from unittest.mock import patch
        from wakfu_server.combat.combat_summon_initialization import (
            detached_summon_scope,
            install_initial_states,
        )
        from wakfu_server.combat.combat_summon_initial_states import initial_state_plan

        with detached_summon_scope(base.fight, base.actor, base.authority), patch(
            "time.time_ns", return_value=1000000000
        ):
            return install_initial_states(
                base.fight,
                base.actor,
                initial_state_plan([state_id, level, flag], 1),
                runtime_factory=lambda *a: (base.dispatcher, base.packets),
            )

    def test_actual_duration_constructor_migrates_and_checkpoint_keeps_clock(self):
        from wakfu_server.combat.fight_checkpoint_store import snapshot
        from wakfu_server.combat.combat_state_ledger import RunningState

        for state_id in (1697, 1409):
            base = self.fixture(state_id)
            hp = base.actor.hp
            self.install(base, state_id)
            (entry,) = base.actor.state_ledger.entries
            self.assertEqual(entry.realtime_duration, 600000)
            self.assertEqual(entry.realtime_deadline_ms, 601000)
            self.assertTrue(entry.realtime_in_combat)
            self.assertIsNone(entry.timer)
            self.assertEqual(base.actor.hp, hp)
            self.assertEqual(
                base.actor.state_ledger.expire(
                    actor_id=base.actor.id, round_number=999, phase="end"
                ),
                (),
            )
            base.fight.actors[base.actor.id] = base.actor
            checkpoint = json.loads(json.dumps(snapshot(base.fight)))
            row = checkpoint["actors"][str(base.actor.id)]["state_ledger"]["entries"][0]
            row["effect_ids"] = tuple(row["effect_ids"])
            restored = RunningState(**row)
            self.assertEqual(restored, entry)
            clocks = {
                restored.uid: dict(
                    deadline_ms=restored.realtime_deadline_ms,
                    in_combat=restored.realtime_in_combat,
                )
            }

            def forbidden(uid):
                self.fail("Installed native state310 suppresses combat expiry")

            self.assertEqual(
                expire_realtime_states(clocks, now_ms=9999999, remove=forbidden), ()
            )
            self.assertEqual(base.actor.state_ledger.entries, (entry,))

    def test_removal_and_replacement_drop_clock_with_carrier(self):
        base = self.fixture()
        self.install(base, 1697, flag=1)
        old = base.actor.state_ledger.entries[0]
        # This is the same central removal primitive used by decurse/retained
        # removal; its clock is owned by the removed immutable carrier.
        self.assertEqual(base.actor.state_ledger.remove(old.uid), old)
        self.assertEqual(base.actor.state_ledger.entries, ())
        self.install(base, 1697, flag=1)
        self.assertIsNotNone(base.actor.state_ledger.entries[0].realtime_deadline_ms)
        base.handler.allocate_uid = lambda: 901
        self.install(base, 1697, level=2, flag=1)
        self.assertEqual(
            [entry.uid for entry in base.actor.state_ledger.entries], [901]
        )
        self.assertEqual(
            base.actor.state_ledger.entries[0].realtime_deadline_ms, 601000
        )

    def test_unknown_phase_or_unqualified_profile_rejects_before_mutation(self):
        for unsupported in ("phase", "turn_timer"):
            base = self.fixture()
            if unsupported == "phase":
                base.fight.phase = "finished"
            else:
                base.catalog["states"]["1697"]["skip_turn_timer"] = False
            with self.assertRaisesRegex(ValueError, "audited finite timeline"):
                self.install(base, 1697)
            self.assertEqual(base.actor.state_ledger.entries, ())
            self.assertEqual(base.packets, [])
