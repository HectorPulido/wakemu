import unittest
from wakfu_server.combat_class_initialization import plan, install, BREEDS
from wakfu_server.spells import encode_deck, available_spells
from wakfu_server.spell_audit import catalog, states_catalog


class ClassInitializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spells = catalog()
        cls.states = states_catalog()

    def char(self, breed, level=200):
        return dict(id=7, breed=breed, level=level, x=0, y=0, z=0)

    def test_sacrier_cannot_inherit_uginak_state(self):
        initial = plan(self.char(11), encode_deck(), self.spells, self.states)
        self.assertEqual([s.reference for s in initial.innates], [4464, 3702])
        self.assertTrue(all(s.protected for s in initial.innates))
        self.assertNotIn(7521, [s.reference for s in initial.innates])

    def test_every_installed_breed_has_exact_native_state_triples(self):
        for breed in BREEDS:
            initial = plan(self.char(breed), encode_deck(), self.spells, self.states)
            self.assertTrue(initial.innates)
            self.assertEqual(len(initial.innates), len(BREEDS[breed]["cle"]) // 3)

    def test_own_passive_roots_installed_once_without_guessed_event(self):
        character = self.char(11)
        passive = next(
            s["id"] for s in available_spells(11, 200) if s["kind"] == "passive"
        )
        initial = plan(character, encode_deck((), [passive]), self.spells, self.states)
        expected = self.spells["spells"][str(passive)]["levels"][199][2]
        self.assertEqual([i.reference for i in initial.passive_invocations], expected)
        calls = []
        install(
            initial,
            install_innate=lambda *a: calls.append(("state", a)),
            install_passive=lambda source, i: calls.append(("passive", source, i)),
        )
        self.assertEqual(len(calls), len(initial.innates) + len(expected))

    def test_foreign_passive_rejected(self):
        foreign = next(
            s["id"]
            for s in available_spells(15, 200)
            if s["kind"] == "passive" and s["breed"] == 15
        )
        with self.assertRaises(ValueError):
            plan(self.char(11), encode_deck((), [foreign]), self.spells, self.states)

    def test_universal_passive_roots_are_owned_by_every_playable_breed(self):
        for breed in BREEDS:
            for spell in available_spells(breed, 200):
                if spell["breed"] != -2 or spell["kind"] != "passive":
                    continue
                with self.subTest(breed=breed, passive=spell["id"]):
                    initial = plan(
                        self.char(breed),
                        encode_deck((), [spell["id"]]),
                        self.spells,
                        self.states,
                    )
                    expected = self.spells["spells"][str(spell["id"])]["levels"][199][2]
                    self.assertEqual(
                        [i.reference for i in initial.passive_invocations], expected
                    )

    def test_owned_innate_protection_survives_catalog_default(self):
        from wakfu_server.combat_state_ledger import StateLedger

        ledger = StateLedger(7)
        definition = self.states["states"]["3442"]
        self.assertFalse(definition["protected"])
        change = ledger.apply(
            self.states,
            3442,
            20,
            caster_id=7,
            uid=100,
            applying_effect_has_delay=False,
            protected=True,
        )
        self.assertTrue(change.applied.protected)
        self.assertTrue(ledger.entries[0].protected)
        ordinary = StateLedger(8).apply(
            self.states, 3442, 20, caster_id=8, uid=101, applying_effect_has_delay=False
        )
        self.assertFalse(ordinary.applied.protected)

    def test_real_native_initialization_is_atomic_when_a_child_is_unsupported(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_class_initialization import initialize_transaction
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = NativeRuntimeFactoryTests()
        NativeRuntimeFactoryTests.setUpClass()
        fixture.setUp()
        initial = plan(self.char(11, 1), encode_deck(), self.spells, self.states)
        before = snapshot(fixture.fight)
        from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution

        real_factory = fixture.factory()

        def unavailable(invocation):
            raise UnsupportedEffectExecution(
                "Deliberate unavailable native child handler"
            )

        def factory(preview, source):
            dispatcher, packets = real_factory(preview, source)
            dispatcher.native_state_handler.execute_child = unavailable
            return dispatcher, packets

        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "Deliberate unavailable"
        ):
            initialize_transaction(
                fixture.fight, initial, factory, self.states, owner_id=3
            )
        self.assertEqual(snapshot(fixture.fight), before)

    def test_real_sacrier_innates_register_owned_tree_without_fabricated_events(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_class_initialization import initialize_transaction

        fixture = NativeRuntimeFactoryTests()
        NativeRuntimeFactoryTests.setUpClass()
        fixture.setUp()
        initial = plan(self.char(11, 1), encode_deck(), self.spells, self.states)
        preview, packets = initialize_transaction(
            fixture.fight, initial, fixture.factory(), self.states, owner_id=3
        )
        self.assertEqual(
            [
                (s.reference, s.protected)
                for s in preview.actors[7].state_ledger.entries
            ],
            [(4464, True), (3702, True)],
        )
        self.assertFalse(fixture.fight.actors[7].state_ledger.entries)
        self.assertTrue(packets)
        self.assertEqual(
            set(preview.native_retained_records),
            set(preview.state_wire_payloads)
            | set(preview.owned_stat_effects)
            | set(preview.native_owned_group_effects),
        )
        self.assertTrue(
            all(
                row["manager_id"] in preview.actors
                for row in preview.native_retained_records.values()
            )
        )
        with self.assertRaisesRegex(ValueError, "already initialized"):
            initialize_transaction(
                preview, initial, fixture.factory(), self.states, owner_id=3
            )

    def test_cra_start_listeners_install_once_with_eleven_actor_population(self):
        from copy import deepcopy
        from dataclasses import replace
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_class_initialization import initialize_transaction
        from wakfu_server.combat_event_replay import NativeExternalEvent

        fixture = NativeRuntimeFactoryTests()
        NativeRuntimeFactoryTests.setUpClass()
        fixture.setUp()
        owner = fixture.fight.actors[7]
        owner.turn_count = 0
        actors = [owner]
        for index in range(10):
            actor = deepcopy(fixture.fight.actors[-7])
            actor.id = 20 + index
            actor.native_obstacle_id = None
            actor.turn_count = 0
            actor.position = (index + 1, 0, 0)
            actor.state_ledger.actor_id = actor.id
            actors.append(actor)
        fixture.fight = Fight(
            77,
            actors,
            {actor.position for actor in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        from native_combat_fixture import initialize_fixture_qi

        initialize_fixture_qi(fixture.fight)
        fixture.fight.ready(3)
        # Production candidates are the full fight population. A state's
        # selected recipient must survive even an unrestricted fcE mask.
        from random import Random
        from wakfu_server.combat_ordinary_authority import (
            OrdinaryActorAuthority,
            ordinary_cast_authority,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        authority = OrdinaryActorAuthority(
            characters={owner.id: dict(self.char(2, 1), map_id=1134)},
            monsters={
                a.id: dict(id=a.id, ref=4, level=1, map_id=1134) for a in actors[1:]
            },
            decks={owner.id: []},
            excluded_decks={owner.id: []},
        )
        adapter = NativeServerRuntimeAdapter(
            actor_authority=authority,
            cast=ordinary_cast_authority(
                actors=authority,
                timing=NativeEffectTimingProvider(self.states),
                rng=Random(1),
                critical=False,
            ),
        )
        contexts = replace(
            adapter.contexts(),
            uid_start=fixture.contexts.uid_start,
            actor_candidates=lambda p, plan, e, i: tuple(p.actors.values()),
        )
        factory = fixture.factory(contexts=contexts, displacement_authority=authority)
        initial = plan(self.char(2, 1), encode_deck(), self.spells, self.states)
        preview, _ = initialize_transaction(
            fixture.fight, initial, factory, self.states, owner_id=3
        )
        roots = [
            row
            for row in preview.native_owned_group_effects.values()
            if row["invocation"]["reference"] == 326924
        ]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["target_id"], owner.id)
        self.assertEqual(roots[0]["execution_count"], 1)
        dispatcher, _ = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        # Exercise the real combat-start listener boundary (1003), separately
        # from the independent opening-mechanics boundary (1028). This checks
        # installation cardinality without making claims about those mechanics.
        for identity in preview.actors:
            for channel in (6, 60, 61):
                dispatcher.replay_event(
                    NativeExternalEvent(identity, (1003,), channel),
                    authority=dispatcher.native_clone_authority,
                )
        children = set(self.states["effects"]["326924"]["children"])
        self.assertEqual(len(children), 32)
        listeners = [
            row
            for row in preview.native_owned_group_effects.values()
            if row["invocation"]["reference"] in children
        ]
        self.assertEqual(len(listeners), 32)
        self.assertEqual({row["target_id"] for row in listeners}, {owner.id})
        self.assertEqual(
            {row["invocation"]["reference"] for row in listeners}, children
        )
        self.assertFalse(
            any(
                row["invocation"]["reference"] == 326924
                for row in preview.native_owned_group_effects.values()
            )
        )
