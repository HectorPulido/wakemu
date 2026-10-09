#!/usr/bin/env python3
"""Run unittest targets and preserve per-test results plus a complete text log."""

from __future__ import annotations

import argparse
import contextlib
import json
import time
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path


class JsonResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.cases = {}
        self.started = {}

    def startTest(self, test):
        self.started[id(test)] = time.monotonic()
        self.cases[id(test)] = {
            "case_id": test.id(),
            "status": "running",
            "duration_seconds": None,
            "details": None,
        }
        super().startTest(test)

    def _record(self, test, status, details=None):
        row = self.cases.setdefault(id(test), {"case_id": test.id()})
        row["status"] = status
        row["details"] = details

    def stopTest(self, test):
        row = self.cases.setdefault(id(test), {"case_id": test.id()})
        started = self.started.pop(id(test), None)
        if started is not None:
            row["duration_seconds"] = round(time.monotonic() - started, 6)
        if row.get("status") == "running":
            row["status"] = "success"
        super().stopTest(test)

    def addSuccess(self, test):
        self._record(test, "success")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._record(test, "failure", self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self._record(test, "error", self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._record(test, "skipped", reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self._record(test, "expected_failure", self._exc_info_to_string(err, test))
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._record(test, "unexpected_success")
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.cases[f"{id(test)}:{len(self.cases)}"] = {
                "case_id": f"{test.id()} [{subtest}]",
                "status": "failure",
                "duration_seconds": None,
                "details": self._exc_info_to_string(err, test),
            }
        super().addSubTest(test, subtest, err)


class JsonRunner(unittest.TextTestRunner):
    resultclass = JsonResult


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="JSON result path")
    parser.add_argument(
        "--log", required=True, type=Path, help="complete unittest text log"
    )
    parser.add_argument(
        "targets", nargs="+", help="unittest module or dotted test names"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    payload = {
        "started_at": started_at,
        "targets": args.targets,
        "cases": [],
        "collection_error": None,
    }
    exit_code = 0
    try:
        with args.log.open("w", encoding="utf-8") as log, contextlib.redirect_stdout(
            log
        ), contextlib.redirect_stderr(log):
            suite = unittest.TestSuite(
                unittest.defaultTestLoader.loadTestsFromName(target)
                for target in args.targets
            )
            result = JsonRunner(stream=log, verbosity=2).run(suite)
        payload["cases"] = list(result.cases.values())
        exit_code = 0 if result.wasSuccessful() else 1
    except BaseException:
        payload["collection_error"] = traceback.format_exc()
        exit_code = 2
    payload.update(
        finished_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(time.monotonic() - started, 6),
        counts={
            status: sum(case.get("status") == status for case in payload["cases"])
            for status in (
                "success",
                "failure",
                "error",
                "skipped",
                "expected_failure",
                "unexpected_success",
            )
        },
        exit_code=exit_code,
        log=str(args.log.resolve()),
    )
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
