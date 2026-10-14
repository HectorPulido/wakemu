"""Local bounded position persistence without distributed occurrence history."""
import time

from .position_checkpoint_policy import REFRESH_SECONDS, load_policy


class PositionCheckpointWorker:
    def __init__(
        self,
        store,
        positions,
        stopping,
        *,
        record,
        clock=time.monotonic,
        loader=load_policy,
        checkpoint=None
    ):
        self.store, self.positions, self.stopping = store, positions, stopping
        self.record, self.clock, self.loader = record, clock, loader
        # Missing/invalid SQL policy is a startup failure, never a silent fallback.
        self.policy = loader(store)
        self.refresh_at = clock() + REFRESH_SECONDS
        self.checkpoint = checkpoint or positions.flush_background

    def run_once(self):
        now = self.clock()
        if now >= self.refresh_at:
            self.refresh_at = now + REFRESH_SECONDS
            try:
                self.policy = self.loader(self.store)
            except Exception as error:
                self.record(
                    event="position_checkpoint_policy_refresh_failed",
                    error_type=type(error).__name__,
                )
        started = self.clock()
        result = self.checkpoint(
            max_accounts=self.policy["max_accounts"],
            max_seconds=self.policy["max_seconds"],
        )
        # Log activity/failures, not an endless stream of idle sweeps.
        if result["attempted"] or result["failures"]:
            self.record(
                event="position_checkpoint_pass",
                **result,
                elapsed_ms=round((self.clock() - started) * 1000, 3)
            )
        return result

    def run(self):
        while not self.stopping.wait(self.policy["interval_seconds"]):
            try:
                self.run_once()
            except Exception as error:
                self.record(
                    event="position_checkpoint_pass_failed",
                    error_type=type(error).__name__,
                )
