"""Public catalog invalidation and cache-outage regressions."""
import threading
import unittest
from wakfu_server.shop_cache import PublicCatalogCache


class Redis:
    def __init__(self):
        self.values = {}
        self.reads = 0
        self.writes = 0

    def get(self, key):
        self.reads += 1
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.writes += 1
        self.values[key] = value


class ShopCacheTests(unittest.TestCase):
    def setUp(self):
        self.revision = 1
        self.loads = 0
        self.price = 100
        self.redis = Redis()
        self.now = 1

    def load(self):
        self.loads += 1
        return {
            "articles": [{"id": 1, "price_kamas": self.price}],
            "categories": [{"id": 1}],
        }

    def cache(self, **kwargs):
        return PublicCatalogCache(
            self.load,
            lambda: self.revision,
            redis_client=self.redis,
            clock=lambda: self.now,
            **kwargs
        )

    def test_local_hit_and_second_worker_redis_hit(self):
        first = self.cache()
        self.assertEqual(first.get(), first.get())
        second = self.cache()
        self.assertEqual(second.get()["articles"][0]["price_kamas"], 100)
        self.assertEqual(self.loads, 1)
        self.assertEqual(self.redis.reads, 2)

    def test_revision_change_invalidates_prices_and_categories(self):
        cache = self.cache()
        cache.get()
        self.price = 200
        self.revision += 1
        self.assertEqual(cache.get()["articles"][0]["price_kamas"], 200)
        self.assertEqual(self.loads, 2)

    def test_redis_outage_falls_back_without_repeated_timeouts(self):
        calls = []

        def fail(key):
            calls.append(key)
            raise OSError("offline")

        self.redis.get = fail
        cache = self.cache()
        self.assertEqual(cache.get()["articles"][0]["price_kamas"], 100)
        self.revision += 1
        cache.get()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.loads, 2)

    def test_corrupt_redis_is_replaced(self):
        self.redis.values["wakemu:shop:public:v1:1"] = '{"articles": 1}'
        self.assertEqual(self.cache().get()["articles"][0]["price_kamas"], 100)
        self.assertEqual(self.loads, 1)
        self.assertEqual(self.redis.writes, 1)

    def test_concurrent_miss_loads_only_once(self):
        cache = self.cache()
        threads = [threading.Thread(target=cache.get) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(self.loads, 1)

    def test_revision_failure_does_not_serve_local_cache(self):
        cache = self.cache()
        cache.get()
        self.price = 300

        def fail():
            raise OSError("revision unavailable")

        cache.revision_loader = fail
        self.assertEqual(cache.get()["articles"][0]["price_kamas"], 300)

    def test_mutation_during_load_retries_with_current_revision(self):
        cache = self.cache()

        def changing_load():
            snapshot = self.load()
            if self.loads == 1:
                self.revision += 1
                self.price = 400
            return snapshot

        cache.snapshot_loader = changing_load
        self.assertEqual(cache.get()["articles"][0]["price_kamas"], 400)
        self.assertNotIn("wakemu:shop:public:v1:1", self.redis.values)
        self.assertEqual(self.loads, 2)

    def test_consistent_loader_revision_is_preserved(self):
        cache = self.cache()

        def versioned_load():
            return dict(self.load(), revision=self.revision)

        cache.snapshot_loader = versioned_load
        self.assertEqual(cache.get()["revision"], 1)
        self.assertEqual(self.cache().get()["revision"], 1)

    def test_ttl_expires_local_snapshot(self):
        cache = self.cache(ttl=10)
        cache.get()
        self.now += 11
        cache.get()
        self.assertEqual(self.redis.reads, 2)


if __name__ == "__main__":
    unittest.main()
