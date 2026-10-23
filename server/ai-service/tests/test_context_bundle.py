"""Final-block piggybacking must never advance a search before verification."""
import base64
from copy import deepcopy
import hashlib
import io
import json
import random
import tempfile
import unittest
from unittest.mock import Mock

from wakfu_ai.bridge.world_bridge import ContextTransport, _json_bytes
from wakfu_ai.context.context_store import ContextStore
from wakfu_ai.planning.query_sessions import QuerySessions
from wakfu_ai.transport.context_bundle import bundle_size, continue_request


def continuation(identity="1"):
    return dict(
        requestId="owner",
        sourceKey="a" * 64,
        response=dict(id=identity, supported=True, result={}),
    )


def block(data, *, offset=0, complete=None):
    whole = data if complete is None else complete
    return dict(
        sha256=hashlib.sha256(whole).hexdigest(),
        size=len(whole),
        offset=offset,
        data=base64.b64encode(data).decode(),
    )


class Sessions:
    _validate_identity = staticmethod(QuerySessions._validate_identity)

    def __init__(self):
        self.calls = 0
        self.answers = {}

    def decide(self, payload, store):
        identity = payload["response"]["id"]
        if identity in self.answers:
            return self.answers[identity]
        self.calls += 1
        result = dict(status="decided", decision=dict(action=dict(type="end_turn")))
        self.answers[identity] = result
        return result


class LocalTransport(ContextTransport):
    def __init__(self, store, sessions, **kwargs):
        super().__init__("http://fixture", **kwargs)
        self.store, self.sessions, self.sent = store, sessions, []
        self.lose_reply = False

    def request(self, endpoint, payload):
        self.sent.append((endpoint, deepcopy(payload)))
        if endpoint == "/v3/context/block":
            return self.store.put(
                payload["sha256"],
                payload["size"],
                payload["offset"],
                base64.b64decode(payload["data"], validate=True),
            )
        if endpoint == "/v3/context/continue":
            result = continue_request(payload, self.store, self.sessions)
            if self.lose_reply:
                self.lose_reply = False
                raise ConnectionError("reply lost after commit")
            return result
        if endpoint == "/v3/decide":
            return self.sessions.decide(payload, self.store)
        raise AssertionError(endpoint)


