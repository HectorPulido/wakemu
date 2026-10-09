import unittest
from contextlib import contextmanager
from threading import Event, Thread
from wakfu_server.combat_group_store import PersistentGroups


class SnapshotConcurrencyTests(unittest.TestCase):
    def test_readers_do_not_wait_for_global_publication_lock_and_detach_members(self):
        row = {
            "map_id": 1,
            "instance_id": 0,
            "group_id": 7,
            "status": "available",
            "members": [{"id": -7, "hp": 10}],
        }

        class Store:
            @contextmanager
            def connection(self):
                yield self

            def execute(self, *args):
                return [row]

        groups = PersistentGroups(Store())
        for method in (lambda: groups.snapshot(1, 0), lambda: groups.available(1, 0)):
            with self.subTest(method=method):
                done = Event()
                results = []
                failures = []

                def read():
                    try:
                        results.extend(method())
                    except Exception as error:
                        failures.append(error)
                    finally:
                        done.set()

                with groups.lock:
                    thread = Thread(target=read, daemon=True)
                    thread.start()
                    completed = done.wait(1)
                thread.join(1)
                self.assertTrue(completed, "Read blocked behind unrelated publication")
                self.assertEqual(failures, [])
                results[0]["members"][0]["hp"] = 0
                self.assertEqual(row["members"][0]["hp"], 10)
