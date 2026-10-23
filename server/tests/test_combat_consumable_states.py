"""Combat projection and return identity for persisted consumable states."""
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from wakfu_server.combat_consumable_states import (
    install,
    restore_checkpoint_projection,
    returning_states,
)
from wakfu_server.fight_checkpoint_store import snapshot


class CombatConsumableStateProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests

        NativeRuntimeFactoryTests.setUpClass()

    def setUp(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests

        self.fixture = NativeRuntimeFactoryTests()
        self.fixture.setUp()
        # The state children touch several ordinary characteristics; the
        # projection fixture supplies a complete bounded profile for them.
        for actor in self.fixture.fight.actors.values():
            for i in range(1, 200):
                actor.effect_stats.setdefault(i, 0)
                actor.effect_minima.setdefault(i, 0)
                actor.effect_maxima.setdefault(i, 100_000)

    def state_row(self):
        return dict(
            uid=901,
            state_id=1210,
            level=10,
            clock="wall",
            duration_ms=900_000,
            remaining_ms=500_000,
            effect_ids=(64544, 64545, 64546),
        )

    def test_projection_keeps_realtime_carrier_and_returns_elapsed_clock(self):
        fight = self.fixture.fight
        character = {"id": 7, "consumable_states": [self.state_row()]}

        packets = install(
            fight, character, self.fixture.factory(), owner_id=3, now_ms=1_000
        )

        self.assertTrue(packets)
        actor = fight.actors[7]
        entry = next(e for e in actor.state_ledger.entries if e.reference == 1210)
        self.assertIsNone(entry.timer)
        self.assertTrue(entry.realtime_in_combat)
        self.assertEqual(entry.realtime_deadline_ms, 501_000)
        self.assertEqual(
            returning_states(fight, 7, now_ms=101_000),
            (
                {
                    "uid": 901,
                    "state_id": 1210,
                    "removed": False,
                    "level": 10,
                    "clock": "wall",
                    "remaining_ms": 400_000,
                },
            ),
        )

        saved = snapshot(fight)
        self.assertEqual(
            saved["native_consumable_initializations"]["7"][0]["world_uid"], 901
        )

    def test_removal_tracks_projected_uid_not_same_reference_reapplication(self):
        fight = self.fixture.fight
        install(
            fight,
            {"id": 7, "consumable_states": [self.state_row()]},
            self.fixture.factory(),
            owner_id=3,
            now_ms=1_000,
        )
        actor = fight.actors[7]
        projected = next(e for e in actor.state_ledger.entries if e.reference == 1210)
        actor.state_ledger.remove(projected.uid)

        # A later native combat cast may apply the same state reference. It
        # must not impersonate the world-owned carrier when returning to-world.
        actor.state_ledger.apply(
            self.fixture.states,
            1210,
            10,
            caster_id=7,
            uid=projected.uid + 1000,
            applying_effect_has_delay=False,
        )
        self.assertEqual(
            returning_states(fight, 7, now_ms=2_000),
            ({"uid": 901, "state_id": 1210, "removed": True},),
        )

    def test_terminal_checkpoint_restores_only_bound_consumable_carriers(self):
        fight = self.fixture.fight
        install(
            fight,
            {"id": 7, "consumable_states": [self.state_row()]},
            self.fixture.factory(),
            owner_id=3,
            now_ms=1_000,
        )
        checkpoint = snapshot(fight)
        other = type(self.fixture)()
        other.setUp()
        for actor in other.fight.actors.values():
            for index in range(1, 200):
                actor.effect_stats.setdefault(index, 0)
                actor.effect_minima.setdefault(index, 0)
                actor.effect_maxima.setdefault(index, 100_000)

        restore_checkpoint_projection(other.fight, checkpoint)

        self.assertEqual(
            returning_states(other.fight, 7, now_ms=1_000),
            (
                {
                    "uid": 901,
                    "state_id": 1210,
                    "removed": False,
                    "level": 10,
                    "clock": "wall",
                    "remaining_ms": 500_000,
                },
            ),
        )

    def test_turbo_craft_imports_and_retires_native_job_manager_rows(self):
        from wakfu_server.combat_effect_profession import (
            NativeProfessionHandler,
            manager_value,
            remove_profession,
        )

        fight = self.fixture.fight
        before_stats = dict(fight.actors[7].effect_stats)
        row = dict(
            uid=902,
            state_id=4073,
            level=1,
            clock="online",
            duration_ms=1_800_000,
            remaining_ms=1_000_000,
            effect_ids=(173760, 173761, 173762),
        )
        install(
            fight,
            {"id": 7, "consumable_states": [row]},
            self.fixture.factory(
                displacement_authority=lambda _fight, _actor: SimpleNamespace(
                    targeting={"is_eGj": True}
                )
            ),
            owner_id=3,
            now_ms=1_000,
        )

        self.assertEqual(manager_value(fight, 7, "xp", 64, 3), 100)
        self.assertEqual(manager_value(fight, 7, "xp", 64, 8), 100)
        self.assertEqual(manager_value(fight, 7, "xp", 65, 3), 100)
        self.assertEqual(manager_value(fight, 7, "xp", 65, 8), 100)
        self.assertEqual(fight.actors[7].effect_stats, before_stats)
        saved = snapshot(fight)
        self.assertEqual(
            saved["native_consumable_initializations"]["7"][0]["world_uid"], 902
        )

        profession_uids = [
            uid
            for uid, effect in fight.owned_stat_effects.items()
            if effect.get("family") == "eXx" and effect.get("state_uid") is not None
        ]
        self.assertEqual(len(profession_uids), 2)
        packets = []
        removal = NativeProfessionHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=None,
            context=None,
            authority=None,
            rng=None,
        )
        remove_profession(removal, profession_uids[0])
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 13560)
        self.assertEqual(
            sum(manager_value(fight, 7, "xp", 64, kind) for kind in (3, 8)),
            100,
        )

    def test_first_aid_food_imports_native_delayed_321_and_delivers_once(self):
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests
        from random import Random

        native = SpellTransactionTests()
        character, monster, fight = native.native_server_fixture(
            19,
            200,
            native_qi=True,
        )
        monsters = {monster["id"]: monster}
        deck = encode_deck([], [])

        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        plan = next(row["plan"] for row in catalog["items"] if row["item_ref"] == 13858)
        food = plan["states"][0]
        row = dict(
            uid=903,
            state_id=food["state_id"],
            level=food["level"],
            clock="event",
            duration_ms=0,
            remaining_ms=0,
            effect_ids=tuple(food["effect_ids"]),
            metadata=food["metadata"],
        )
        character = dict(character, consumable_states=[row])
        fight, _packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        self.assertEqual(
            len(fight.native_consumable_initializations[character["id"]]), 1
        )
        self.assertEqual(len(fight.native_delay_queue["entries"]), 1)
        pending = fight.native_delay_queue["entries"][0]
        self.assertEqual(pending["clock_id"], character["id"])
        source = fight.native_owned_group_effects[pending["uid"]]
        self.assertEqual(source["effect_class"], 321)
        self.assertEqual(source["native_delayed_value"], 1335)
        self.assertIn(pending["uid"], fight.native_retained_order)

        factories, _adapter = server_runtime(
            character,
            monsters,
            deck,
            action_id=2,
            critical=False,
        )
        dispatcher, _outbox = factories(
            fight, {"native_retained_container": {"present": False}}
        )
        self.assertEqual(
            dispatcher.native_delays.boundary(
                actor_id=character["id"],
                round_number=pending["round"] - 1,
                phase=pending["phase"],
            ),
            (),
        )
        self.assertTrue(
            any(
                entry.reference == food["state_id"]
                for entry in fight.actors[character["id"]].state_ledger.entries
            )
        )
        outcomes = dispatcher.native_delays.boundary(
            actor_id=character["id"],
            round_number=pending["round"],
            phase=pending["phase"],
        )
        self.assertEqual(outcomes, (True,))
        self.assertEqual(fight.native_delay_queue["entries"], [])
        self.assertNotIn(pending["uid"], fight.native_owned_group_effects)
        self.assertNotIn(pending["uid"], fight.native_retained_order)
        self.assertEqual(
            [
                entry
                for entry in fight.actors[character["id"]].state_ledger.entries
                if entry.reference == food["state_id"]
            ],
            [],
        )
        self.assertEqual(
            dispatcher.native_delays.boundary(
                actor_id=character["id"],
                round_number=pending["round"],
                phase=pending["phase"],
            ),
            (),
        )

    def test_all_first_aid_variants_use_their_native_delayed_expiry(self):
        """Each item-specific 1335 plan reaches the native 321 delay runner."""
        from random import Random

        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.spells import encode_deck

        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        # These five recipes share state 1335, but the native delay varies by
        # item. Exercise each real plan and its actual combat runner so a
        # catalog-wide approximation cannot hide a missing item branch.
        expected_delays = {
            13858: 10,
            13862: 5,
            13886: 15,
            14055: 10,
            19095: 10,
        }
        for item_ref, expected_delay in expected_delays.items():
            with self.subTest(item_ref=item_ref):
                (
                    character,
                    monster,
                    fight,
                ) = SpellTransactionTests().native_server_fixture(
                    19,
                    200,
                    native_qi=True,
                )
                monsters = {monster["id"]: monster}
                deck = encode_deck([], [])
                plan = next(
                    item["plan"]
                    for item in catalog["items"]
                    if item["item_ref"] == item_ref
                )
                state = next(row for row in plan["states"] if row["state_id"] == 1335)
                character = dict(
                    character,
                    consumable_states=[
                        dict(
                            uid=90_300 + item_ref,
                            state_id=state["state_id"],
                            level=state["level"],
                            clock=state["clock"],
                            duration_ms=state["duration_ms"],
                            remaining_ms=state["duration_ms"],
                            effect_ids=tuple(state["effect_ids"]),
                            metadata=state["metadata"],
                        )
                    ],
                )
                fight, _ = prepare_server_initialization(
                    character,
                    monsters,
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=Random(1),
                    fight_start=False,
                )
                pending_rows = fight.native_delay_queue["entries"]
                self.assertEqual(len(pending_rows), 1)
                pending = pending_rows[0]
                source = fight.native_owned_group_effects[pending["uid"]]
                self.assertEqual(source["effect_class"], 321)
                self.assertEqual(source["native_delayed_value"], 1335)
                self.assertEqual(pending["round"], expected_delay + 1)
                self.assertEqual(pending["clock_id"], character["id"])

                factories, _ = server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=2,
                    critical=False,
                )
                dispatcher, _ = factories(
                    fight, {"native_retained_container": {"present": False}}
                )
                self.assertEqual(
                    dispatcher.native_delays.boundary(
                        actor_id=character["id"],
                        round_number=pending["round"] - 1,
                        phase=pending["phase"],
                    ),
                    (),
                )
                self.assertTrue(
                    any(
                        entry.reference == 1335
                        for entry in fight.actors[character["id"]].state_ledger.entries
                    )
                )
                self.assertEqual(
                    dispatcher.native_delays.boundary(
                        actor_id=character["id"],
                        round_number=pending["round"],
                        phase=pending["phase"],
                    ),
                    (True,),
                )
                self.assertEqual(fight.native_delay_queue["entries"], [])
                self.assertFalse(
                    any(
                        entry.reference == 1335
                        for entry in fight.actors[character["id"]].state_ledger.entries
                    )
                )
                self.assertEqual(
                    dispatcher.native_delays.boundary(
                        actor_id=character["id"],
                        round_number=pending["round"],
                        phase=pending["phase"],
                    ),
                    (),
                )

    def test_first_aid_native_1001_subscription_heals_through_original_runner(self):
        from random import Random

        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            19,
            200,
            native_qi=True,
        )
        monsters = {monster["id"]: monster}
        deck = encode_deck([], [])
        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        plan = next(
            item["plan"] for item in catalog["items"] if item["item_ref"] == 13858
        )
        state = next(row for row in plan["states"] if row["state_id"] == 1335)
        character = dict(
            character,
            consumable_states=[
                dict(
                    uid=93_001,
                    state_id=state["state_id"],
                    level=state["level"],
                    clock=state["clock"],
                    duration_ms=state["duration_ms"],
                    remaining_ms=state["duration_ms"],
                    effect_ids=tuple(state["effect_ids"]),
                    metadata=state["metadata"],
                )
            ],
        )
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        actor = fight.actors[character["id"]]
        set_hp_raw_current(actor, actor.max_hp - 50)
        before = actor.hp
        factories, _ = server_runtime(
            character, monsters, deck, action_id=2, critical=False
        )
        dispatcher, _ = factories(
            fight, {"native_retained_container": {"present": False}}
        )
        dispatcher.replay_event(
            NativeExternalEvent(character["id"], (1001,), 6),
            authority=dispatcher.native_clone_authority,
        )
        self.assertGreater(actor.hp, before)
        self.assertLessEqual(actor.hp, actor.max_hp)
        self.assertTrue(
            any(entry.reference == 1335 for entry in actor.state_ledger.entries)
        )

    def test_two_reactive_foods_import_native_delays_and_expire_once(self):
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests
        from random import Random

        native = SpellTransactionTests()
        character, monster, fight = native.native_server_fixture(
            19,
            200,
            native_qi=True,
        )
        monsters = {monster["id"]: monster}
        deck = encode_deck([], [])
        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        expected = {1371: (13865, 5), 3362: (19097, 10)}
        rows = []
        for index, (state_id, (item_ref, delay)) in enumerate(expected.items()):
            plan = next(
                row["plan"] for row in catalog["items"] if row["item_ref"] == item_ref
            )
            state = next(row for row in plan["states"] if row["state_id"] == state_id)
            rows.append(
                dict(
                    uid=920 + index,
                    state_id=state_id,
                    level=state["level"],
                    clock="event",
                    duration_ms=0,
                    remaining_ms=0,
                    effect_ids=tuple(state["effect_ids"]),
                    metadata=state["metadata"],
                )
            )

        character = dict(character, consumable_states=rows)
        fight, _packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        self.assertEqual(
            {
                binding["state_id"]
                for binding in fight.native_consumable_initializations[character["id"]]
            },
            {1371, 3362},
        )
        pending_by_value = {}
        for pending in fight.native_delay_queue["entries"]:
            source = fight.native_owned_group_effects[pending["uid"]]
            self.assertEqual(source["effect_class"], 321)
            pending_by_value[source["native_delayed_value"]] = pending
        self.assertEqual(set(pending_by_value), {1371, 3362})
        for state_id, (_item_ref, expected_delay) in expected.items():
            pending = pending_by_value[state_id]
            # Native table-turn 1 is the first scheduled turn.
            self.assertEqual(pending["round"], expected_delay + 1)

        factories, _adapter = server_runtime(
            character,
            monsters,
            deck,
            action_id=2,
            critical=False,
        )
        dispatcher, _outbox = factories(
            fight, {"native_retained_container": {"present": False}}
        )
        for state_id, (_item_ref, _delay) in expected.items():
            pending = pending_by_value[state_id]
            self.assertEqual(
                dispatcher.native_delays.boundary(
                    actor_id=character["id"],
                    round_number=pending["round"] - 1,
                    phase=pending["phase"],
                ),
                (),
            )
            self.assertTrue(
                any(
                    entry.reference == state_id
                    for entry in fight.actors[character["id"]].state_ledger.entries
                )
            )
            self.assertEqual(
                dispatcher.native_delays.boundary(
                    actor_id=character["id"],
                    round_number=pending["round"],
                    phase=pending["phase"],
                ),
                (True,),
            )
            self.assertFalse(
                any(
                    entry.reference == state_id
                    for entry in fight.actors[character["id"]].state_ledger.entries
                )
            )
            self.assertEqual(
                dispatcher.native_delays.boundary(
                    actor_id=character["id"],
                    round_number=pending["round"],
                    phase=pending["phase"],
                ),
                (),
            )

    def test_halloween_food_imports_both_native_event_carriers_and_returns_removal(
        self,
    ):
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests
        from random import Random

        native = SpellTransactionTests()
        character, monster, fight = native.native_server_fixture(
            19,
            200,
            native_qi=True,
        )
        monsters = {monster["id"]: monster}
        deck = encode_deck([], [])
        catalog = json.loads((DATA_ROOT / "native-consumable-actions.json").read_text())
        plan = next(row["plan"] for row in catalog["items"] if row["item_ref"] == 10374)
        rows = [
            dict(
                uid=910 + index,
                state_id=state["state_id"],
                level=state["level"],
                clock="event",
                duration_ms=0,
                remaining_ms=0,
                effect_ids=tuple(state["effect_ids"]),
                metadata=state["metadata"],
            )
            for index, state in enumerate(plan["states"])
        ]
        character = dict(character, consumable_states=rows)
        fight, _packets = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(1),
            fight_start=False,
        )
        actor = fight.actors[character["id"]]
        entries = {entry.reference: entry for entry in actor.state_ledger.entries}
        self.assertTrue({950, 748}.issubset(entries))
        bindings = fight.native_consumable_initializations[character["id"]]
        self.assertEqual({binding["state_id"] for binding in bindings}, {950, 748})
        initial_fumble = actor.effect_stats[10]
        self.assertEqual(initial_fumble, 10)
        factory, _adapter = server_runtime(
            character,
            monsters,
            deck,
            action_id=2,
            critical=False,
        )
        dispatcher, _outbox = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        from wakfu_server.combat_event_replay import NativeExternalEvent

        dispatched = dispatcher.replay_event(
            # 79519 declares a global subscription, so native channel 61 is
            # required for this 1030 listener (79520 remains channel 6).
            NativeExternalEvent(character["id"], (1030,), 61),
            authority=dispatcher.native_clone_authority,
        )
        self.assertTrue(dispatched)
        self.assertEqual(actor.effect_stats[10], 0)
        self.assertEqual(
            returning_states(fight, character["id"], now_ms=2_000),
            (
                {"uid": 910, "state_id": 950, "removed": True},
                {
                    "uid": 911,
                    "state_id": 748,
                    "removed": False,
                    "level": 50,
                    "clock": "event",
                    "remaining_ms": 0,
                },
            ),
        )


if __name__ == "__main__":
    unittest.main()