class ContextBundleTests(unittest.TestCase):
    def test_bundle_size_matches_complete_wire_json_for_ascii_and_unicode_metadata(
        self,
    ):
        for request in (continuation(), dict(continuation(), requestId='héctor/"\\')):
            for blocks in ([], [block(b"a")], [block(b"a"), block(b"b" * 16384)]):
                self.assertEqual(
                    bundle_size(request, blocks),
                    len(_json_bytes(dict(request=request, blocks=blocks))),
                )

    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.store = ContextStore(root.name)
        self.addCleanup(self.store.close)
        self.sessions = Sessions()
        self.transport = LocalTransport(self.store, self.sessions)

    def test_small_complete_context_and_continuation_share_one_request(self):
        data = b"entire complete native graph"
        digest = hashlib.sha256(data).hexdigest()
        self.transport.begin_context_bundle()
        self.assertEqual(
            self.transport._upload(io.BytesIO(data), digest, len(data)), digest
        )
        self.assertFalse(self.store.has(digest))
        self.assertEqual(self.transport.sent, [])
        self.transport.continue_with_context(continuation())
        self.assertEqual(
            [path for path, _ in self.transport.sent], ["/v3/context/continue"]
        )
        self.assertEqual(self.store.read(digest), data)
        self.assertEqual(self.sessions.calls, 1)
        self.assertIsNone(self.transport._context_bundle)

    def test_large_context_stages_blocks_and_attaches_only_complete_final_block(self):
        self.transport.block_bytes = 4
        data = b"1234567890"
        digest = hashlib.sha256(data).hexdigest()
        self.transport.begin_context_bundle()
        self.transport._upload(io.BytesIO(data), digest, len(data))
        self.assertEqual([entry[1]["offset"] for entry in self.transport.sent], [0, 4])
        self.assertEqual(self.transport._context_bundle[0]["offset"], 8)
        self.transport.continue_with_context(continuation())
        self.assertEqual(self.store.read(digest), data)
        self.assertEqual(len(self.transport.sent), 3)

    def test_all_attachment_shapes_and_full_checksums_precede_any_publication(self):
        good = block(b"good")
        bad = block(b"other")
        bad["data"] = base64.b64encode(b"wrong").decode()
        with self.assertRaisesRegex(ValueError, "checksum"):
            continue_request(
                dict(request=continuation(), blocks=[good, bad]),
                self.store,
                self.sessions,
            )
        self.assertEqual(self.sessions.calls, 0)
        self.assertFalse(self.store.has(good["sha256"]))

    def test_bad_staged_final_checksum_cannot_advance_search(self):
        good = block(b"123456")
        self.store.put(good["sha256"], 6, 0, b"123")
        bad = dict(good, offset=3, data=base64.b64encode(b"bad").decode())
        with self.assertRaisesRegex(ValueError, "checksum"):
            continue_request(
                dict(request=continuation(), blocks=[bad]), self.store, self.sessions
            )
        self.assertEqual(self.sessions.calls, 0)
        self.assertFalse(self.store.has(good["sha256"]))

    def test_existing_verified_object_does_not_hide_bad_repeated_attachment(self):
        data = b"good"
        good = block(data)
        self.store.put(good["sha256"], 4, 0, data)
        bad = dict(good, offset=2, data=base64.b64encode(b"xx").decode())
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            continue_request(
                dict(request=continuation(), blocks=[bad]), self.store, self.sessions
            )
        self.assertEqual(self.sessions.calls, 0)
        self.assertEqual(self.store.read(good["sha256"]), data)

    def test_lost_reply_retry_uses_identical_bundle_without_second_advance(self):
        data = b"complete native graph"
        self.transport.begin_context_bundle()
        self.transport._upload(
            io.BytesIO(data), hashlib.sha256(data).hexdigest(), len(data)
        )
        self.transport.lose_reply = True
        self.transport.continue_with_context(continuation())
        self.assertEqual(self.sessions.calls, 1)
        self.assertEqual(len(self.transport.sent), 2)
        self.assertEqual(self.transport.sent[0], self.transport.sent[1])

    def test_failure_retains_pending_bundle_until_explicit_abort(self):
        data = b"complete"
        self.transport.begin_context_bundle()
        self.transport._upload(
            io.BytesIO(data), hashlib.sha256(data).hexdigest(), len(data)
        )
        pending = deepcopy(self.transport._context_bundle)
        self.transport._retry_request = Mock(side_effect=ConnectionError("down"))
        with self.assertRaises(ConnectionError):
            self.transport.continue_with_context(continuation())
        self.assertEqual(self.transport._context_bundle, pending)
        self.transport.abort_context_bundle()
        self.assertIsNone(self.transport._context_bundle)

    def test_attachment_count_overflow_flushes_complete_objects_without_truncation(
        self,
    ):
        self.transport.begin_context_bundle()
        data = [f"graph-{i}".encode() for i in range(20)]
        for raw in data:
            self.transport._upload(
                io.BytesIO(raw), hashlib.sha256(raw).hexdigest(), len(raw)
            )
        self.assertEqual(len(self.transport._context_bundle), 16)
        self.transport.continue_with_context(continuation())
        for raw in data:
            self.assertEqual(self.store.read(hashlib.sha256(raw).hexdigest()), raw)
        self.assertEqual(self.sessions.calls, 1)

    def test_byte_overflow_flushes_without_oversized_envelopes(self):
        self.transport.begin_context_bundle()
        rng = random.Random(42)
        data = [rng.randbytes(1024 * 1024) for _ in range(3)]
        for raw in data:
            self.transport._upload(
                io.BytesIO(raw), hashlib.sha256(raw).hexdigest(), len(raw)
            )
        self.transport.continue_with_context(continuation())
        self.assertTrue(
            all(
                len(_json_bytes(payload)) < 4 * 1024 * 1024
                for _, payload in self.transport.sent
            )
        )
        self.assertTrue(
            all(
                self.store.has(hashlib.sha256(raw).hexdigest(), len(raw))
                for raw in data
            )
        )

    def test_duplicate_registration_and_custom_subclass_without_super(self):
        transport = object.__new__(LocalTransport)
        transport.store, transport.sessions, transport.sent = (
            self.store,
            self.sessions,
            [],
        )
        transport.block_bytes = 1024
        transport.lose_reply = False
        raw = b"same graph"
        digest = hashlib.sha256(raw).hexdigest()
        transport.begin_context_bundle()
        for _ in range(2):
            transport._upload(io.BytesIO(raw), digest, len(raw))
        self.assertEqual(len(transport._context_bundle), 1)
        transport.continue_with_context(continuation())
        self.assertEqual(self.sessions.calls, 1)

    def test_no_attachment_uses_existing_endpoint_and_invalid_lists_do_not_advance(
        self,
    ):
        self.transport.begin_context_bundle()
        self.transport.continue_with_context(continuation())
        self.assertEqual(self.transport.sent[0][0], "/v3/decide")
        before = self.sessions.calls
        for blocks in ([], [block(b"x")] * 2, [dict(block(b"x"), data="!")]):
            with self.assertRaises(ValueError):
                continue_request(
                    dict(request=continuation("bad"), blocks=blocks),
                    self.store,
                    self.sessions,
                )
        self.assertEqual(self.sessions.calls, before)


if __name__ == "__main__":
    unittest.main()
