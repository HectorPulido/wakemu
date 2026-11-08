"""Native preview ownership, weak cycles and public serialization contracts."""
import gc
import sys
import unittest
import weakref
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai-service"))
from wakfu_server.combat_state import Fight
from wakfu_server import combat_retained_collections as storage
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_ai.context.native_fingerprint import fingerprint
from wakfu_ai.context.native_context import _instance_fields


def fixture(*, qi=True):
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_characteristic_link import bind_characteristic_stats

    actors = [
        Actor(1, 0, (0, 0, 0), 100, 6, 3, 20, 1),
        Actor(-1, 1, (1, 0, 0), 100, 6, 3, 10, 1),
    ]
    fight = Fight(7, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}})
    for actor in actors:
        actor.effect_stats = {120: 10}
    bind_characteristic_stats(fight)
    owner = fight.native_retained_records.owner
    owner.records.install_owned(1, {"uid": 1, "manager_id": 1})
    owner.order.append(1)
    if qi:
        from native_combat_fixture import initialize_fixture_qi
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

        initialize_fixture_qi(fight)
        fight.native_pointer_checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
    return fight


class OwnershipTests(unittest.TestCase):
    def test_release_and_standalone_alias_compatibility(self):
        fight = fixture()
        gc.collect()
        enabled = gc.isenabled()
        gc.disable()
        try:
            copied = deepcopy(fight)
            owner = copied.native_retained_records.owner
            refs = [
                weakref.ref(value)
                for value in (
                    copied,
                    owner,
                    owner.records,
                    owner.order,
                    owner.records[1],
                )
            ]
            del copied, owner
            self.assertEqual(refs[0]() is not None, False)
            self.assertEqual([r() is not None for r in refs[1:]], [False] * 4)
            gc.collect()
            self.assertTrue(all((r() is None for r in refs)))
            source = storage.RetainedCollections()
            source.records.install_owned(1, {"uid": 1, "manager_id": 2})
            source.order.append(1)
            for value in (source.records, source.order, source.records[1]):
                copied = deepcopy(value)
                self.assertIsNotNone(copied.owner)
                self.assertIsNot(copied.owner, source)
            old = source.records[1]
            source.records.install_owned(1, {"uid": 1, "manager_id": 3})
            owner, row = deepcopy((source, old))
            self.assertIs(row.owner, owner)
            self.assertEqual(row["manager_id"], 2)
            self.assertIsNot(row, owner.records[1])
        finally:
            if enabled:
                gc.enable()

    def test_codec_and_authority_bytes(self):
        fight = fixture(qi=False)
        encoded = encode_state(fight, preserve_scalars=True)
        restored = decode_state(encoded)
        owner = restored.native_retained_records.owner
        self.assertIsNotNone(owner)
        self.assertIs(restored.native_retained_records[1].owner, owner)
        self.assertIs(restored._native_retained_owner, owner)
        self.assertIs(storage.bound_collections(vars(restored)), owner)
        from wakfu_server.fight_checkpoint_store import snapshot

        signature = {
            "fingerprint": fingerprint(fight),
            "encoded": encoded,
            "checkpoint": snapshot(fight),
        }
        logical = _instance_fields(fight.native_retained_records)
        self.assertIs(logical["owner"], fight.native_retained_records.owner)
        self.assertNotIn("_owner_ref", logical)
        self.assertNotIn("_native_retained_owner", _instance_fields(fight))
        self.assertNotIn("_native_retained_owner", signature["checkpoint"])

    def test_adopted_clone_and_custom_reduction(self):
        fight = fixture()
        preview = deepcopy(fight)
        from wakfu_server.combat_area_boundary import adopt_fight

        adopt_fight(fight, preview)
        del preview
        copied = deepcopy(fight)
        owner = copied._native_retained_owner
        self.assertIs(copied.native_retained_records.owner, owner)
        self.assertNotIn("_owner_anchor", vars(owner.actors))
        self.assertNotIn("_owner_anchor", vars(owner.records))

        class CustomFight(Fight):
            reductions = 0

            def __reduce_ex__(self, protocol):
                type(self).reductions += 1
                return super().__reduce_ex__(protocol)

        checkpoint = deepcopy(fight.native_pointer_checkpoint)
        self.assertIsNot(checkpoint._qi.fight, fight)
        self.assertIs(checkpoint._qi.objects[1].actor, checkpoint._qi.fight.actors[1])
        qi = deepcopy(fight.native_pointer_checkpoint._qi)
        self.assertIsNot(qi.fight, fight)
        self.assertIs(qi.objects[1].actor, qi.fight.actors[1])
        restored = decode_state(encode_state(fight, preserve_scalars=True))
        self.assertIs(
            restored.native_pointer_checkpoint.validate(restored).fight, restored
        )
        self.assertIs(restored.actors[1].effect_stats._fight, restored)

        class CustomOwnedMap(storage.OwnedMap):
            pass

        opaque = object()
        self.assertIs(CustomOwnedMap(opaque, "records").owner, opaque)
        custom = CustomFight.__new__(CustomFight)
        custom.value = [1]
        cloned = deepcopy(custom)
        self.assertEqual(cloned.value, [1])
        self.assertIsNot(cloned.value, custom.value)
        self.assertEqual(CustomFight.reductions, 1)


if __name__ == "__main__":
    unittest.main()
