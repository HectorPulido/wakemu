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
            s["id"] for s in available_spells(15, 200) if s["kind"] == "passive"
        )
        with self.assertRaises(ValueError):
            plan(self.char(11), encode_deck((), [foreign]), self.spells, self.states)

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
