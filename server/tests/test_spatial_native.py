"""Exercise the installed Rust ABI, including metadata lifetime isolation."""

from pathlib import Path
import ctypes
import json
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.spatial_native import NativeSpatial, NativeSpatialError, _NativeBuffer


class NativeSpatialTests(unittest.TestCase):
    def test_native_internal_failure_is_not_an_ordinary_command_rejection(self):
        # A poisoned native mutex cannot safely be induced in the real shared
        # library. Inject its documented transport envelope into a real handle.
        with NativeSpatial("internal-error-envelope") as native:
            original = native._library
            payload = json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "internal",
                        "message": "Native registry poisoned",
                    },
                }
            ).encode()
            allocation = ctypes.create_string_buffer(payload)
            response = _NativeBuffer(
                ctypes.cast(allocation, ctypes.POINTER(ctypes.c_ubyte)),
                len(payload),
                len(allocation),
            )
            released = []
            native._library = SimpleNamespace(
                wakemu_spatial_call=lambda *_args: response,
                wakemu_spatial_free=lambda buffer: released.append(buffer.len),
                wakemu_spatial_drop=original.wakemu_spatial_drop,
            )
            with self.assertRaisesRegex(RuntimeError, "Native registry poisoned"):
                native.call("engine.stats")
            self.assertEqual(released, [len(payload)])

    def test_real_native_membership_is_isolated_between_engine_handles(self):
        actor = dict(
            id=11, account_id=7, map_id=527, instance_id=0, x=1, y=2, z=3, direction=4
        )
        with NativeSpatial("world-left") as left, NativeSpatial("world-right") as right:
            prepared = left.call(
                "world.join_prepare",
                generation="session-a",
                peer_id=1,
                character=actor,
            )
            left.call("world.join_ready", token=prepared["token"])
            left.call("world.join_commit", token=prepared["token"])
            row = left.call("world.get", id=11)
            self.assertEqual(
                (row["generation"], row["x"], row["z"]), ("session-a", 1, 3)
            )
            self.assertIsNone(right.call("world.get", id=11))

    def test_real_abi_rejections_free_buffers_and_close_is_idempotent(self):
        native = NativeSpatial("ffi-error-lifetime")
        for sequence in range(32):
            with self.assertRaises(NativeSpatialError) as caught:
                native.call("unsupported.fixture.command", sequence=sequence)
            self.assertTrue(caught.exception.code)
            self.assertEqual(caught.exception.native_code, caught.exception.code)
        native.close()
        native.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            native.call("unsupported.fixture.command")

    def test_missing_explicit_library_never_selects_another_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing-spatial-library"
            with patch.dict("os.environ", {"WAKFU_SPATIAL_LIBRARY": str(missing)}):
                with self.assertRaisesRegex(RuntimeError, "library is missing"):
                    NativeSpatial("missing-library")

    def test_domain_metadata_cannot_overwrite_live_world_state(self):
        class NoDeepcopy(dict):
            def __deepcopy__(self, memo):
                raise AssertionError("Character-domain graphs must not be copied")

        owner = (7, "session-a", 11)
        inventory = NoDeepcopy(items=[{"reference": 4275, "quantity": 2}])
        with NativeSpatial("domain-projections") as native:
            world = native.bind_character(
                owner,
                dict(
                    id=11,
                    account_id=7,
                    map_id=527,
                    instance_id=0,
                    x=1,
                    y=2,
                    z=3,
                    direction=4,
                    hp=90,
                    inventory=inventory,
                    guild_native={"name": "Current"},
                ),
                domain="world",
            )
            positions = native.bind_character(
                owner,
                dict(
                    id=11,
                    account_id=7,
                    map_id=1134,
                    instance_id=0,
                    x=0,
                    y=0,
                    z=0,
                    direction=0,
                    hp=60,
                    inventory=inventory,
                ),
                domain="positions",
            )
            self.assertIs(world["inventory"], inventory)
            self.assertIs(positions["inventory"], inventory)
            self.assertEqual(world["hp"], 90)
            self.assertEqual(world["guild_native"], {"name": "Current"})
            self.assertEqual(positions["hp"], 60)
            self.assertFalse(set(world) & {"id", "account_id", "map_id", "x", "y", "z"})
            native.release_character(owner, "world")
            self.assertIsNone(native.character(owner, domain="world"))
            self.assertIs(native.character(owner, domain="positions"), positions)
            native.release_character(owner, "positions")
            self.assertEqual(native.bindings, {})

    def test_close_wakes_a_native_scope_wait_without_holding_the_gil(self):
        native = NativeSpatial("close-scope-wait")
        handle = native._handle
        native.call("world.scope_acquire", map_id=527, instance_id=0)
        started, completed, closed = (threading.Event() for _ in range(3))
        errors = []

        def waiting():
            started.set()
            try:
                native.call("world.scope_acquire", map_id=527, instance_id=0)
            except Exception as error:
                errors.append(error)
            finally:
                completed.set()

        def closing():
            try:
                native.close()
            finally:
                closed.set()

        waiter = threading.Thread(target=waiting, daemon=True)
        closer = threading.Thread(target=closing, daemon=True)
        try:
            waiter.start()
            self.assertTrue(started.wait(2))
            time.sleep(0.03)
            self.assertFalse(completed.is_set())
            closer.start()
            self.assertTrue(
                closed.wait(2), "Native close did not cancel the scope wait"
            )
            self.assertTrue(completed.wait(2), "Native scope waiter did not exit")
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], RuntimeError)
        finally:
            # Also unblock a regressed Python locking implementation so the test
            # reports its failed assertion instead of hanging the test process.
            native._library.wakemu_spatial_drop(handle)
            waiter.join(timeout=2)
            if closer.ident is not None:
                closer.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
