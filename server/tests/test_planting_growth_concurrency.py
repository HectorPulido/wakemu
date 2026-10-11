import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Event, Thread
from wakfu_server.planting_runtime import Plantings


class GrowthConcurrencyTests(unittest.TestCase):
    def test_slow_growth_database_does_not_block_movement_cancellation(self):
        entered = Event()
        release = Event()
        cancelled = Event()
        errors = []

        class Store:
            calls = 0
            clock = staticmethod(lambda: 100)
            now = staticmethod(lambda: datetime.now(timezone.utc))

            class Result:
                @staticmethod
                def fetchall():
                    return []

                def __iter__(self):
                    return iter(())

            @contextmanager
            def connection(self):
                self.calls += 1
                if self.calls == 2:
                    entered.set()
                    if not release.wait(2):
                        raise TimeoutError("Test growth was not released")
                yield self

            def execute(self, *args):
                return self.Result()

        plantings = Plantings(Store())
        plantings.publish_growth = lambda *a, **kw: []

        def grow():
            try:
                plantings.mature(None, publish=lambda *a: None)
            except Exception as error:
                errors.append(error)

        growth = Thread(target=grow, daemon=True)
        growth.start()
        if not entered.wait(1):
            release.set()
            growth.join(1)
            self.fail(f"Growth did not reach its slow query: {errors!r}")

        def cancel():
            plantings.cancel(6, "current")
            cancelled.set()

        movement = Thread(target=cancel, daemon=True)
        movement.start()
        completed = cancelled.wait(0.5)
        release.set()
        growth.join(1)
        movement.join(1)
        self.assertTrue(completed, "Movement waited for unrelated growth SQL")
        self.assertEqual(errors, [])
