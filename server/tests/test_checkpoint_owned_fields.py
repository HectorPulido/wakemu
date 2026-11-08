"""Detached checkpoint payloads must not copy retained ownership backreferences."""
from copy import deepcopy
import gc
import json
from threading import RLock
from types import SimpleNamespace
import unittest
import weakref

from wakfu_server.checkpoint_worker import (
    detach,
    serialize_detached,
    _checkpoint_fields,
)
from wakfu_server.combat_retained_collections import RetainedCollections, OwnedMap


class CheckpointOwnedFieldsTests(unittest.TestCase):
    def test_payload_closure_releases_copies_after_return_and_error(self):
        previous_gc = gc.isenabled()
        gc.disable()
        try:
            copied_refs = []

            class Payload:
                def __deepcopy__(self, memo):
                    copied = Payload()
                    memo[id(self)] = copied
                    copied_refs.append(weakref.ref(copied))
                    return copied

            class Failure:
                def __deepcopy__(self, memo):
                    raise RuntimeError("expected checkpoint copy failure")

            source = {"payload": Payload()}
            copied = _checkpoint_fields(source)
            self.assertIn("payload", copied)
            del copied, source
            self.assertIsNone(
                copied_refs[-1](), "normal return must release the copied payload"
            )

            source = {"payload": Payload(), "failure": Failure()}
            with self.assertRaisesRegex(
                RuntimeError, "expected checkpoint copy failure"
            ):
                _checkpoint_fields(source)
            del source
            self.assertIsNone(
                copied_refs[-1](), "exception must release partial copied payloads"
            )

            shared = [1, {"value": 2}]
            cycle_list = []
            cycle_tuple = (cycle_list,)
            cycle_list.append(cycle_tuple)
            graph = {"first": shared, "second": shared, "cycle": cycle_tuple}
            detached = _checkpoint_fields(graph)
            self.assertIs(detached["first"], detached["second"])
            self.assertIsNot(detached["first"], shared)
            self.assertIs(detached["cycle"][0][0], detached["cycle"])
        finally:
            if previous_gc:
                gc.enable()

    def test_detach_plain_owned_payload_preserves_aliases_without_recapturing_actors(
        self,
    ):
        actor_payload_copies = []

        class Payload:
            def __deepcopy__(self, memo):
                actor_payload_copies.append(1)
                return {"copied": True}

        class Actor:
            def __init__(self):
                self.id, self.hp, self.payload = 7, 100, Payload()

            def __deepcopy__(self, memo):
                raise AssertionError("checkpoint fields traversed owner actors")

        owner = RetainedCollections()
        row = owner.records.install_owned(11, dict(uid=11, manager_id=7, target_id=7))
        owner.order.append(11)
        payload = {"values": [1, 2]}
        owner.sources["owned_stat_effects"][11] = payload
        owner.actors[7] = Actor()
        fight = SimpleNamespace(
            id=77,
            actors=owner.actors,
            native_retained_records=owner.records,
            native_retained_order=owner.order,
            owned_stat_effects=owner.sources["owned_stat_effects"],
            row_alias=row,
            payload_alias=payload,
        )
        live_runtime = SimpleNamespace(
            fight=fight,
            action_id=4,
            native_action_id=8,
            awaiting_ack=None,
            round=2,
            duration=30,
        )
        shared = SimpleNamespace(
            fight=fight, runtime=live_runtime, checkpoint_revision=12, lock=RLock()
        )
        frozen, runtime, revision = detach(shared)
        self.assertEqual(12, revision)
        self.assertEqual([1], actor_payload_copies)
        self.assertIs(runtime.fight, frozen)
        self.assertIs(type(frozen.native_retained_records), dict)
        self.assertIs(type(frozen.native_retained_records[11]), dict)
        self.assertIs(type(frozen.native_retained_order), list)
        self.assertIs(type(frozen.owned_stat_effects), dict)
        self.assertIs(frozen.row_alias, frozen.native_retained_records[11])
        self.assertIs(frozen.payload_alias, frozen.owned_stat_effects[11])
        self.assertIsNot(frozen.payload_alias, payload)
        state = serialize_detached(frozen, runtime=runtime)
        self.assertEqual(
            {"11": dict(uid=11, manager_id=7, target_id=7)},
            state["native_retained_records"],
        )
        self.assertEqual(
            dict(id=7, hp=100, payload={"copied": True}), state["actors"]["7"]
        )
        encoded = json.dumps(state, allow_nan=False)
        row["target_id"] = 99
        payload["values"].append(3)
        owner.actors[7].hp = 0
        self.assertEqual(
            encoded,
            json.dumps(serialize_detached(frozen, runtime=runtime), allow_nan=False),
        )

    def test_opaque_mapping_and_owned_subclass_keep_original_copy_protocol(self):
        calls = []

        class CustomMap(dict):
            def __deepcopy__(self, memo):
                calls.append("custom")
                result = type(self)()
                memo[id(self)] = result
                for key, value in dict.items(self):
                    result[deepcopy(key, memo)] = deepcopy(value, memo)
                return result

        class CustomOwnedMap(OwnedMap):
            def __deepcopy__(self, memo):
                calls.append("owned-subclass")
                return {"opaque": True}

        class PretendBuiltin(type):
            __hash__ = type.__hash__

            def __eq__(cls, other):
                raise AssertionError("opaque type equality must not be consulted")

        class OpaqueMap(dict, metaclass=PretendBuiltin):
            def __deepcopy__(self, memo):
                calls.append("opaque-metaclass")
                return {"custom_copy": True}

        opaque = _checkpoint_fields(OpaqueMap(value=1))
        self.assertEqual({"custom_copy": True}, opaque)
        self.assertEqual(["opaque-metaclass"], calls)
        calls.clear()

        custom = CustomMap(payload=[1, 2])
        copied = _checkpoint_fields(
            dict(a=custom, b=custom, subclass=CustomOwnedMap(object(), "records"))
        )
        self.assertEqual(["custom", "owned-subclass"], calls)
        self.assertIs(type(copied["a"]), CustomMap)
        self.assertIs(copied["a"], copied["b"])
        self.assertIsNot(copied["a"]["payload"], custom["payload"])
        self.assertEqual({"opaque": True}, copied["subclass"])

    def test_plain_container_alias_and_tuple_cycle_match_deepcopy(self):
        child = []
        graph = (child,)
        child.append(graph)
        copied = _checkpoint_fields(graph)
        self.assertIs(copied[0][0], copied)
        self.assertIsNot(copied[0], child)
        payload = {"nested": [1, {"value": 2}]}
        source = {"one": payload, "two": payload}
        copied = _checkpoint_fields(source)
        self.assertEqual(deepcopy(source), copied)
        self.assertIs(copied["one"], copied["two"])


if __name__ == "__main__":
    unittest.main()
