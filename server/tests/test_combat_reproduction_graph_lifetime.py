"""Completed reproduction helpers release private traversal closures promptly."""
import gc
import unittest
import weakref
from unittest.mock import patch

from wakfu_server import combat_reproduction_state as codec
from wakfu_server.combat_state import Actor


def actor():
    return Actor(7, 0, (1, 2, 0), 100, 6, 3, 10, 20)


class ReproductionGraphLifetimeTests(unittest.TestCase):
    def setUp(self):
        # Normalize the tiny witness without changing GC policy or thresholds.
        gc.collect()

    def test_successful_encode_does_not_retain_source_through_closure(self):
        source = actor()
        reference = weakref.ref(source)
        payload = codec.encode_state({"actor": source, "alias": source})
        del source
        self.assertIsNone(reference())
        restored = codec.decode_state(payload)
        self.assertIs(restored["actor"], restored["alias"])
        self.assertEqual(restored["actor"].id, 7)

    def test_rejected_encode_releases_already_visited_source(self):
        def reject():
            source = actor()
            reference = weakref.ref(source)
            with self.assertRaises(codec.UnsupportedReproductionState):
                codec.encode_state({"actor": source, "unsupported": lambda: None})
            return reference

        self.assertIsNone(reject()())

    def test_successful_decode_does_not_retain_restored_actor(self):
        payload = codec.encode_state({"actor": actor()})
        restored = codec.decode_state(payload)
        reference = weakref.ref(restored["actor"])
        del restored
        self.assertIsNone(reference())

    def test_rejected_decode_releases_already_allocated_actor(self):
        payload = codec.encode_state({"actor": actor()})
        payload["services"] = [{"node": -1, "field": "unsupported"}]
        allocated = []

        class ObservedActor(Actor):
            def __getattribute__(self, name):
                if name == "__dict__" and not allocated:
                    allocated.append(weakref.ref(self))
                return super().__getattribute__(name)

        resolve_class = codec._class
        with patch.object(
            codec,
            "_class",
            side_effect=lambda name: ObservedActor
            if name == "Actor"
            else resolve_class(name),
        ):
            with self.assertRaises(codec.UnsupportedReproductionState):
                codec.decode_state(payload)
        self.assertEqual(len(allocated), 1)
        self.assertIsNone(allocated[0]())

    def test_source_and_result_cycles_aliases_and_scalar_identity_survive(self):
        source = {"actor": actor(), "bytes": b"native", "tuple": (1, 2, 3)}
        source["alias"] = source["actor"]
        source["cycle"] = source
        for preserve in (False, True):
            with self.subTest(preserve_scalars=preserve):
                payload = codec.encode_state(source, preserve_scalars=preserve)
                restored = codec.decode_state(payload)
                self.assertIs(restored["cycle"], restored)
                self.assertIs(restored["actor"], restored["alias"])
                self.assertEqual(
                    codec.encode_state(restored, preserve_scalars=preserve), payload
                )
                self.assertIs(source["cycle"], source)
                self.assertIs(source["actor"], source["alias"])
