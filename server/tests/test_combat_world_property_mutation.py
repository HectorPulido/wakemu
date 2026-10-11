"""Typed PB namespace, lazy manager and ordered eHN notifications."""
import unittest
from wakfu_server.combat_world_property_mutation import mutate_property_manager


class WorldPropertyMutationTests(unittest.TestCase):
    def test_absent_fight_manager_is_not_created(self):
        calls = []
        self.assertIsNone(
            mutate_property_manager(
                None, 31, namespace=1, applying=True, notify=lambda *a: calls.append(a)
            )
        )
        self.assertEqual(calls, [])

    def test_world_lazy_counter_and_last_removal_reset(self):
        calls = []
        counts = mutate_property_manager(
            None, 83, namespace=0, applying=True, notify=lambda *a: calls.append(a)
        )
        self.assertEqual(counts, {83: 1})
        self.assertIsNone(
            mutate_property_manager(
                counts,
                83,
                namespace=0,
                applying=False,
                notify=lambda *a: calls.append(a),
            )
        )
        self.assertEqual(calls, [(83, True), (83, False)])

    def test_existing_manager_notifies_even_absent_decrement(self):
        calls = []
        counts = {12: 2}
        result = mutate_property_manager(
            counts,
            83,
            namespace=0,
            applying=False,
            notify=lambda *a: calls.append((dict(counts), a)),
        )
        self.assertIs(result, counts)
        self.assertEqual(calls, [({12: 2}, (83, False))])

    def test_signed_byte_wrap_keeps_nonzero_negative_presence(self):
        counts = {83: 127}
        mutate_property_manager(
            counts, 83, namespace=0, applying=True, notify=lambda *_: None
        )
        self.assertEqual(counts, {83: -128})

    def test_namespace_bool_or_float_rejects_without_mutation_or_notification(self):
        for namespace in (True, False, 0.0, 1.0):
            counts = {83: 1}
            calls = []
            with self.assertRaisesRegex(
                ValueError, "typed property mutation authority"
            ):
                mutate_property_manager(
                    counts,
                    83,
                    namespace=namespace,
                    applying=True,
                    notify=lambda *a: calls.append(a),
                )
            self.assertEqual(counts, {83: 1})
            self.assertEqual(calls, [])
