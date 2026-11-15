"""Application domain helpers extracted from the World bootstrap."""

from datetime import datetime, timezone
import os


class Diagnostics:
    def __init__(self, runtime):
        self.runtime = runtime

    def write_records(self, rows):
        # Rows have already passed through redact(). Filesystem writes happen on a
        # dedicated bounded queue, independent of LIVE ownership and game threads.
        self.runtime.DIAGNOSTIC_LOG.enqueue(rows)

    def record(self, **fields):
        active = self.runtime.current_request()
        event = fields.get("event", "")
        if active is not None and (
            event.endswith("_rejected") or event.endswith("_failed")
        ):
            active.rejection(event, fields.get("reason", fields.get("detail", "")))
            fields["state_at_rejection"] = self.runtime.safe_snapshot(
                active.failure_snapshot
            )
        row = self.runtime.redact(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "server_boot_id": self.runtime.SERVER_BOOT_ID,
                "server_pid": os.getpid(),
                **self.runtime.request_context(),
                **fields,
            }
        )
        if active is not None and not active.closed:
            active.append(row)
            if event == "unexpected_request_exception":
                active.flush()
        else:
            self.runtime.write_records([row])
