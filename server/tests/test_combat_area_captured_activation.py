import unittest
from types import SimpleNamespace
import test_combat_effect_area_events as area_event_tests
from wakfu_server.combat_effect_area_targets import NativeAreaTarget


class CapturedAreaActivationTests(unittest.TestCase):
    def fixture(self):
        runtime, row, calls = area_event_tests.AreaEventTests().fixture()
        definition = runtime.definitions["1474"]
        definition["native_area_properties"] = [1]
        row.update(
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
            remaining_activations=1,
        )
        target = runtime.fight.actors[8]
        target.native_is_amO = True
        target.native_fight_affiliation = 0
        return runtime, row, calls, definition, target

    def test_owner_change_does_not_change_captured_ally_filter(self):
        runtime, row, calls, definition, target = self.fixture()
        runtime.fight.actors[7].team = 1
        runtime.fight.actors[7].native_fight_affiliation = 1
        self.assertFalse(runtime._activate(row, definition, target))
        self.assertEqual((row["remaining_activations"], calls), (1, []))
        target.native_fight_affiliation = 1
        self.assertTrue(runtime._activate(row, definition, target))
        self.assertEqual(row["remaining_activations"], 0)
        self.assertEqual(len(calls), 1)

    def test_captured_filter_survives_absent_owner(self):
        runtime, row, calls, definition, target = self.fixture()
        del runtime.fight.actors[7]
        self.assertFalse(runtime._activate(row, definition, target))
        self.assertEqual(row["remaining_activations"], 1)

    def test_unknown_capture_and_unknown_target_reject_before_charge(self):
        for missing in ("capture", "target", "target_type"):
            runtime, row, calls, definition, target = self.fixture()
            if missing == "capture":
                row.pop("native_fight_affiliation_source")
            elif missing == "target":
                target.native_fight_affiliation = None
            else:
                del target.native_is_amO
            with self.assertRaisesRegex(ValueError, "native"):
                runtime._activate(row, definition, target)
            self.assertEqual((row["remaining_activations"], calls), (1, []))

    def test_null_qf_area_target_reads_its_captured_affiliation(self):
        runtime, row, calls, definition, target = self.fixture()
        runtime.fight.native_effect_areas[902] = dict(
            uid=902,
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
            native_running_effect_manager=False,
        )
        area = NativeAreaTarget(902, (0, 0, 0), 1, 99)
        self.assertFalse(runtime._activate(row, definition, area))
        self.assertEqual(row["remaining_activations"], 1)

    def test_null_and_explicit_non_amo_bypass_only_this_filter(self):
        runtime, row, calls, definition, target = self.fixture()
        row.pop("native_fight_affiliation_source")
        self.assertTrue(runtime._activate(row, definition, None))
        self.assertEqual(row["remaining_activations"], 0)
        target.native_is_amO = False
        self.assertIsNone(runtime._target_affiliation(target))

    def test_real_roster_target_uses_existing_typed_affiliation_provider(self):
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority

        runtime, row, calls, definition, target = self.fixture()
        del target.native_is_amO

        class Adapter:
            def _actor(self, fight, actor):
                return NativeActorAuthority(
                    targeting=dict(is_amO=True, is_eGj=True),
                    is_player=True,
                    deck_spell_ids=frozenset(),
                    excluded_deck_spell_ids=frozenset(),
                    is_carried=False,
                    breed_id=1,
                    summon_count=0,
                    summon_counts_by_breed={},
                    occupant_blocks=True,
                )

            def affiliation(self, fight, identity):
                return 0

        adapter = Adapter()
        runtime.target_authority = adapter._actor
        runtime.area_affiliation = adapter.affiliation
        self.assertFalse(runtime._activate(row, definition, target))

    def test_actual_server_factory_binds_registered_player_and_npc_area_targets(self):
        from copy import deepcopy
        from random import Random
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            1,
            60,
            native_qi=True,
            target_distance=1,
        )
        before = snapshot(fight)
        preview = deepcopy(fight)
        factory, _ = server_runtime(
            character,
            {monster["id"]: monster},
            encode_deck(),
            action_id=2,
            critical=False,
            rng=Random(0),
        )
        dispatcher, packets = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        self.assertFalse(hasattr(dispatcher, "contexts"))
        events = dispatcher.native_area_events
        for identity in (character["id"], monster["id"]):
            target = preview.actors[identity]
            self.assertFalse(hasattr(target, "native_is_amO"))
            self.assertEqual(events._target_affiliation(target), target.team)
            # A filtered ally must not execute glyph children or consume a
            # charge. The explicit area fixture is independent of its producer.
            _, row, _, definition, _ = self.fixture()
            row.update(owner_id=identity, native_fight_affiliation=target.team)
            self.assertFalse(events._activate(row, definition, target))
            self.assertEqual(row["remaining_activations"], 1)
        self.assertEqual(len(packets), 0)
        self.assertTrue(snapshot(fight) == before, "Source fight was mutated")
