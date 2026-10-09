import threading
import unittest

from tools.candidate_session_lease import start, stop_all


class CandidateSessionHeartbeatTests(unittest.TestCase):
    def tearDown(self):
        stop_all()

    def test_renews_fixture_lease_without_replacing_generation(self):
        renewed = threading.Event()

        class FakeStore:
            def __init__(self):
                self.calls = []

            def heartbeat(self, account_id, generation, ttl):
                self.calls.append((account_id, generation, ttl))
                renewed.set()
                return True

        store = FakeStore()
        start(store, 41, "same-generation", interval=0.01)

        self.assertTrue(renewed.wait(1))
        stop_all()

        self.assertEqual(store.calls[0], (41, "same-generation", 3600))

    def test_stops_renewing_when_generation_is_stale(self):
        attempted = threading.Event()

        class StaleStore:
            calls = 0

            def heartbeat(self, account_id, generation, ttl):
                self.calls += 1
                attempted.set()
                return False

        store = StaleStore()
        start(store, 42, "replaced-generation", interval=0.01)

        self.assertTrue(attempted.wait(1))
        threading.Event().wait(0.05)
        stop_all()

        self.assertEqual(store.calls, 1)

    def test_retries_transient_store_error_on_same_generation(self):
        renewed = threading.Event()

        class FlakyStore:
            calls = 0

            def heartbeat(self, account_id, generation, ttl):
                self.calls += 1
                if self.calls == 1:
                    raise OSError("temporary database failure")
                renewed.set()
                return True

        store = FlakyStore()
        start(store, 43, "stable-generation", interval=0.01)

        self.assertTrue(renewed.wait(1))
        stop_all()

        self.assertGreaterEqual(store.calls, 2)


if __name__ == "__main__":
    unittest.main()
