"""Original315 Feca definitions retain exact timers and expire via central Qf removal."""
from copy import deepcopy
from dataclasses import replace
from wakfu_server.combat_state_timing import StateTimer
import random
import struct
import unittest
import test_combat_spell_transaction as fixture_module
from wakfu_server.spells import encode_deck
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_timed_expiration import prepare_timed_expiration
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot


class AreaTimedExpirationTests(unittest.TestCase):
    def fixture(self):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            1, 200, native_qi=True
        )
        deck = encode_deck([6967], [])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(1),
            fight_start=True,
        )
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6967, -5, -7, -1),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.runtime_source = (character, monster, deck)
        return tx.fight

    def test_area_timer_wrong_clock_preserves_and_due_clock_removes_native_envelope(
        self,
    ):
        fight = self.fixture()
        before = snapshot(fight)
        areas = list(fight.native_owned_area_effects.values())
        self.assertTrue(areas)
        for row in areas:
            self.assertEqual(
                row["timer"], dict(actor_id=7, expiration_round=2, phase="start")
            )
        wrong, packets = prepare_timed_expiration(
            fight, actor_id=-7, round_number=2, phase="start", action_id=3
        )
        self.assertEqual(set(wrong.native_effect_areas), set(fight.native_effect_areas))
        self.assertFalse(packets)
        expired, packets = prepare_timed_expiration(
            fight, actor_id=7, round_number=2, phase="start", action_id=3
        )
        self.assertFalse(expired.native_effect_areas)
        self.assertFalse(expired.native_owned_area_effects)
        removals = [body for opcode, body in packets if opcode == 13560]
        for row in areas:
            self.assertTrue(
                any(
                    struct.unpack(">qq", body[-16:]) == (7, row["uid"])
                    for body in removals
                )
            )
        self.assertEqual(snapshot(fight), before)

    def test_expiring_parent_removes_indefinite_owned_area_through_qf(self):
        fight = self.fixture()
        # Synthetic ownership variant of actual retained state/area carriers:
        # isolate parent expiry independently of the area's own duration.
        parent = next(
            entry
            for actor in fight.actors.values()
            for entry in actor.state_ledger.entries
            if entry.uid in fight.state_wire_payloads
        )
        manager = fight.actors[parent.target_id]
        manager.state_ledger._entries = tuple(
            replace(entry, timer=StateTimer(7, 2, "start"))
            if entry.uid == parent.uid
            else replace(entry, timer=None)
            for entry in manager.state_ledger.entries
        )
        child_uids = tuple(fight.native_owned_area_effects)
        for child_uid in child_uids:
            child = fight.native_owned_area_effects[child_uid]
            child["timer"] = None
            child["state_uid"] = parent.uid
            record = fight.native_retained_records[child_uid]
            record["owner_uid"] = parent.uid
            record["container_present"] = True
            record["container_type"] = 1
            record["container_id"] = parent.reference
        before = snapshot(fight)
        expired, packets = prepare_timed_expiration(
            fight, actor_id=7, round_number=2, phase="start", action_id=3
        )
        self.assertFalse(expired.native_owned_area_effects)
        self.assertFalse(expired.native_effect_areas)
        self.assertNotIn(parent.uid, expired.state_wire_payloads)
        removals = [body for opcode, body in packets if opcode == 13560]
        for child_uid in child_uids:
            self.assertTrue(
                any(
                    struct.unpack(">qq", body[-16:]) == (7, child_uid)
                    for body in removals
                )
            )
        self.assertEqual(snapshot(fight), before)

    def test_expiration_uses_actual_area_callbacks_for_nonempty_child_registry(self):
        from wakfu_server.combat_server_spell import server_runtime

        fight = self.fixture()
        character, monster, deck = self.runtime_source
        # Explicit nonempty registry variant: the callback, not expiry, decides
        # exit-mask cleanup. The referenced child is an actual retained runner.
        child_uid = next(iter(fight.native_retained_records))
        for row in fight.native_effect_areas.values():
            row.setdefault("child_effect_uids", {})["7"] = [child_uid]

        def runtime_factory(*, action_id):
            return server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=random.Random(1),
            )[0]

        before = snapshot(fight)
        expired, packets = prepare_timed_expiration(
            fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=3,
            runtime_factory=runtime_factory,
        )
        self.assertFalse(expired.native_effect_areas)
        self.assertFalse(expired.native_owned_area_effects)
        self.assertTrue(any(opcode == 13560 for opcode, body in packets))
        self.assertEqual(snapshot(fight), before)

    def test_runtime_precheck_includes_owned_area_timer_and_atomic_bad_clock(self):
        runtime = RuntimeMessages(self.fixture())
        packets = runtime._expire_owned(actor_id=7, round_number=2, phase="start")
        self.assertFalse(runtime.fight.native_effect_areas)
        self.assertTrue(any(opcode == 13560 for opcode, body in packets))
        fight = self.fixture()
        row = next(iter(fight.native_owned_area_effects.values()))
        row["timer"]["actor_id"] = 999
        before = snapshot(fight)
        with self.assertRaisesRegex(ValueError, "area timer"):
            prepare_timed_expiration(
                fight, actor_id=7, round_number=2, phase="start", action_id=3
            )
        self.assertEqual(snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
