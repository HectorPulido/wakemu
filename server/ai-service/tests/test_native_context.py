"""Lossless native value graph encoding and untrusted graph validation."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from collections import deque
import base64
import copy
import json
import sys
import unittest
import gc
from types import CellType
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.context.native_context import NativeGraph, encode, encode_bytes, _encode


class DynamicSlots:
    __slots__ = ("__dict__", "slot_value", "_internal")

    def __init__(self):
        self.slot_value = {"deep": [1, 2]}
        self._internal = "preserve-private"
        self.future_runtime_field = {37: "future"}


@dataclass(slots=True)
class SlottedDatum:
    kind: str
    values: tuple


def child_ref(graph, container, key):
    node = container
    assert node["type"] == "dict"
    for encoded_key, encoded_value in node["entries"]:
        actual_key = graph.resolve(encoded_key)
        if actual_key == key:
            return encoded_value
    raise KeyError(key)


class NativeContextTests(unittest.TestCase):
    def test_exact_integer_tuple_fast_path_is_byte_identical_and_keeps_identity(self):
        left = tuple([11, 12, 13])
        right = tuple([11, 12, 13])
        self.assertIsNot(left, right)
        value = {"left": left, "right": right, "alias": left}
        value["cycle"] = value

        cached = encode_bytes(value)
        uncached = _encode(value, serialize_nodes=True, _geometry_cache=False)
        self.assertEqual(cached, uncached)
        self.assertEqual(
            cached,
            json.dumps(encode(value), separators=(",", ":"), allow_nan=False).encode(),
        )
        graph = json.loads(cached)
        root = graph["nodes"][graph["root"]["ref"]]
        refs = {
            key["value"]: val["ref"]
            for key, val in root["entries"]
            if "value" in key and "ref" in val
        }
        self.assertEqual(refs["left"], refs["alias"])
        self.assertNotEqual(refs["left"], refs["right"])
        self.assertEqual(
            graph["nodes"][refs["left"]],
            {"type": "tuple", "items": [{"value": 11}, {"value": 12}, {"value": 13}]},
        )

    def test_tuple_fast_path_falls_back_for_bool_subclass_and_custom_hash(self):
        class TupleSubclass(tuple):
            pass

        class FutureValue:
            def __hash__(self):
                raise AssertionError("Ineligible tuples must not invoke custom hashes")

        future = FutureValue()
        subclass = TupleSubclass((1, 2, 3))
        subclass.future = {"tuple": subclass, "bytes": b"complete future fields"}
        cases = [(1, True, 3), subclass, (1, future, 3)]
        for item in cases:
            with self.subTest(item=item):
                payload = {"tuple": item, "alias": item}
                self.assertEqual(
                    encode_bytes(payload),
                    _encode(payload, serialize_nodes=True, _geometry_cache=False),
                )
        graph = NativeGraph(json.loads(encode_bytes({"tuple": subclass})))
        reference = graph.field(graph.data["root"], "tuple")
        fields = graph.resolve(reference)["fields"]
        self.assertEqual(graph.field(fields["future"], "tuple"), reference)
        self.assertEqual(
            graph.plain(graph.field(fields["future"], "bytes")),
            b"complete future fields",
        )

    def test_full_deque_keeps_capacity_aliases_cycles_and_subclass_fields(self):
        class FutureQueue(deque):
            pass

        queue = FutureQueue([b"first", (1, 2, 3)], maxlen=4)
        queue.future = {"revision": 9, "queue": queue}
        queue.append(queue)
        value = {"outbox": queue, "alias": queue}
        graph = encode(value)
        self.assertEqual(
            encode_bytes(value),
            json.dumps(graph, separators=(",", ":"), allow_nan=False).encode(),
        )
        native = NativeGraph(graph)
        outbox = native.field(native.data["root"], "outbox")
        self.assertEqual(outbox, native.field(native.data["root"], "alias"))
        node = native.resolve(outbox)
        self.assertEqual(node["type"], "deque")
        self.assertEqual(node["maxlen"], 4)
        self.assertEqual(node["items"][-1], outbox)
        plain = NativeGraph(encode(deque([1, 2], maxlen=3)))
        self.assertEqual(plain.plain(plain.data["root"]).maxlen, 3)
        malformed = copy.deepcopy(graph)
        malformed["nodes"][outbox["ref"]]["maxlen"] = -1
        with self.assertRaises(ValueError):
            NativeGraph(malformed)

    def test_direct_json_preserves_identical_full_graph_types_fields_and_cycles(self):
        class FutureList(list):
            __slots__ = ("__private", "__dict__")

            def __init__(self):
                super().__init__([1, (2, 3, 4)])
                self.__private = b"all-private-fields"
                self.future = {"parent": self}

        shared = FutureList()
        value = dict(
            left=shared,
            right=shared,
            datum=SlottedDatum("full", (1, 2)),
            bytes=bytearray(b"raw"),
            view=memoryview(b"view"),
            date=date(2026, 10, 7),
            time=datetime(2026, 10, 7, tzinfo=timezone.utc),
            decimal=Decimal("1.25"),
            cells=frozenset({(1, 2, 3), (4, 5, 6)}),
        )
        value["self"] = value
        expected = encode(value)
        actual = encode_bytes(value)
        self.assertEqual(
            actual,
            json.dumps(expected, separators=(",", ":"), allow_nan=False).encode(),
        )
        NativeGraph(json.loads(actual))

    def test_completed_snapshot_does_not_retain_nodes_in_recursive_closure(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            value = {"all": [(i, i + 1, 0) for i in range(1000)]}
            value["self"] = value
            graph = encode(value)
            self.assertFalse(
                any(
                    isinstance(referrer, CellType)
                    for referrer in gc.get_referrers(graph["nodes"])
                )
            )
            NativeGraph(graph)
        finally:
            if enabled:
                gc.enable()

    def test_dynamic_dataclass_and_inherited_slot_fields_are_preserved(self):
        class SlottedBase:
            __slots__ = ("base_slot",)

        class FutureState(SlottedBase):
            __slots__ = ("child_slot",)

            def __init__(self):
                self.base_slot = "base"
                self.child_slot = 9

        future = FutureState()
        dynamic = DynamicSlots()
        data = {
            "future": future,
            "dynamic": dynamic,
            "dataclass": SlottedDatum("combat", (3, 4)),
        }
        graph = NativeGraph(encode(data))
        root = graph.root
        future_node = graph.resolve(child_ref(graph, root, "future"))
        dynamic_node = graph.resolve(child_ref(graph, root, "dynamic"))
        datum_node = graph.resolve(child_ref(graph, root, "dataclass"))
        self.assertEqual(future_node["type"], "object")
        self.assertEqual(set(future_node["fields"]), {"base_slot", "child_slot"})
        self.assertEqual(
            set(dynamic_node["fields"]),
            {"slot_value", "_internal", "future_runtime_field"},
        )
        self.assertEqual(set(datum_node["fields"]), {"kind", "values"})
        self.assertEqual(
            graph.resolve(dynamic_node["fields"]["future_runtime_field"])["type"],
            "dict",
        )

    def test_aliases_cycles_integer_keys_and_json_round_trip_shape(self):
        shared = {7: "integer key", "bytes": b"raw"}
        root_value = {"left": shared, "right": shared}
        cycle = [root_value]
        root_value["cycle"] = cycle
        encoded = encode(root_value)
        self.assertEqual(encoded["encoding"], "wakfu-native-graph-1")
        # The format is directly transportable as JSON and references retain
        # shared identity and the back-edge rather than duplicating/truncating.
        graph = NativeGraph(json.loads(json.dumps(encoded)))
        root = graph.root
        left_ref = child_ref(graph, root, "left")
        right_ref = child_ref(graph, root, "right")
        self.assertEqual(left_ref, right_ref)
        left = graph.resolve(left_ref)
        int_key = child_ref(graph, left, 7)
        self.assertEqual(graph.resolve(int_key), "integer key")
        cycle_node = graph.resolve(child_ref(graph, root, "cycle"))
        self.assertEqual(graph.resolve(cycle_node["items"][0]), root)

    def test_bytes_datetime_decimal_sets_and_immutable_terrain_keep_type_tags(self):
        class ImmutableTerrainSet(frozenset):
            pass

        payload = {
            "bytes": b"\x00\xffraw",
            "bytearray": bytearray(b"mutable"),
            "memoryview": memoryview(b"view"),
            "date": date(2025, 2, 3),
            "datetime": datetime(2025, 2, 3, 4, 5, 6, 7, tzinfo=timezone.utc, fold=1),
            "decimal": Decimal("1234567890.00100"),
            "set": {4, 1, 9},
            "frozen": frozenset({"west", "east"}),
            "terrain": ImmutableTerrainSet({(0, 0, 0), (1, 0, 0)}),
        }
        encoded = encode(payload)
        graph = NativeGraph(json.loads(json.dumps(encoded)))
        self.assertEqual(encoded["encoding"], "wakfu-native-graph-1")
        tags = {node["type"] for node in graph.nodes}
        self.assertTrue(
            {
                "bytes",
                "bytearray",
                "memoryview",
                "date",
                "datetime",
                "decimal",
                "set",
                "frozenset",
            }.issubset(tags)
        )
        terrain_node = next(
            node
            for node in graph.nodes
            if node.get("nativeClass", {})
            .get("name", "")
            .endswith("ImmutableTerrainSet")
        )
        self.assertEqual(terrain_node["type"], "frozenset")
        self.assertTrue(
            terrain_node["nativeClass"]["name"].endswith("ImmutableTerrainSet")
        )
        datetime_node = graph.resolve(child_ref(graph, graph.root, "datetime"))
        self.assertEqual(datetime_node["fold"], 1)
        decimal_node = graph.resolve(child_ref(graph, graph.root, "decimal"))
        self.assertEqual(decimal_node["value"], "1234567890.00100")
        byte_node = graph.resolve(child_ref(graph, graph.root, "bytes"))
        self.assertEqual(base64.b64decode(byte_node["value"]), b"\x00\xffraw")
        self.assertEqual(encode(payload), encode(payload))

    def test_container_subclasses_keep_native_class_and_extra_private_slots(self):
        class FutureList(list):
            __slots__ = ("__dict__", "__future_slot")

            def __init__(self, values):
                super().__init__(values)
                self.__future_slot = {"version": 8}
                self.dynamic_extension = b"capture"

        class FutureDict(dict):
            pass

        values = FutureList(["known", 7])
        mapping = FutureDict({"x": 1})
        mapping.future_field = [2, 3]
        graph = NativeGraph(encode({"list": values, "dict": mapping}))
        root = graph.root
        list_node = graph.resolve(child_ref(graph, root, "list"))
        dict_node = graph.resolve(child_ref(graph, root, "dict"))
        self.assertEqual(list_node["type"], "list")
        self.assertEqual(
            list_node["nativeClass"]["name"],
            "NativeContextTests.test_container_subclasses_keep_native_class_and_extra_private_slots.<locals>.FutureList",
        )
        self.assertEqual(
            set(list_node["fields"]), {"_FutureList__future_slot", "dynamic_extension"}
        )
        self.assertEqual(dict_node["type"], "dict")
        self.assertEqual(
            dict_node["nativeClass"]["name"],
            "NativeContextTests.test_container_subclasses_keep_native_class_and_extra_private_slots.<locals>.FutureDict",
        )
        self.assertEqual(set(dict_node["fields"]), {"future_field"})

    def test_callable_instances_are_objects_with_fields_and_mixed_set_cycles_survive(
        self,
    ):
        class CallableNative:
            __slots__ = ("__private_value", "__dict__")

            def __init__(self):
                self.__private_value = "kept"
                self.future_flag = True
                self.calls = 0

            def __call__(self):
                self.calls += 1

        class CycleNode:
            __slots__ = ("contents",)

            def __hash__(self):
                return id(self)

        callable_value = CallableNative()
        cycle_node = CycleNode()
        mixed = {1, "one", cycle_node}
        cycle_node.contents = mixed
        graph = NativeGraph(encode({"callable": callable_value, "mixed": mixed}))
        root = graph.root
        callable_node = graph.resolve(child_ref(graph, root, "callable"))
        self.assertEqual(callable_node["type"], "object")
        self.assertEqual(
            set(callable_node["fields"]),
            {"_CallableNative__private_value", "future_flag", "calls"},
        )
        self.assertEqual(callable_value.calls, 0)
        mixed_node = graph.resolve(child_ref(graph, root, "mixed"))
        self.assertEqual(mixed_node["type"], "set")
        self.assertEqual(len(mixed_node["items"]), 3)
        object_node = next(
            graph.resolve(item)
            for item in mixed_node["items"]
            if isinstance(graph.resolve(item), dict)
            and graph.resolve(item).get("type") == "object"
        )
        self.assertEqual(graph.resolve(object_node["fields"]["contents"]), mixed_node)

    def test_callable_is_only_a_descriptor_and_is_never_invoked(self):
        calls = []

        def forbidden():
            calls.append("ran")

        encoded = encode({"callback": forbidden})
        graph = NativeGraph(encoded)
        descriptor = graph.resolve(child_ref(graph, graph.root, "callback"))
        self.assertEqual(descriptor["type"], "callable")
        self.assertEqual(
            descriptor["name"],
            "NativeContextTests.test_callable_is_only_a_descriptor_and_is_never_invoked.<locals>.forbidden",
        )
        self.assertEqual(calls, [])

    def test_malformed_references_nodes_scalars_and_encoding_are_rejected(self):
        valid = encode({"x": [1]})
        variants = []
        for reference in (
            {},
            {"unknown": 0},
            {"ref": True},
            {"ref": 0.0},
            {"ref": -1},
            {"value": []},
            {"value": {}},
            {"value": 0, "ref": 0},
            {"value": 0, "extra": 0},
            {"ref": 0, "extra": 0},
        ):
            bad = copy.deepcopy(valid)
            bad["root"] = reference
            variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["encoding"] = "unknown"
        variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["root"] = {"ref": 999}
        variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["nodes"][0] = {"type": "wat"}
        variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["nodes"][0]["items"] = [{"ref": -1}]
        variants.append(bad)
        bad = {
            "encoding": "wakfu-native-graph-1",
            "root": {"value": float("nan")},
            "nodes": [],
        }
        variants.append(bad)
        bad = {
            "encoding": "wakfu-native-graph-1",
            "root": {"ref": 0},
            "nodes": [{"type": "bytes", "value": "%%%"}],
        }
        variants.append(bad)
        bad = {
            "encoding": "wakfu-native-graph-1",
            "root": {"ref": 0},
            "nodes": [{"type": "object", "module": 1, "name": "X", "fields": {}}],
        }
        variants.append(bad)
        for malformed in variants:
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                NativeGraph(malformed)

    def test_nonfinite_and_unsupported_native_objects_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Non-finite native context value"):
            encode(float("inf"))
        with self.assertRaisesRegex(ValueError, "Non-finite native decimal"):
            encode(Decimal("NaN"))

        class EmptyNative:
            __slots__ = ()

        with self.assertRaisesRegex(ValueError, "Unsupported native context type"):
            encode(EmptyNative())

    def test_future_coordinator_lock_keeps_identity_and_explicit_local_authority(self):
        from threading import Lock
        from wakfu_ai.context.native_fingerprint import fingerprint

        lock = Lock()
        source = {"future_dispatch_lock": lock, "same_lock": lock}
        graph = NativeGraph(encode(source))
        root = graph.resolve(graph.data["root"])
        values = {graph.plain(key): value for key, value in root["entries"]}
        self.assertEqual(values["future_dispatch_lock"], values["same_lock"])
        node = graph.resolve(values["future_dispatch_lock"])
        self.assertFalse(graph.plain(node["fields"]["transferable"]))
        self.assertFalse(graph.plain(node["fields"]["locked"]))
        before = fingerprint(source)
        with lock:
            self.assertNotEqual(before, fingerprint(source))
            held = NativeGraph(encode(source))
            held_root = held.resolve(held.data["root"])
            reference = held_root["entries"][0][1]
            self.assertTrue(held.plain(held.resolve(reference)["fields"]["locked"]))


if __name__ == "__main__":
    unittest.main()
