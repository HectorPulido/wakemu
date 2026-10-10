"""Bounded, coalesced asynchronous access to the scheduled persistence callback."""
import threading
import time
from collections import OrderedDict


class ManualCheckpoint:
    def __init__(self, flush, *, clock=time.monotonic, history_limit=32):
        if history_limit < 1:
            raise ValueError("Checkpoint history must be positive")
        self.flush = flush
        self.clock = clock
        self.history_limit = history_limit
        self.lock = threading.Lock()
        self.sequence = 0
        self.active = None
        self.results = OrderedDict()

    def request(self, *, requester=None, notify=None):
        """Return immediately; repeated requests join the single active save."""
        with self.lock:
            if self.active is not None:
                run = self.active
                coalesced = True
            else:
                self.sequence += 1
                run = dict(
                    handle=str(self.sequence),
                    status="running",
                    started=self.clock(),
                    listeners={},
                )
                self.active = run
                coalesced = False
            if notify is not None and len(run["listeners"]) < 64:
                run["listeners"][requester] = notify
            result = dict(
                handle=run["handle"], status=run["status"], coalesced=coalesced
            )
            if not coalesced:
                threading.Thread(
                    target=self._run,
                    args=(run,),
                    name="wakfu-manual-checkpoint",
                    daemon=True,
                ).start()
        return result

    def status(self, handle):
        with self.lock:
            if self.active is not None and self.active["handle"] == handle:
                return dict(handle=handle, status="running")
            if handle not in self.results:
                raise ValueError("Checkpoint desconocido o expirado")
            return dict(self.results[handle])

    def _run(self, run):
        try:
            count = self.flush()
            result = dict(handle=run["handle"], status="completed", characters=count)
        except Exception as error:
            # SQL and connection error text can contain private implementation data.
            result = dict(
                handle=run["handle"], status="failed", error_type=type(error).__name__
            )
        result["elapsed_ms"] = round((self.clock() - run["started"]) * 1000, 3)
        with self.lock:
            self.results[run["handle"]] = result
            while len(self.results) > self.history_limit:
                self.results.popitem(last=False)
            listeners = tuple(run["listeners"].values())
            self.active = None
        for notify in listeners:
            try:
                notify(dict(result))
            except Exception:
                # A disconnected requester cannot change persistence success.
                pass


def checkpoint_message(result):
    handle = result["handle"]
    if result["status"] == "running":
        return (
            f"Checkpoint #{handle} en curso. Puedes seguir jugando; "
            f"consulta con !checkpoint {handle}."
        )
    if result["status"] == "completed":
        return (
            f"Checkpoint #{handle} completado: {result['characters']} posiciones "
            f"guardadas en {result['elapsed_ms'] / 1000:.3f} s."
        )
    return f"Checkpoint #{handle} falló ({result['error_type']}); los cambios pendientes se reintentarán."
