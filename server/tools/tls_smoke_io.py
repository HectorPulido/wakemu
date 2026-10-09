"""Small socket helpers shared by the disposable TLS smoke runners."""

import time


def recv_exact(sock, size, *, closed=None, io_lock=None):
    """Read exactly ``size`` bytes, keeping partial data through socket timeouts."""
    result = bytearray()
    while len(result) < size:
        if closed is not None and closed.is_set():
            raise EOFError("TLS peer closed")
        try:
            if io_lock is None:
                chunk = sock.recv(size - len(result))
            else:
                # SSLSocket wraps one OpenSSL SSL object; serialize each
                # individual SSL operation against writes from the caller.
                with io_lock:
                    chunk = sock.recv(size - len(result))
        except TimeoutError:
            # A timeout ends only this recv call; it does not end the frame.
            # Yield the lock to a queued writer instead of immediately
            # reacquiring it in a tight polling loop.
            if io_lock is not None:
                time.sleep(0)
            continue
        if not chunk:
            raise EOFError("TLS peer closed")
        result.extend(chunk)
    return bytes(result)


def send_all(sock, data, *, io_lock=None):
    """Write a complete TLS frame without overlapping another SSL operation."""
    if io_lock is None:
        sock.sendall(data)
    else:
        with io_lock:
            sock.sendall(data)
