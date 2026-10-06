"""Retry a logout barrier without repeating already completed barriers."""
import time


def retry_step(operation, *, retry_errors, failed, renew, wait=time.sleep):
    """Keep ownership during a transient outage; propagate invariant failures.

    Operations must be idempotent: a connection can fail after a commit. The
    caller advances to the next barrier only when this operation succeeds.
    """
    while True:
        try:
            return operation()
        except retry_errors as error:
            failed(error)
            try:
                renew()
            except retry_errors:
                pass
            wait(1)
