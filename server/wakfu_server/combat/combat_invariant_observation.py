"""Opt-in pre-adoption diagnostics with no gameplay rejection or callbacks."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from threading import get_ident

from .combat_invariants import (
    Boundary,
    BoundaryReport,
    Finding,
    check_prepared_boundary,
)


_active = ContextVar("combat_invariant_observation", default=None)


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return get_ident(), task


class BoundaryObservation:
    def __init__(self, limit, resource_authority=None):
        self._owner = _owner()
        self._limit = limit
        self._reports = []
        self._dropped = 0
        self._resource_authority = resource_authority

    @property
    def reports(self):
        return tuple(self._reports)

    @property
    def complete(self):
        return self._dropped == 0 and all(
            row.invariant not in ("checker.failed", "coverage.limit")
            for report in self._reports
            for row in report.findings
        )

    def require_boundary(self, operation):
        matches = tuple(
            report for report in self._reports if report.boundary.operation == operation
        )
        if not self.complete or not matches:
            raise AssertionError("Missing or incomplete invariant boundary observation")
        return matches

    def raise_if_violated(self):
        if not self.complete or not self._reports:
            raise AssertionError("Missing or incomplete invariant boundary observation")
        for report in self._reports:
            report.raise_if_violated()


@contextmanager
def invariant_observation_scope(*, limit=64, resource_authority=None):
    """Each nested scope owns its collector; inherited tasks cannot mutate it.

    Tests assert after execution. Findings are computed before adoption, but
    this observer deliberately supplies no new rollback/enforcement behavior.
    """
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("Bounded invariant observation limit required")
    from .combat_invariant_resources import ResourceAuthority

    if (
        resource_authority is not None
        and type(resource_authority) is not ResourceAuthority
    ):
        raise ValueError("Typed hash-bound resource authority required")
    collector = BoundaryObservation(limit, resource_authority)
    token = _active.set(collector)
    try:
        yield collector
    finally:
        _active.reset(token)


def observe_prepared_boundary(
    fight, runtime, *, operation, runtime_binding="candidate", ack=None
):
    collector = _active.get()
    if collector is None or collector._owner != _owner():
        return
    if len(collector._reports) >= collector._limit:
        collector._dropped += 1
        return
    boundary = Boundary(operation, "pre_adoption", runtime_binding)
    try:
        report = check_prepared_boundary(
            fight,
            runtime,
            boundary,
            resource_authority=collector._resource_authority,
            ack=ack,
        )
    except Exception as error:
        report = BoundaryReport(
            boundary,
            (
                Finding(
                    "checker.failed",
                    "boundary",
                    "unknown",
                    "Inspection failed: " + type(error).__name__,
                ),
            ),
            (),
            0,
        )
    collector._reports.append(report)
