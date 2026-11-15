"""Application domain helpers extracted from the World bootstrap."""

import time


class PositionPersistence:
    def __init__(self, runtime):
        self.runtime = runtime

    def position_lease_active(self, account_id, generation, character_id):
        with self.runtime.LOCK:
            live = self.runtime.LIVE.get(account_id)
            return live is not None and live[0] == generation

    def flush_positions(self, *, background_budget=None, **scope):
        started = time.monotonic()
        try:
            with self.runtime.CHECKPOINT_WATCHDOG.watch():
                result = (
                    self.runtime.POSITIONS.flush_background(**background_budget)
                    if background_budget is not None
                    else self.runtime.POSITIONS.flush(**scope)
                )
                count = (
                    result["characters"] if background_budget is not None else result
                )
        except Exception as error:
            self.runtime.record(
                event="position_batch_timing",
                status="failed",
                elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                account_id=scope.get("account_id"),
                error_type=type(error).__name__,
            )
            raise
        if background_budget is None or result["attempted"]:
            self.runtime.record(
                event="position_batch_timing",
                status="completed",
                characters=count,
                elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                account_id=scope.get("account_id"),
            )
        evictions = self.runtime.POSITIONS.drain_evictions()
        for account, generation, character_id in evictions:
            self.runtime.record(
                event="position_buffer_stale_evicted",
                account_id=account,
                actor_id=character_id,
            )
        if count:
            self.runtime.record(event="position_batch_flushed", characters=count)
        return result
