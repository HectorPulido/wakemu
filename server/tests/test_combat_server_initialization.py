import unittest
from copy import deepcopy
from unittest.mock import patch
from random import Random
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.combat_relative_probability import RelativeGroupAuthority
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck
from wakfu_server.combat_state import Actor
import test_combat_spell_transaction as fixture_module


class ServerInitializationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.SpellTransactionTests()
        self.character, monster, self.fight = fixture.native_server_fixture(16, 60)
        self.monsters = {monster["id"]: monster}
        self.deck = encode_deck((), [6936])

    def test_server_initialization_uses_relative_provider_and_never_double_installs(
        self,
    ):
        before = snapshot(self.fight)
        seen = []
        original = RelativeGroupAuthority.__call__

        def capture(provider, *args):
            seen.append(args[2]["effect_class"])
            return original(provider, *args)

        with patch.object(RelativeGroupAuthority, "__call__", capture):
            preview, packets = prepare_server_initialization(
                self.character,
                self.monsters,
                self.fight,
                3,
                self.deck,
                action_id=1,
                rng=Random(7),
            )
        self.assertIn(999, seen)
        self.assertTrue(preview.native_class_initializations)
        self.assertTrue(packets)
        self.assertEqual(snapshot(self.fight), before)
        stable = snapshot(preview)
        with self.assertRaises(ValueError):
            prepare_server_initialization(
                self.character,
                self.monsters,
                preview,
                3,
                self.deck,
                action_id=2,
                rng=Random(7),
            )
        self.assertEqual(snapshot(preview), stable)

    def test_unsupported_relative_child_rolls_back_earlier_innates(self):
        before = snapshot(self.fight)
        with patch.object(
            RelativeGroupAuthority,
            "__call__",
            side_effect=ValueError("Native population unavailable"),
        ):
            with self.assertRaisesRegex(ValueError, "population unavailable"):
                prepare_server_initialization(
                    self.character,
                    self.monsters,
                    self.fight,
                    3,
                    self.deck,
                    action_id=1,
                    rng=Random(7),
                )
        self.assertEqual(snapshot(self.fight), before)

    def test_real_sacro_start_passive_applies_state_3231_without_forcing_child(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(11, 20)
        deck = encode_deck((), [5051])
        before = snapshot(fight)
        installed, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
        )
        self.assertFalse(installed.native_start_event_delivered)
        self.assertNotIn(
            3231, {s.reference for s in installed.actors[7].state_ledger.entries}
        )
        started, packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        self.assertTrue(started.native_start_event_delivered)
        self.assertIn(
            3231, {s.reference for s in started.actors[7].state_ledger.entries}
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_real_iop_virility_passive_installs_state_3229(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(8, 20)
        deck = encode_deck((), [4795])
        before = snapshot(fight)
        installed, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        activated = []
        execute_activation = EffectDispatcher.execute_activation

        def capture_activation(dispatcher, invocation, **kwargs):
            if invocation.reference == 149539:
                activated.append(invocation.native_retained_container)
            return execute_activation(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute_activation", capture_activation):
            started, packets = prepare_server_initialization(
                character,
                {monster["id"]: monster},
                fight,
                3,
                deck,
                action_id=1,
                rng=Random(7),
                fight_start=True,
            )
        self.assertTrue(started.native_start_event_delivered)
        retained = next(
            row
            for row in installed.native_owned_group_effects.values()
            if row["invocation"]["reference"] == 149539
        )
        parent_container = retained["native_retained_container"]
        self.assertEqual(parent_container["level"], 20)
        self.assertEqual(parent_container["id"], (4795 << 16) | 20)
        import json

        checkpoint = json.loads(json.dumps(snapshot(installed)))
        checkpoint_group = next(
            row
            for row in checkpoint["native_owned_group_effects"].values()
            if row["invocation"]["reference"] == 149539
        )
        self.assertEqual(
            checkpoint_group["native_retained_container"], parent_container
        )
        self.assertTrue(activated)
        self.assertEqual(activated[0], parent_container)

        from wakfu_server.combat_start_events import deliver_fight_start

        def replay_checkpoint(saved, *, legacy=False):
            restored = deepcopy(installed)
            restored.native_owned_group_effects = {
                int(uid): row
                for uid, row in saved["native_owned_group_effects"].items()
            }
            restored.native_retained_records = {
                int(uid): row for uid, row in saved["native_retained_records"].items()
            }
            restored.native_retained_order = list(saved["native_retained_order"])
            restored.native_class_initializations = {
                int(actor_id): row
                for actor_id, row in saved["native_class_initializations"].items()
            }
            group_uid = next(
                uid
                for uid, row in restored.native_owned_group_effects.items()
                if row["invocation"]["reference"] == 149539
            )
            if legacy:
                restored.native_owned_group_effects[group_uid].pop(
                    "native_retained_container"
                )
                restored.native_retained_records[group_uid]["container_id"] = None
            factory, _ = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=9,
                critical=False,
                rng=Random(7),
            )
            dispatcher, _ = factory(
                restored, {"native_retained_container": {"present": False}}
            )
            with restored.effect_resolution():
                deliver_fight_start(
                    dispatcher, initialized_actor_ids=tuple(restored.actors)
                )
            return restored

        restored = replay_checkpoint(checkpoint)
        self.assertIn(
            3229, {state.reference for state in restored.actors[7].state_ledger.entries}
        )
        # Older checkpoints lack the explicit context and the redundant
        # RetainedEffect.container_id. Rebuild only when Qe payload, stored
        # parent invocation level, native spell type, and effect-tree membership
        # agree; never infer from a child invocation.
        legacy = replay_checkpoint(checkpoint, legacy=True)
        self.assertIn(
            3229, {state.reference for state in legacy.actors[7].state_ledger.entries}
        )
        self.assertNotIn(
            3229,
            {state.reference for state in installed.actors[7].state_ledger.entries},
        )
        self.assertIn(
            3229,
            {state.reference for state in started.actors[7].state_ledger.entries},
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_start_failure_discards_initialization_and_uid_changes(self):
        before = snapshot(self.fight)
        with patch(
            "wakfu_server.combat_start_events.deliver_fight_start",
            side_effect=ValueError("Native start child unavailable"),
        ):
            with self.assertRaisesRegex(ValueError, "start child unavailable"):
                prepare_server_initialization(
                    self.character,
                    self.monsters,
                    self.fight,
                    3,
                    self.deck,
                    action_id=1,
                    rng=Random(7),
                    fight_start=True,
                )
        self.assertEqual(snapshot(self.fight), before)

    def test_common_factory_combines_catalog_and_keeps_passive_deck_owned(self):
        factory, adapter = server_runtime(
            self.character,
            self.monsters,
            self.deck,
            action_id=1,
            critical=False,
            rng=Random(7),
        )
        self.assertIsInstance(factory.relative_group_children, RelativeGroupAuthority)
        self.assertIs(factory.relative_group_children.effects, factory.effects)
        self.assertIn(6936, adapter.actor_authority.ordinary.decks[7])

    def test_shared_runtime_accepts_per_owner_character_and_deck_snapshots(self):
        second = deepcopy(self.character)
        second.update(id=8, account_id=4, breed=self.character["breed"])
        second_deck = encode_deck([], [])
        characters = {7: self.character, 8: second}
        decks = {7: self.deck, 8: second_deck}
        factory, adapter = server_runtime(
            self.character,
            self.monsters,
            self.deck,
            action_id=1,
            critical=False,
            rng=Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        shared = deepcopy(self.fight)
        shared.actors[8] = Actor(
            8,
            0,
            (1, 0, 0),
            50,
            6,
            3,
            90,
            1,
            4,
            True,
        )
        adapter.actor_authority(shared, shared.actors[8])
        self.assertIn(6936, adapter.actor_authority.ordinary.decks[7])
        self.assertEqual(adapter.actor_authority.ordinary.decks[8], frozenset())
        self.assertIs(factory.relative_group_children.effects, factory.effects)

    def test_shared_runtime_requires_exact_deck_snapshot_for_each_owner(self):
        second = deepcopy(self.character)
        second.update(id=8, account_id=4)
        with self.assertRaisesRegex(ValueError, "Every controlled player"):
            server_runtime(
                self.character,
                self.monsters,
                self.deck,
                action_id=1,
                critical=False,
                player_characters={7: self.character, 8: second},
                deck_blobs={7: self.deck},
            )

    def test_shared_roster_initializes_each_owner_and_casts_with_its_deck(self):
        import struct
        from copy import deepcopy
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_state import Actor

        (
            first,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(15, 1)
        from wakfu_server.monsters import owned_instance

        monster = owned_instance(5525, 1, -7, map_id=1134, x=1, y=0, z=0)
        first.update(account_id=3)
        (
            second,
            _second_monster,
            second_fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(15, 1)
        second.update(id=8, account_id=4, x=0, y=0, z=0)
        first.update(x=-1, y=0, z=0)
        fight.actors[7].position = (-1, 0, 0)
        fight.actors[-7].position = (1, 0, 0)
        second_actor = Actor(
            8,
            0,
            (0, 0, 0),
            second["hp"],
            6,
            3,
            200,
            1,
            4,
            True,
            max_hp=second["max_hp"],
        )
        second_actor.turn_count = 1
        build_player_snapshot(
            second, second_actor, wp_current=6, wp_maximum=6, running_effects=()
        ).install(second_actor)
        fight.actors[8] = second_actor
        fight.ready_owners.clear()
        fight.phase = "placement"
        fight.order = []
        fight.turn_index = 0
        fight.turn_id = 0
        fight.placement[0].update({(-1, 0, 0), (0, 0, 0)})
        fight.placement[1].add((1, 0, 0))
        fight._check_positions()
        fight.order = [8, 7, -7]
        fight.turn_index = 0
        fight.native_effect_uid_next = 1
        freeze_terrain(fight)

        first_deck = encode_deck([], [])
        second_deck = encode_deck([6266], [])
        first["builds"] = {0: {"deck": first_deck.hex()}}
        second["builds"] = {0: {"deck": second_deck.hex()}}

        class SnapshotStore:
            def character(self, account_id, character_id):
                value = {7: first, 8: second}.get(character_id)
                if value is None or value["account_id"] != account_id:
                    raise ValueError("Unknown owner character snapshot")
                return deepcopy(value)

        adapter = CombatSessionAdapter(SnapshotStore())
        left = Session(3, 7, "left-generation", 1134, 0)
        right = Session(4, 8, "right-generation", 1134, 0)
        ready = adapter.ready_transition(
            left, fight, None, True, {-7: monster}, fight_start=False
        )
        self.assertEqual(ready.fight.phase, "placement")
        ready = adapter.ready_transition(
            right,
            ready.fight,
            ready.runtime,
            True,
            {-7: monster},
            fight_start=False,
            previous_native_action_id=(
                0 if ready.runtime is None else ready.runtime.native_action_id
            ),
        )
        initialized = ready.fight
        characters, decks = adapter.player_sources(initialized)
        self.assertTrue(initialized.actors[7].effect_stats)
        self.assertTrue(initialized.actors[8].effect_stats)
        self.assertEqual(decks[7], first_deck)
        self.assertEqual(decks[8], second_deck)
        self.assertEqual(characters[8]["id"], 8)
        self.assertEqual(initialized.current.id, 8)

        transaction = prepare_server_spell(
            struct.pack(">qqiih", 8, (8 << 32) | 6266, 1, 0, 0),
            second,
            {-7: monster},
            initialized,
            4,
            decks[8],
            action_id=2,
            line_of_sight=lambda *_args: True,
            critical=False,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(transaction.plan["actor_id"], 8)
        self.assertEqual(transaction.fight.actors[8].ap, initialized.actors[8].ap - 4)
        self.assertEqual(initialized.actors[8].ap, 6)
