"""Owner edges follow native metadata gateways without scanning other managers."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    TrackedRow,
    replace_collection,
    _rebuild,
)


class OwnedChildrenIndexTests(unittest.TestCase):
    def test_order_mutation_replacement_clone_and_opaque_reentrancy(self):
        owner = RetainedCollections()

        def install(uid, parent, manager=7):
            row = owner.records.install_owned(
                uid, dict(uid=uid, manager_id=manager, owner_uid=parent)
            )
            if uid not in owner.order:
                owner.order.append(uid)
            return row

        first = install(30, 9)
        install(20, 9, -7)  # Cross-manager edge; never restrict to parent manager.
        install(10, None)
        owner._refresh_order()
        self.assertEqual(owner.owned_children(9), (30, 20))
        owner.order[:] = [20, 10, 30]
        self.assertIsNone(owner.owned_children(9))
        owner._refresh_order()
        self.assertEqual(owner.owned_children(9), (20, 30))
        first["owner_uid"] = 10
        self.assertEqual(owner.owned_children(9), (20,))
        self.assertEqual(owner.owned_children(10), (30,))
        replacement = install(30, 9)
        first["owner_uid"] = 888  # Detached alias cannot rehome its replacement.
        self.assertEqual(owner.owned_children(888), ())
        self.assertEqual(owner.owned_children(9), (20, 30))
        cloned, old_alias = deepcopy((owner, first))
        cloned._refresh_order()
        self.assertEqual(cloned.owned_children(9), (20, 30))
        old_alias["owner_uid"] = 999
        self.assertEqual(cloned.owned_children(999), ())
        cloned.records[30]["owner_uid"] = 10
        self.assertEqual(owner.owned_children(9), (20, 30))
        self.assertEqual(cloned.owned_children(9), (20,))
        _rebuild(cloned)  # Exact explicit restore boundary rebuilds derived edges.
        self.assertEqual(cloned.owned_children(9), (20,))
        self.assertEqual(cloned.owned_children(10), (30,))
        target = SimpleNamespace(native_retained_records=owner.records)
        replace_collection(
            target, "native_retained_records", {30: replacement, 10: owner.records[10]}
        )
        owner.order.remove(20)
        owner._refresh_order()
        self.assertEqual(owner.owned_children(9), (30,))
        calls = []
        replacement.get = lambda *args: calls.append(args)
        self.assertIsNone(owner.owned_children(9))
        self.assertEqual(calls, [])
        del replacement.get
        self.assertEqual(owner.owned_children(9), (30,))

        def changing():
            self.assertIsNone(owner.owned_children(9))
            yield ("owner_uid", 10)

        replacement.update(changing())
        self.assertEqual(owner.owned_children(9), ())
        self.assertEqual(owner.owned_children(10), (30,))
        replacement["owner_uid"] = True
        self.assertIsNone(owner.owned_children(10))
        replacement["owner_uid"] = 9
        self.assertEqual(owner.owned_children(9), (30,))
        with patch.object(
            TrackedRow, "get", lambda *args: self.fail("opaque reader called")
        ):
            self.assertIsNone(owner.owned_children(9))
        replacement.owner = None
        self.assertIsNone(owner.owned_children(9))
        replacement.owner = owner
        replacement["owner_uid"] = 9
        self.assertEqual(owner.owned_children(9), (30,))
        del owner.records[30]
        owner.order.remove(30)
        owner._refresh_order()
        self.assertEqual(owner.owned_children(9), ())
        replacement["owner_uid"] = 9
        self.assertEqual(owner.owned_children(9), ())


if __name__ == "__main__":
    unittest.main()
