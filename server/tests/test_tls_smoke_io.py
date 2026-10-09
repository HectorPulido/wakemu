"""Concurrent TLS helper checks for disposable protocol smoke clients."""
import threading
import time
import unittest
from unittest.mock import patch

from tools.tls_smoke_io import recv_exact, send_all


class _ConcurrentSocket:
    def __init__(self):
        self.guard = threading.Lock()
        self.active = 0
        self.overlap = False

    def _operation(self):
        with self.guard:
            self.overlap |= self.active > 0
            self.active += 1
        time.sleep(0.03)
        with self.guard:
            self.active -= 1

    def recv(self, size):
        self._operation()
        return b"x"

    def sendall(self, data):
        self._operation()


class _PartialThenTimeoutSocket:
    def __init__(self):
        self.reads = [b"ab", TimeoutError(), b"cd"]

    def recv(self, size):
        value = self.reads.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class _WriterPriorityLock:
    """Deterministically let the writer run when the reader yields."""

    def __init__(self):
        self.guard = threading.Lock()
        self.writer_waiting = threading.Event()
        self.writer_acquired = threading.Event()

    def __enter__(self):
        if self.writer_waiting.is_set():
            self.writer_acquired.set()
            self.writer_waiting.clear()
        self.guard.acquire()
        return self

    def __exit__(self, *_):
        self.guard.release()


class TLSIOTests(unittest.TestCase):
    def test_reader_and_writer_never_overlap_socket_ssl_operations(self):
        sock = _ConcurrentSocket()
        io_lock = threading.Lock()
        start = threading.Event()
        errors = []

        def read_frame():
            start.wait()
            try:
                if recv_exact(sock, 1, io_lock=io_lock) != b"x":
                    raise AssertionError("reader returned an unexpected frame")
            except Exception as error:
                errors.append(error)

        def write_frame():
            start.wait()
            try:
                send_all(sock, b"frame", io_lock=io_lock)
            except Exception as error:
                errors.append(error)

        reader = threading.Thread(target=read_frame)
        writer = threading.Thread(target=write_frame)
        reader.start()
        writer.start()
        start.set()
        reader.join(timeout=1)
        writer.join(timeout=1)

        self.assertFalse(reader.is_alive())
        self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])
        self.assertFalse(sock.overlap)

    def test_timeout_keeps_partial_frame_and_yields_to_waiting_writer(self):
        sock = _PartialThenTimeoutSocket()
        io_lock = _WriterPriorityLock()
        sleeps = []

        def yield_to_writer(seconds):
            sleeps.append(seconds)
            io_lock.writer_waiting.set()

        with patch("tools.tls_smoke_io.time.sleep", side_effect=yield_to_writer):
            self.assertEqual(recv_exact(sock, 4, io_lock=io_lock), b"abcd")
        self.assertEqual(sleeps, [0])

    def test_writer_completes_while_reader_is_polling(self):
        class PollingSocket(_ConcurrentSocket):
            def recv(self, size):
                raise TimeoutError()

        sock = PollingSocket()
        io_lock = threading.Lock()
        stop = threading.Event()
        errors = []

        def poll_reader():
            try:
                recv_exact(sock, 1, closed=stop, io_lock=io_lock)
            except EOFError:
                pass
            except Exception as error:
                errors.append(error)

        reader = threading.Thread(target=poll_reader)
        reader.start()
        time.sleep(0.01)
        start = time.monotonic()
        send_all(sock, b"frame", io_lock=io_lock)
        elapsed = time.monotonic() - start
        stop.set()
        reader.join(timeout=1)

        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
