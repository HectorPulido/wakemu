"""Small socket helpers shared by the disposable TLS smoke runners."""


def recv_exact(sock, size, *, closed=None):
    """Read exactly ``size`` bytes, keeping partial data through socket timeouts."""
    result = bytearray()
    while len(result) < size:
        if closed is not None and closed.is_set():
            raise EOFError("TLS peer closed")
        try:
            chunk = sock.recv(size - len(result))
        except TimeoutError:
            # A timeout ends only this recv call; it does not end the frame.
            continue
        if not chunk:
            raise EOFError("TLS peer closed")
        result.extend(chunk)
    return bytes(result)
