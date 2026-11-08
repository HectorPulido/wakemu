"""Unit cases for the isolated native handler registry proposal."""
import unittest
from types import SimpleNamespace

from test_retained_indexed_query import fixture
from wakfu_server.combat_versioned_handlers import NativeVersionedHandlers
from wakfu_server.combat_structural_qf_scope import Frame, _FRAMES, qualify_replay


class VersionedHandlerTests(unittest.TestCase):
    def frame_scope(self, dispatcher):
        frame = Frame(dispatcher)
        token = _FRAMES.set((*_FRAMES.get(), frame))
        return frame, token

    def test_public_mapping_mutations_advance_version_and_keep_alias(self):
        handlers = NativeVersionedHandlers({1: object()})
        alias = handlers
        version = handlers.version
        handlers[2] = object()
        self.assertEqual(handlers.version, version + 1)
        version = handlers.version
        handlers.update({3: object()})
        self.assertEqual(handlers.version, version + 1)
        version = handlers.version
        handlers.setdefault(4, object())
        self.assertEqual(handlers.version, version + 1)
        version = handlers.version
        handlers.pop(3)
        self.assertEqual(handlers.version, version + 1)
        self.assertIs(alias, handlers)
        self.assertEqual(list(handlers), [1, 2, 4])
        self.assertEqual(dict(handlers), handlers.copy())

    def test_reentrant_partial_update_is_visible_and_clears_guard_on_error(self):
        handlers = NativeVersionedHandlers({1: "first"})
        observed = []
        version = handlers.version

        class ReentrantPairs:
            def __iter__(self):
                observed.append(handlers.mutation_in_progress)
                yield (2, "second")
                observed.append(handlers.mutation_in_progress)
                raise RuntimeError("stop after one native-style update")

        with self.assertRaisesRegex(RuntimeError, "stop after one"):
            handlers.update(ReentrantPairs())
        self.assertEqual(observed, [True, True])
        self.assertEqual(handlers[2], "second")
        self.assertGreater(handlers.version, version)
        self.assertFalse(handlers.mutation_in_progress)

    def test_custom_key_callback_sees_mutation_guard_before_hash(self):
        handlers = NativeVersionedHandlers()
        observed = []

        class Key:
            def __hash__(self):
                observed.append(handlers.mutation_in_progress)
                return 7

        handlers[Key()] = "value"
        self.assertEqual(observed, [True])
        self.assertFalse(handlers.mutation_in_progress)

    def test_real_qualify_replay_checks_version_replacement_and_legacy_map(self):
        fight, retention = fixture()
        authority = object()

        native_handlers = NativeVersionedHandlers({1: object()})
        dispatcher = SimpleNamespace(
            handlers=native_handlers,
            native_retention=retention,
            native_clone_authority=authority,
        )
        frame, token = self.frame_scope(dispatcher)
        try:
            qualify_replay(dispatcher, retention, authority)
            self.assertTrue(frame.enabled)
            dispatcher.handlers[1] = object()
            qualify_replay(dispatcher, retention, authority)
            self.assertFalse(frame.enabled)
        finally:
            _FRAMES.reset(token)

        dispatcher.handlers = NativeVersionedHandlers({1: object()})
        frame, token = self.frame_scope(dispatcher)
        try:
            dispatcher.handlers = NativeVersionedHandlers({1: object()})
            qualify_replay(dispatcher, retention, authority)
            self.assertFalse(frame.enabled)
        finally:
            _FRAMES.reset(token)

        dispatcher.handlers = {1: object()}
        frame, token = self.frame_scope(dispatcher)
        try:
            dispatcher.handlers[1] = object()
            qualify_replay(dispatcher, retention, authority)
            self.assertFalse(frame.enabled)
        finally:
            _FRAMES.reset(token)

    def test_qualify_revokes_frame_created_during_reentrant_partial_update(self):
        _fight, retention = fixture()
        authority = object()
        handlers = NativeVersionedHandlers({1: object()})
        dispatcher = SimpleNamespace(
            handlers=handlers,
            native_retention=retention,
            native_clone_authority=authority,
        )
        outer, outer_token = self.frame_scope(dispatcher)
        created = []

        class ReentrantPairs:
            def __iter__(self):
                frame = Frame(dispatcher)
                created.append(frame)
                token = _FRAMES.set((*_FRAMES.get(), frame))
                try:
                    qualify_replay(dispatcher, retention, authority)
                finally:
                    _FRAMES.reset(token)
                yield (2, "partial")
                raise RuntimeError("stop after partial update")

        try:
            with self.assertRaisesRegex(RuntimeError, "partial update"):
                handlers.update(ReentrantPairs())
            self.assertFalse(created[0].enabled)
            qualify_replay(dispatcher, retention, authority)
            self.assertFalse(outer.enabled)
            self.assertFalse(handlers.mutation_in_progress)
            self.assertIn(2, handlers)
        finally:
            _FRAMES.reset(outer_token)


if __name__ == "__main__":
    unittest.main()
