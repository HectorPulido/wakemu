#!/usr/bin/env python3
"""Extract exact failed transaction pairs from a completed normal-cast audit.

This is a standard-library-only report summarizer. It does not load the game
catalog or run combat. Bounded-search and unresolved-authority outcomes are
kept outside the transaction-rejection manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class _JsonStream:
    """Small-buffer JSON reader; decoded values are bounded individually."""

    def __init__(
        self,
        stream,
        *,
        chunk_size: int = 64 * 1024,
        max_value_chars: int = 32 * 1024 * 1024,
    ):
        self.stream = stream
        self.chunk_size = chunk_size
        self.max_value_chars = max_value_chars
        self.buffer = ""
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def _fill(self) -> bool:
        if self.position:
            self.buffer = self.buffer[self.position :]
            self.position = 0
        chunk = self.stream.read(self.chunk_size)
        if chunk == "":
            self.eof = True
            return False
        self.buffer += chunk
        if len(self.buffer) > self.max_value_chars:
            raise ValueError(
                "A single JSON value exceeds the configured streaming bound"
            )
        return True

    def _ensure(self) -> bool:
        if self.position < len(self.buffer):
            return True
        return self._fill()

    def whitespace(self) -> None:
        while True:
            while (
                self.position < len(self.buffer)
                and self.buffer[self.position] in " \t\r\n"
            ):
                self.position += 1
            if self.position < len(self.buffer) or not self._fill():
                return

    def peek(self) -> str:
        self.whitespace()
        if self.position >= len(self.buffer):
            raise ValueError("Unexpected end of JSON report")
        return self.buffer[self.position]

    def take(self, expected: str | None = None) -> str:
        char = self.peek()
        if expected is not None and char != expected:
            raise ValueError(f"Expected {expected!r}, found {char!r}")
        self.position += 1
        return char

    def decode_value(self):
        self.whitespace()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
                self.position = end
                return value
            except json.JSONDecodeError as exc:
                if self.eof or not self._fill():
                    raise ValueError(
                        f"Invalid or truncated JSON report at character {exc.pos}: {exc.msg}"
                    ) from exc

    def skip_value(self) -> None:
        """Validate and skip an unneeded JSON value without retaining containers."""
        first = self.peek()
        if first == '"':
            self._skip_string()
            return
        if first == "{":
            self.take("{")
            if self.peek() == "}":
                self.take("}")
                return
            while True:
                if self.peek() != '"':
                    raise ValueError("JSON object keys must be strings")
                self._skip_string()
                self.take(":")
                self.skip_value()
                delimiter = self.peek()
                if delimiter == "}":
                    self.take("}")
                    return
                self.take(",")
        if first == "[":
            self.take("[")
            if self.peek() == "]":
                self.take("]")
                return
            while True:
                self.skip_value()
                delimiter = self.peek()
                if delimiter == "]":
                    self.take("]")
                    return
                self.take(",")
        if first in "}]":
            raise ValueError(f"Unexpected JSON delimiter {first!r}")

        token = []
        while self._ensure():
            char = self.buffer[self.position]
            if char in ",]} \t\r\n":
                break
            token.append(char)
            self.position += 1
        try:
            value = json.loads(
                "".join(token),
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid JSON scalar {''.join(token)!r}") from exc
        if isinstance(value, (dict, list, str)):
            raise ValueError("Unexpected JSON scalar value")

    def _skip_string(self) -> None:
        self.take('"')
        while True:
            if not self._ensure():
                raise ValueError("Truncated string in skipped JSON value")
            char = self.buffer[self.position]
            self.position += 1
            if char == '"':
                return
            if ord(char) < 0x20:
                raise ValueError("Control character in JSON string")
            if char != "\\":
                continue
            if not self._ensure():
                raise ValueError("Truncated escape in skipped JSON string")
            escape = self.buffer[self.position]
            self.position += 1
            if escape in '"\\/bfnrt':
                continue
            if escape != "u":
                raise ValueError("Invalid escape in skipped JSON string")
            for _ in range(4):
                if (
                    not self._ensure()
                    or self.buffer[self.position] not in "0123456789abcdefABCDEF"
                ):
                    raise ValueError("Invalid unicode escape in skipped JSON string")
                self.position += 1


def _stream_report(report_path: Path, on_row) -> dict:
    """Read summary metadata and invoke on_row once per row, without loading the file."""
    metadata = {}
    seen_root_keys = set()
    rows_present = False
    metadata_keys = {
        "finished",
        "numeric_summary",
        "scope",
        "source_before",
        "source_after",
        "source_stable",
        "tool_sha256",
        "tool_stable",
        "normal_tool_sha256",
        "normal_tool_stable",
        "ready_gate_passed",
        "commit_policy",
        "commit_each_prepared",
    }
    with report_path.open("r", encoding="utf-8") as stream:
        reader = _JsonStream(stream)
        reader.take("{")
        if reader.peek() == "}":
            reader.take("}")
        else:
            while True:
                key = reader.decode_value()
                if not isinstance(key, str):
                    raise ValueError("Normal-cast report root keys must be strings")
                if key in seen_root_keys:
                    raise ValueError(f"Duplicate top-level JSON key: {key}")
                seen_root_keys.add(key)
                reader.take(":")
                if key == "rows":
                    rows_present = True
                    reader.take("[")
                    if reader.peek() != "]":
                        while True:
                            row = reader.decode_value()
                            if not isinstance(row, dict):
                                raise ValueError(
                                    "Normal-cast report rows must be objects"
                                )
                            on_row(row)
                            delimiter = reader.peek()
                            if delimiter == "]":
                                break
                            reader.take(",")
                    reader.take("]")
                elif key in metadata_keys:
                    metadata[key] = reader.decode_value()
                else:
                    reader.skip_value()
                delimiter = reader.peek()
                if delimiter == "}":
                    reader.take("}")
                    break
                reader.take(",")
        reader.whitespace()
        if reader.position < len(reader.buffer) or reader._fill():
            reader.whitespace()
            if reader.position < len(reader.buffer):
                raise ValueError("Trailing data after JSON report")
    metadata["_rows_present"] = rows_present
    return metadata


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stream_report_rows(report_path: Path, on_row) -> dict:
    """Public bounded-memory reader for audit tools that need custom row filters.

    ``on_row`` receives one fully decoded row at a time. Rows are not retained
    by this reader; selected root metadata and a chunked file hash are returned.
    """
    metadata = _stream_report(report_path, on_row)
    return {"metadata": metadata, "report_sha256": _sha256_file(report_path)}


def _attempt_summary(attempt: dict) -> dict:
    failure = attempt.get("first_root_failure") or {}
    effect = failure.get("first_failed_effect") or {}
    return {
        "branch": attempt.get("branch"),
        "target": attempt.get("target"),
        "status": attempt.get("status"),
        "failed_stage": attempt.get("failed_stage"),
        "reason": failure.get("root_reason", failure.get("reason")),
        "failure_kind": failure.get("kind"),
        "effect_reference": effect.get("effect_reference"),
        "effect_family": effect.get("effect_class"),
        "effect_level": effect.get("level"),
        "target_id": effect.get("target_id"),
        "state_uid": effect.get("state_uid"),
    }


def summarize(report_path: Path) -> dict:
    pairs = []
    seen = {}

    def visit_row(row):
        runtime = row.get("runtime_access") or {}
        for action in runtime.get("actions", []):
            if action.get("origin") != "normal_owned_deck":
                continue
            if action.get("status") != "effect_transaction_rejected":
                continue

            key = (row.get("breed"), row.get("level"), action.get("reference"))
            if key in seen:
                existing = seen[key]
                attempts = [
                    _attempt_summary(attempt)
                    for attempt in action.get("attempts", [])
                    if attempt.get("status") == "rejected"
                    and attempt.get("failed_stage") == "effect_transaction"
                ]
                if existing["attempts"] != attempts:
                    raise ValueError(
                        f"Conflicting duplicate transaction-rejected pair: {key}"
                    )
                continue
            attempts = [
                _attempt_summary(attempt)
                for attempt in action.get("attempts", [])
                if attempt.get("status") == "rejected"
                and attempt.get("failed_stage") == "effect_transaction"
            ]
            if not attempts:
                raise ValueError(
                    f"Rejected action has no qualified transaction attempt: {key}"
                )
            first_effect = next(
                (
                    attempt["effect_family"]
                    for attempt in attempts
                    if attempt["effect_family"] is not None
                ),
                None,
            )
            pairs.append(
                {
                    "breed": key[0],
                    "level": key[1],
                    "spell_reference": key[2],
                    "first_failed_family": first_effect,
                    "attempts": attempts,
                }
            )
            seen[key] = pairs[-1]

    streamed = stream_report_rows(report_path, visit_row)
    metadata = streamed["metadata"]
    if metadata.get("finished") is not True:
        raise ValueError("Normal-cast report is not marked finished")
    if not metadata.get("_rows_present"):
        raise ValueError("Normal-cast report has no rows array")
    numeric_summary = metadata.get("numeric_summary")
    if not isinstance(numeric_summary, dict) or not isinstance(
        numeric_summary.get("normal"), dict
    ):
        raise ValueError(
            "Normal-cast report has no valid numeric_summary.normal metadata"
        )
    summary = numeric_summary["normal"]
    partition = summary.get("preparation_partition")
    if not isinstance(partition, dict):
        raise ValueError(
            "Normal-cast report has no valid normal.preparation_partition metadata"
        )
    expected = partition.get("effect_transaction_rejected")
    if isinstance(expected, bool) or not isinstance(expected, int):
        raise ValueError("Normal-cast report has no integer transaction-rejected count")

    pairs.sort(key=lambda item: (item["breed"], item["level"], item["spell_reference"]))
    if len(pairs) != expected:
        raise ValueError(
            f"Expected {expected} transaction-rejected pairs, extracted {len(pairs)}"
        )
    return {
        "report": str(report_path),
        "report_sha256": streamed["report_sha256"],
        "denominator_spell_level_pairs": summary.get("expected_spell_level_pairs"),
        "transaction_rejected_pairs": len(pairs),
        "qualification": "normal_owned_deck action status=effect_transaction_rejected; includes only rejected attempts with failed_stage=effect_transaction",
        "negative_prerequisite_outcomes_included": False,
        "pairs": pairs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report", type=Path, help="completed audit_class_normal_casts JSON"
    )
    parser.add_argument("output", type=Path, help="manifest JSON output")
    args = parser.parse_args()
    result = summarize(args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        f"Wrote {result['transaction_rejected_pairs']} pairs from {result['report_sha256']}"
    )


if __name__ == "__main__":
    main()
