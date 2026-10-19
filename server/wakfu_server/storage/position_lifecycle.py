"""Deferred lifecycle completion while authoritative positions are contended."""

from .position_buffer import PositionOwnerBusy


class PendingPositionReturn:
    """Retry one return-position flush per idle tick, then finish exactly once."""

    def __init__(self, *, now, initial_delay=0.1, max_delay=1.0):
        if (
            type(now) not in (int, float)
            or type(initial_delay) not in (int, float)
            or initial_delay <= 0
            or type(max_delay) not in (int, float)
            or max_delay < initial_delay
        ):
            raise ValueError("Invalid pending position return policy")
        self.attempts = 0
        self.next_attempt_at = float(now)
        self.initial_delay = float(initial_delay)
        self.max_delay = float(max_delay)
        self.completed = False

    def attempt(self, *, now, flush, complete, busy):
        """Try a single flush; return false while the return remains pending.

        Only PositionOwnerBusy is deferred. Other checkpoint errors propagate.
        Completion is marked before its callback so it can never run twice if a
        later post-flush step raises.
        """
        if self.completed:
            return True
        if (
            type(now) not in (int, float)
            or not callable(flush)
            or not callable(complete)
            or not callable(busy)
        ):
            raise ValueError("Invalid pending position return attempt")
        if now < self.next_attempt_at:
            return False
        try:
            flush()
        except PositionOwnerBusy as error:
            self.attempts += 1
            delay = min(
                self.initial_delay * (2 ** min(self.attempts - 1, 16)),
                self.max_delay,
            )
            self.next_attempt_at = float(now) + delay
            busy(error, self.attempts)
            return False
        self.attempts += 1
        self.completed = True
        complete()
        return True
