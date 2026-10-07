import unittest

from server.tools.tls_smoke_io import recv_exact


class _FragmentedSocket:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def recv(self, size):
        chunk = next(self.chunks)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk[:size]


class TLSReadExactTests(unittest.TestCase):
    def test_partial_frame_survives_timeout(self):
        sock = _FragmentedSocket((b"\x00\x00", TimeoutError(), b"\x00\x07", b"\x03"))
        self.assertEqual(recv_exact(sock, 5), b"\x00\x00\x00\x07\x03")

    def test_eof_after_partial_frame_is_not_reframed(self):
        sock = _FragmentedSocket((b"\x00\x00", b""))
        with self.assertRaises(EOFError):
            recv_exact(sock, 4)
