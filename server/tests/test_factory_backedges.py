"""Factory-owned runtime edges preserve identity and release temporary fights."""
from copy import deepcopy
from collections import Counter
import gc
import unittest
import weakref
from unittest.mock import patch

from wakfu_server.combat_runtime_backrefs import (
    FactoryOwnerReference,
    FactoryMethod,
    FactoryCallback,
)
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_state import Fight


def remaining_cycles(references):
    """Failure-only bounded graph evidence in this already-loaded process."""
    from collections import defaultdict, deque
    import types

    allocations = [
        (index, id(reference()))
        for index, reference in enumerate(references)
        if reference() is not None
    ]
    previous = gc.get_debug()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        gc.collect()
        objects = {id(value): value for value in gc.garbage}
        incoming = defaultdict(list)
        children = defaultdict(list)
        edge_fields = defaultdict(list)
        labels = {}
        for identity, value in objects.items():
            kind = type(value)
            label = kind.__module__ + "." + kind.__qualname__
            if kind is types.FunctionType:
                label += ":" + value.__qualname__
            labels[identity] = label
            names = {}
            if kind is dict:
                names = {
                    id(child): key for key, child in value.items() if type(key) is str
                }
            for child in gc.get_referents(value):
                if id(child) in objects:
                    target = id(child)
                    incoming[target].append(identity)
                    children[identity].append(target)
                    edge_fields[(identity, target)].append(names.get(target, ""))
        results = []
        for index, identity in allocations:
            if identity not in objects:
                results.append({"allocation": index, "live_external_owner": True})
                continue
            reachable, queue = {identity}, deque([identity])
            while queue and len(reachable) < 20000:
                current = queue.popleft()
                for source in incoming.get(current, ()):
                    if source not in reachable:
                        reachable.add(source)
                        queue.append(source)

            # Iterative Kosaraju over the Fight's reverse-reachable subgraph.
            visited, order = set(), []
            for start in reachable:
                if start in visited:
                    continue
                stack = [(start, False)]
                while stack and len(visited) < 20000:
                    current, expanded = stack.pop()
                    if expanded:
                        order.append(current)
                    elif current not in visited:
                        visited.add(current)
                        stack.append((current, True))
                        stack.extend(
                            (node, False)
                            for node in incoming.get(current, ())
                            if node in reachable and node not in visited
                        )
            assigned, components = set(), []
            for start in reversed(order):
                if start in assigned:
                    continue
                component, stack = [], [start]
                assigned.add(start)
                while stack:
                    current = stack.pop()
                    component.append(current)
                    for child in children.get(current, ()):
                        if child in reachable and child not in assigned:
                            assigned.add(child)
                            stack.append(child)
                if len(component) > 1 or any(
                    node in children.get(node, ()) for node in component
                ):
                    components.append(component)

            scc_paths = []
            for component in components:
                origins = set(component)
                todo = deque((node, (node,)) for node in component)
                reached, route = set(origins), None
                while todo and route is None and len(reached) < 20000:
                    current, trail = todo.popleft()
                    if current == identity:
                        route = trail
                        break
                    for child in children.get(current, ()):
                        if child in reachable and child not in reached:
                            reached.add(child)
                            todo.append((child, trail + (child,)))
                if route is not None:
                    scc_paths.append(
                        {
                            "members": [labels.get(node, "?") for node in component],
                            "cycle_to_fight": [labels.get(node, "?") for node in route],
                            "fields_to_fight": [
                                edge_fields.get((source, target), [""])[0]
                                for source, target in zip(route, route[1:])
                            ],
                        }
                    )

            adjacency = [
                {
                    "from_id": source,
                    "from": labels.get(source, "?"),
                    "to_id": target,
                    "to": labels.get(target, "?"),
                    "fields": edge_fields.get((source, target), []),
                }
                for source in reachable
                for target in children.get(source, ())
                if target in reachable
            ]
            results.append(
                {
                    "allocation": index,
                    "reachable_nodes": len(reachable),
                    "scc_paths_to_fight": scc_paths,
                    "graph_truncated": len(reachable) >= 20000,
                    "labels": {str(node): labels.get(node, "?") for node in reachable},
                    "adjacency": adjacency,
                }
            )
        return results
    finally:
        gc.set_debug(previous)
        gc.garbage.clear()


class FactoryBackedgeTests(unittest.TestCase):
    def test_owner_identity_standalone_and_copy_escape(self):
        class Owner:
            def execute(self, value):
                return self, value

        owner = Owner()
        component = NativeAreaEventRuntime(None, owner, definitions={})
        pointer = weakref.ref(owner)
        del owner
        self.assertIs(component.dispatcher, pointer())
        owner = pointer()
        component.dispatcher = FactoryOwnerReference(owner)
        self.assertIs(component.dispatcher, owner)
        owner.component = component
        owner.callback = FactoryMethod(owner.execute)

        def actual_owner(actual, value):
            return actual, value

        owner.copyable = FactoryCallback(actual_owner, FactoryOwnerReference(owner))
        self.assertIs(owner.callback(7)[0], owner)
        clone = deepcopy(owner)
        self.assertIs(clone.component.dispatcher, clone)
        self.assertIs(clone.callback(8)[0], clone)
        self.assertIs(clone.copyable(9)[0], clone)
        from wakfu_server.wakia_bridge.wakfu_ai.context import native_context

        _instance_fields, encode = (
            native_context._instance_fields,
            native_context.encode,
        )

        self.assertIs(_instance_fields(clone.component)["dispatcher"], clone)
        self.assertIs(_instance_fields(clone.callback.owner)["owner"], clone)
        encode(clone.component)
        escaped = deepcopy(component)
        self.assertIsNot(escaped.dispatcher, owner)
        self.assertIs(escaped.dispatcher.component, escaped)
        del escaped, clone
        del owner
        self.assertIsNone(pointer())
        with self.assertRaisesRegex(RuntimeError, "expired"):
            component.dispatcher
        expired_copy = deepcopy(component)
        self.assertIsNone(_instance_fields(expired_copy)["dispatcher"])
        encode(expired_copy)
        with self.assertRaisesRegex(RuntimeError, "expired"):
            expired_copy.dispatcher

    def test_actual_initialized_cast_start_end_release_all_temporary_fights(self):
        from tests.test_native_callback_owner_cycle import CallbackOwnerCycleTests

        CallbackOwnerCycleTests.setUpClass()
        gc.collect()
        enabled = gc.isenabled()
        gc.disable()
        baseline = {id(value) for value in gc.get_objects() if type(value) is Fight}
        try:
            clone, original = CallbackOwnerCycleTests().prepared_private_clone()
            for callback in (clone.turn_start_provider, clone.turn_end_provider):
                result, packets = callback(
                    clone.fight,
                    actor_id=clone.fight.current.id,
                    action_id=clone.action_id + 1,
                )
                self.assertIsInstance(packets, tuple)
                del result, packets
            del callback, clone
            self.assertFalse(
                any(reference() is not None for reference in original.values())
            )
            references = [
                weakref.ref(value)
                for value in gc.get_objects()
                if type(value) is Fight and id(value) not in baseline
            ]
            alive = [
                index
                for index, reference in enumerate(references)
                if reference() is not None
            ]
            details = remaining_cycles(references) if alive else []
            self.assertEqual(
                alive, [], f"Temporary Fights still alive: {alive}; cycles={details}"
            )
        finally:
            if enabled:
                gc.enable()
            gc.collect()
