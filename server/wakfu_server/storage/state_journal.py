"""Redis CAS write-ahead state snapshots with exact SQLite baselines.

Domain adapters validate ownership and payloads. Redis acknowledgments preserve
newer mutations when SQLite has only committed an earlier revision.
"""
import json
import uuid

_PUT = """local old=redis.call('HGET',KEYS[1],ARGV[1]);
if (ARGV[2]=='' and old) or (ARGV[2]~='' and old~=ARGV[2]) then return 0 end;
redis.call('HSET',KEYS[1],ARGV[1],ARGV[3]); return 1"""


class StateJournalError(ValueError):
    pass


class StateJournal:
    def __init__(self, client, namespace):
        self.client = client
        self.namespace = namespace
        self._call("ping")  # Configured Redis never silently falls back to SQLite.

    def _call(self, method, *args):
        try:
            return getattr(self.client, method)(*args)
        except Exception as error:
            raise StateJournalError("Redis state journal unavailable") from error

    @staticmethod
    def field(key):
        return json.dumps(list(key), separators=(",", ":"))

    @staticmethod
    def encode(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def read(self, key):
        encoded = self._call("hget", self.namespace, self.field(key))
        if encoded is None:
            return None, None
        if isinstance(encoded, bytes):
            encoded = encoded.decode()
        try:
            value = json.loads(encoded)
            if (
                value["version"] != 1
                or value["key"] != list(key)
                or not isinstance(value["revision"], str)
            ):
                raise ValueError()
            if "baseline" not in value or "current" not in value:
                raise ValueError()
        except (ValueError, KeyError, TypeError) as error:
            raise StateJournalError("Invalid Redis state record") from error
        return value, encoded

    def put(self, key, current, *, expected=None, baseline=None):
        previous = None if expected is None else json.loads(expected)
        value = dict(
            version=1,
            key=list(key),
            revision=uuid.uuid4().hex,
            baseline=baseline if previous is None else previous["baseline"],
            current=current,
        )
        encoded = self.encode(value)
        if (
            self._call(
                "eval",
                _PUT,
                1,
                self.namespace,
                self.field(key),
                expected or "",
                encoded,
            )
            != 1
        ):
            raise StateJournalError("Redis state revision conflict")
        return value, encoded

    def records(self):
        # Read individual fields again to avoid using an outdated SCAN value.
        rows = self._call("hkeys", self.namespace)
        for field in rows:
            try:
                key = tuple(json.loads(field))
            except (ValueError, TypeError) as error:
                raise StateJournalError("Invalid Redis state key") from error
            value, encoded = self.read(key)
            if value is not None:
                yield key, value, encoded

    def checkpoint(self, key, committed_encoded):
        """Advance baseline after SQL commit, preserving any newer current state."""
        committed = json.loads(committed_encoded)
        for _ in range(8):
            latest, encoded = self.read(key)
            if latest is None:
                raise StateJournalError("Redis state disappeared after SQLite commit")
            if latest["baseline"] == committed["current"]:
                return True
            if latest["baseline"] != committed["baseline"]:
                raise StateJournalError("Redis baseline changed after SQLite commit")
            updated = dict(
                latest, baseline=committed["current"], revision=uuid.uuid4().hex
            )
            if (
                self._call(
                    "eval",
                    _PUT,
                    1,
                    self.namespace,
                    self.field(key),
                    encoded,
                    self.encode(updated),
                )
                == 1
            ):
                return True
        raise StateJournalError("Redis state checkpoint revision conflict")
