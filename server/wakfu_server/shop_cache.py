"""Optional, revision-bound caching of public shop catalog data only."""
import json
import logging
import os
import threading
import time

LOG = logging.getLogger(__name__)


def redis_from_environment():
    """Keep a missing or unavailable Redis service outside the purchase path."""
    url = os.environ.get("WAKFU_REDIS_URL")
    if not url:
        return None
    try:
        import redis

        return redis.Redis.from_url(
            url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            retry_on_timeout=False,
        )
    except (ImportError, ValueError):
        LOG.warning("Shop catalog Redis configuration unavailable")
        return None


class PublicCatalogCache:
    """Cache articles/categories, never authentication, balances or purchases.

    ``revision_loader`` must read an authoritative database revision changed by
    every article/category mutation, including direct SQL. ``snapshot_loader``
    returns {"articles": [...], "categories": [...]} with an optional integer
    "revision" from its consistent database snapshot. Callers treat the returned
    snapshot as read-only. Revision checks bracket a cache miss so a concurrent
    catalog update cannot publish a mixed snapshot under an older revision.
    """

    def __init__(
        self,
        snapshot_loader,
        revision_loader,
        *,
        redis_client=None,
        namespace="wakemu:shop:public:v1",
        ttl=300,
        clock=time.monotonic,
    ):
        self.snapshot_loader = snapshot_loader
        self.revision_loader = revision_loader
        self.redis = redis_client
        self.namespace = namespace
        self.ttl = max(1, min(int(ttl), 3600))
        self.clock = clock
        self._lock = threading.Lock()
        self._revision = None
        self._snapshot = None
        self._expires = 0
        self._redis_retry = 0

    @staticmethod
    def _valid(snapshot):
        return (
            isinstance(snapshot, dict)
            and set(snapshot)
            in ({"articles", "categories"}, {"articles", "categories", "revision"})
            and all(
                isinstance(snapshot[key], list)
                and all(isinstance(row, dict) for row in snapshot[key])
                for key in ("articles", "categories")
            )
        )

    def _redis_call(self, method, *args):
        if self.redis is None or self.clock() < self._redis_retry:
            return None
        try:
            return getattr(self.redis, method)(*args)
        except Exception as error:
            # Cache failure must not make the public store unavailable. Avoid
            # repeating a connection timeout on every request during an outage.
            self._redis_retry = self.clock() + 5
            LOG.warning("Shop catalog Redis unavailable: %s", type(error).__name__)
            return None

    def get(self):
        with self._lock:
            try:
                revision = str(self.revision_loader())
            except Exception:
                # Do not serve potentially stale enabled flags or prices when
                # the authoritative revision cannot be checked.
                return self.snapshot_loader()
            now = self.clock()
            if (
                self._revision == revision
                and self._snapshot is not None
                and now < self._expires
            ):
                return self._snapshot
            key = f"{self.namespace}:{revision}"
            raw = self._redis_call("get", key)
            if raw:
                try:
                    snapshot = json.loads(raw)
                    if self._valid(snapshot) and (
                        "revision" not in snapshot
                        or str(snapshot["revision"]) == revision
                    ):
                        self._remember(revision, snapshot)
                        return snapshot
                except (ValueError, TypeError, UnicodeError):
                    pass
            # A second check prevents concurrent direct SQL edits from placing
            # new rows under an old revision. One retry bounds load under churn.
            for _ in range(2):
                snapshot = self.snapshot_loader()
                if not self._valid(snapshot):
                    raise ValueError("Invalid public shop catalog snapshot")
                try:
                    after = str(self.revision_loader())
                except Exception:
                    return snapshot
                if after == revision and (
                    "revision" not in snapshot or str(snapshot["revision"]) == revision
                ):
                    key = f"{self.namespace}:{revision}"
                    self._redis_call(
                        "setex",
                        key,
                        self.ttl,
                        json.dumps(snapshot, separators=(",", ":")),
                    )
                    self._remember(revision, snapshot)
                    return snapshot
                revision = after
            return snapshot

    def _remember(self, revision, snapshot):
        self._revision = revision
        self._snapshot = snapshot
        self._expires = self.clock() + self.ttl
