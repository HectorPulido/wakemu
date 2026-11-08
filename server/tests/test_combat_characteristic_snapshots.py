"""Private characteristic snapshots preserve legacy reconciliation behavior."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import combat_characteristic_reconciliation as module


def fixture():
    actors = {}
    for identity in (1, 2):
        actor = SimpleNamespace(
            id=identity, hp=20, ap=6, mp=3, max_hp=20, max_ap=6, max_mp=3
        )
        for name in module._MAPS:
            setattr(actor, name, {3: 8, 1: 2})
        actors[identity] = actor
    return SimpleNamespace(id=9, actors=actors)


class SignatureSnapshotTests(unittest.TestCase):
    def exercise(self, private, mutate, configure=lambda fight, trace: None):
        fight, trace = fixture(), []
        configure(fight, trace)
        capture = (
            module._capture_characteristics
            if private
            else module.characteristic_signatures
        )
        before = capture(fight)
        mutate(fight, trace)

        def hidden(state):
            trace.append("visibility")
            return getattr(state, "hidden", set())

        def serialize(actor, state):
            trace.append(("serialize", actor.id))
            return (actor.id, actor.hp, tuple(sorted(actor.effect_stats.items())))

        with patch(
            "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
            hidden,
        ), patch.object(
            module, "actor_state", lambda opcode, fid, aid, data: (fid, aid, data)
        ):
            try:
                result = module.changed_characteristic_packets(fight, before, serialize)
            except Exception as exc:
                result = (type(exc), str(exc))
        return result, trace

    def test_scalar_changes_insertion_order_and_hidden_to_visible(self):
        changes = (
            lambda f, t: None,
            lambda f, t: f.actors[2].effect_stats.update({3: 99}),
            lambda f, t: setattr(f.actors[2], "hp", 19),
            lambda f, t: setattr(f.actors[2], "effect_stats", {1: 2, 3: 8}),
            lambda f, t: setattr(f, "hidden", set()),
            lambda f, t: (
                setattr(f, "hidden", set()),
                f.actors[2].effect_stats.update({1: 7}),
            ),
        )
        for mutate in changes:
            with self.subTest(mutate=mutate):
                configure = lambda f, t: setattr(f, "hidden", {2})
                self.assertEqual(
                    self.exercise(False, mutate, configure),
                    self.exercise(True, mutate, configure),
                )

    def test_custom_maps_equality_and_error_order(self):
        def configure(fight, trace):
            class Value:
                def __eq__(self, other):
                    trace.append("eq")
                    return isinstance(other, Value)

                def __ne__(self, other):
                    raise AssertionError("legacy tuple comparison must use equality")

            class Mapping(dict):
                def items(self):
                    trace.append("items")
                    return super().items()

            fight.actors[1].effect_stats = Mapping({1: Value()})

        def mutate(fight, trace):
            cls = type(fight.actors[1].effect_stats[1])
            fight.actors[1].effect_stats[1] = cls()

        self.assertEqual(
            self.exercise(False, mutate, configure),
            self.exercise(True, mutate, configure),
        )

        def mixed(fight, trace):
            fight.actors[2].effect_stats = {1: 3, "x": 4}

        self.assertEqual(self.exercise(False, mixed), self.exercise(True, mixed))

    def test_detached_snapshot_and_legacy_shape_unchanged(self):
        fight = fixture()
        legacy = module.characteristic_signatures(fight)
        private = module._capture_characteristics(fight)
        self.assertEqual(legacy[1][7][0], ("effect_stats", ((1, 2), (3, 8))))
        fight.actors[1].effect_stats[1] = 90
        self.assertEqual(private[1][7][0][1].values[1], 2)
        self.assertEqual(legacy[1][7][0][1][0], (1, 2))
        self.assertFalse(
            module._same_signature(
                private[1], module._capture_characteristics(fight)[1]
            )
        )

    def test_map_field_suffix_changes_match_tuple_equality(self):
        fight = fixture()
        old_legacy = module.characteristic_signatures(fight)
        old_private = module._capture_characteristics(fight)
        with patch.object(module, "_MAPS", module._MAPS[:-1]):
            new_legacy = module.characteristic_signatures(fight)
            new_private = module._capture_characteristics(fight)
        self.assertNotEqual(old_legacy[1], new_legacy[1])
        self.assertFalse(module._same_signature(old_private[1], new_private[1]))
        self.assertFalse(module._same_signature(new_private[1], old_private[1]))

    def test_integer_guard_identity_and_large_values(self):
        large = 1 << 200
        value = {large: large}
        captured = module._map_snapshot(value)
        self.assertIs(type(captured), module._ScalarMapSnapshot)
        value[large] += 1
        self.assertEqual(captured.values, {large: large})
        for value in ({True: 1}, {1: True}):
            self.assertIs(type(module._map_snapshot(value)), tuple)

        class Meta(type):
            def __eq__(self, other):
                raise AssertionError("type equality must not execute")

        class Integer(int, metaclass=Meta):
            pass

        for value in ({Integer(1): 2}, {1: Integer(2)}):
            self.assertIs(type(module._map_snapshot(value)), tuple)

    def test_no_change_does_not_query_malformed_visibility(self):
        for capture in (
            module.characteristic_signatures,
            module._capture_characteristics,
        ):
            fight = fixture()
            before = capture(fight)
            with patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                side_effect=ValueError("bad receipt"),
            ) as hidden:
                self.assertEqual(
                    module.changed_characteristic_packets(
                        fight, before, lambda *a: b""
                    ),
                    [],
                )
                hidden.assert_not_called()


if __name__ == "__main__":
    unittest.main()
