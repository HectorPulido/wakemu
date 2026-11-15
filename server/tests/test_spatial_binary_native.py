"""Binary codec ABI ownership, validation and transport failure handling."""

import ctypes
from types import SimpleNamespace
import unittest

from wakfu_server.spatial_native import NativeSpatial, NativeSpatialError, _NativeBuffer


class NativeBinaryTests(unittest.TestCase):
    def test_real_binary_codec_preserves_nuls_and_releases_rejection_buffers(self):
        with NativeSpatial("binary-codec") as native:
            self.assertEqual(
                native.call_binary(3, buffers=(b"a\x00b", b"", b"c")), b"a\x00bc"
            )
            self.assertEqual(native.call_binary(3), b"")
            for _ in range(16):
                with self.assertRaises(NativeSpatialError):
                    native.call_binary(0xFFFFFFFF)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            native.call_binary(3)

    def test_binary_inputs_borrow_original_bytes_and_output_is_freed(self):
        source = b"owned\x00input"
        with NativeSpatial("binary-borrow") as native:
            original = native._library
            allocation = ctypes.create_string_buffer(b"\x00ok\x00done")
            response = _NativeBuffer(
                ctypes.cast(allocation, ctypes.POINTER(ctypes.c_ubyte)),
                8,
                len(allocation),
            )
            released = []

            def encode(handle, op, descriptors, count, integers, integer_count):
                self.assertEqual(op, 3)
                self.assertEqual((count, integer_count), (1, 2))
                self.assertEqual(
                    descriptors[0].data,
                    ctypes.cast(ctypes.c_char_p(source), ctypes.c_void_p).value,
                )
                self.assertEqual(
                    ctypes.string_at(descriptors[0].data, descriptors[0].len), source
                )
                self.assertEqual(
                    (integers[0], integers[1]), (-(1 << 63), (1 << 63) - 1)
                )
                return response

            native._library = SimpleNamespace(
                wakemu_wire_call=encode,
                wakemu_spatial_free=lambda output: released.append(output.len),
                wakemu_spatial_drop=original.wakemu_spatial_drop,
            )
            self.assertEqual(
                native.call_binary(
                    3, buffers=(source,), integers=(-(1 << 63), (1 << 63) - 1)
                ),
                b"ok\x00done",
            )
            self.assertEqual(released, [8])

    def test_binary_statuses_free_output_and_distinguish_internal_failure(self):
        with NativeSpatial("binary-status") as native:
            original = native._library
            for status, expected in (
                (1, NativeSpatialError),
                (2, RuntimeError),
                (255, RuntimeError),
            ):
                with self.subTest(status=status):
                    payload = bytes([status]) + b"rejected"
                    allocation = ctypes.create_string_buffer(payload)
                    response = _NativeBuffer(
                        ctypes.cast(allocation, ctypes.POINTER(ctypes.c_ubyte)),
                        len(payload),
                        len(allocation),
                    )
                    released = []
                    native._library = SimpleNamespace(
                        wakemu_wire_call=lambda *_args: response,
                        wakemu_spatial_free=lambda output: released.append(output.len),
                        wakemu_spatial_drop=original.wakemu_spatial_drop,
                    )
                    with self.assertRaises(expected):
                        native.call_binary(3)
                    self.assertEqual(released, [len(payload)])

    def test_invalid_python_inputs_are_rejected_before_native_dispatch(self):
        with NativeSpatial("binary-validation") as native:
            for kwargs in (
                {"op": True},
                {"op": -1},
                {"op": 1 << 32},
                {"op": 3, "buffers": (bytearray(b"mutable"),)},
                {"op": 3, "integers": (True,)},
                {"op": 3, "integers": (1 << 63,)},
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    native.call_binary(**kwargs)

    def test_binary_error_retains_native_cache_miss_code(self):
        with NativeSpatial("binary-cache-miss") as native:
            original = native._library
            payload = b"\x01scene_cache_miss\x00Reload the evicted scene index"
            allocation = ctypes.create_string_buffer(payload)
            response = _NativeBuffer(
                ctypes.cast(allocation, ctypes.POINTER(ctypes.c_ubyte)),
                len(payload),
                len(allocation),
            )
            released = []
            native._library = SimpleNamespace(
                wakemu_wire_call=lambda *_args: response,
                wakemu_spatial_free=lambda output: released.append(output.len),
                wakemu_spatial_drop=original.wakemu_spatial_drop,
            )
            with self.assertRaises(NativeSpatialError) as caught:
                native.call_binary(3)
            self.assertEqual(caught.exception.code, "scene_cache_miss")
            self.assertEqual(str(caught.exception), "Reload the evicted scene index")
            self.assertEqual(released, [len(payload)])
