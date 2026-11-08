"""Checkpoint containers preserve native records, traversal and errors."""
import hashlib
import json
from types import SimpleNamespace
import unittest

from wakfu_server import fight_checkpoint_store as checkpoints
from wakfu_server.characters.owned_social_context import OwnedSocialContext
from wakfu_server.combat_carrying import NativeCarryPair
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_instance_level_group import InstanceDifficultySnapshot
from wakfu_server.combat_state_ledger import StateLedger, RunningState


class CheckpointPlainContainerTests(unittest.TestCase):
    def test_typed_snapshot_has_exact_fields_and_roundtrips(self):
        ledger = StateLedger(7)
        state = RunningState(
            91, 6807, 1, 7, 7, -1, "target", False, (123,), 0, True, None
        )
        ledger._entries = (state,)
        social = OwnedSocialContext(7, 9, 30, None, 0, "plain-container-test")
        book = CopyBookAction((7 << 32) | 6266, 6266, 20, False, True, False)
        carry = NativeCarryPair(7, 8, (2, 3, 0), 1, 2, 19, 144)
        instance = InstanceDifficultySnapshot(7, None, "fBg.drG.Optional.empty")
        graph = dict(
            social=social,
            book=book,
            carry=carry,
            instance=instance,
            ledger=ledger,
            nested=({2: [True, None]}, {3, 1}, frozenset({4, 2})),
        )
        fight = SimpleNamespace(actors={7: SimpleNamespace(id=7)}, typed=graph)
        social_expected = dict(
            actor_id=7,
            account_id=9,
            nation_id=30,
            guild_id=None,
            guild_level=0,
            source_revision="plain-container-test",
            source="owned-social-components-mvcc-v1",
            policy="wakemu-fight-admission-social-snapshot-v1",
        )

        def digest(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

        social_expected["source_sha256"] = digest(social_expected)
        social_expected["sha256"] = digest(social_expected)
        expected = dict(
            actors={"7": {"id": 7}},
            typed=dict(
                social=social_expected,
                book=dict(
                    uid=(7 << 32) | 6266,
                    reference=6266,
                    level=20,
                    special=False,
                    elemental=True,
                    neutral=False,
                ),
                carry=dict(
                    carrier_id=7,
                    carried_id=8,
                    position=[2, 3, 0],
                    carried_direction=1,
                    carrier_direction=2,
                    source_uid=19,
                    source_reference=144,
                ),
                instance=dict(
                    actor_id=7, difficulty=None, source="fBg.drG.Optional.empty"
                ),
                ledger=dict(
                    actor_id=7,
                    entries=[
                        dict(
                            uid=91,
                            reference=6807,
                            level=1,
                            caster_id=7,
                            target_id=7,
                            duration=-1,
                            clock_actor="target",
                            tick_at_turn_end=False,
                            effect_ids=[123],
                            realtime_duration=0,
                            retained=True,
                            timer=None,
                            protected=None,
                            realtime_deadline_ms=None,
                            realtime_in_combat=None,
                        )
                    ],
                ),
                nested=[{"2": [True, None]}, [1, 3], [2, 4]],
            ),
        )
        actual = checkpoints.snapshot(fight)
        self.assertEqual(actual, expected)
        decoded = json.loads(json.dumps(actual))["typed"]
        self.assertEqual(OwnedSocialContext.from_record(decoded["social"]), social)
        self.assertEqual(CopyBookAction(**decoded["book"]), book)
        self.assertEqual(InstanceDifficultySnapshot(**decoded["instance"]), instance)
        decoded["carry"]["position"] = tuple(decoded["carry"]["position"])
        self.assertEqual(NativeCarryPair(**decoded["carry"]), carry)
        decoded["ledger"]["entries"][0]["effect_ids"] = (123,)
        self.assertEqual(RunningState(**decoded["ledger"]["entries"][0]), state)
        self.assertEqual(ledger.entries, (state,))
        self.assertIs(fight.typed["ledger"], ledger)

    def test_subclass_traversal_and_rejection_order_are_preserved(self):
        observed = []

        class CustomDict(dict):
            def items(self):
                observed.append("dict.items")
                return reversed(tuple(super().items()))

        class CustomList(list):
            def __iter__(self):
                observed.append("list.iter")
                return super().__iter__()

        class Key:
            def __str__(self):
                observed.append("key.str")
                return "key"

        class Scalar(int):
            pass

        result = checkpoints._plain(CustomDict([(3, CustomList([1, 2])), (1, (4,))]))
        self.assertEqual(result, {"1": [4], "3": [1, 2]})
        self.assertEqual(list(result), ["1", "3"])
        self.assertEqual(observed, ["dict.items", "list.iter"])
        observed.clear()
        with self.assertRaisesRegex(
            ValueError, "^Fight contains nonserializable state$"
        ):
            checkpoints._plain({Key(): object()})
        self.assertEqual(observed, ["key.str"])
        with self.assertRaisesRegex(
            ValueError, "^Fight contains nonserializable state$"
        ):
            checkpoints._plain([Scalar(1), CustomList([2])])
        self.assertEqual(observed, ["key.str"])
        with self.assertRaises(TypeError):
            checkpoints._plain({1, "mixed"})
        with self.assertRaisesRegex(
            ValueError, "^Invalid native character-copy book action$"
        ):
            checkpoints._plain(CopyBookAction(1, 2, 20, False, "invalid", False))


if __name__ == "__main__":
    unittest.main()
