"""Test-only session renewal for disposable TLS clients without native heartbeats."""
import threading


_ACTIVE = {}
_LOCK = threading.Lock()


def start(store, account_id, generation, interval=5):
    """Renew one fixture lease without changing its authenticated generation."""
    with _LOCK:
        previous = _ACTIVE.pop(account_id, None)
        if previous is not None:
            previous[0].set()
        stop = threading.Event()

        def renew():
            while not stop.wait(interval):
                try:
                    if not store.heartbeat(account_id, generation, ttl=3600):
                        return
                except Exception:
                    # Retry transient pool/database failures without replacing
                    # or reviving an expired/replaced generation.
                    continue

        thread = threading.Thread(target=renew, daemon=True)
        _ACTIVE[account_id] = (stop, thread)
        thread.start()


def stop_all():
    """Stop and join all active disposable-session renewers."""
    with _LOCK:
        active = list(_ACTIVE.values())
        _ACTIVE.clear()
    for stop, _ in active:
        stop.set()
    for _, thread in active:
        thread.join(timeout=2)
