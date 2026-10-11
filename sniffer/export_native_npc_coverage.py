"""Inventory every native conversational speaker and evidence still missing.

Original captures prove spawn identity/map/XYZ. Quest targets and Lua visual
coordinates remain separately classified; they never become actor spawns by
name, graphic identity, or a nearby marker alone.
"""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from export_captured_native_npcs import recover
from qualify_captured_npc_dialogues import qualify


def original_capture(path):
    """Require original world-server provenance for the relevant frames."""
    relevant = 0
    with path.open() as source:
        for line in source:
            frame = json.loads(line)
            if frame.get("opcode") not in (12608, 12969, 13222):
                continue
            relevant += 1
            host = frame.get("remote", "").split("/", 1)[0]
            if not host.endswith(".ankama-games.com"):
                raise ValueError("NPC original source includes an unverified server")
    if not relevant:
        raise ValueError("Capture has no native NPC evidence frames")
    return recover(path)


def coverage(native, captures, markers=()):
    sources, positions, interactions, qualified = [], [], [], []
    for captured in captures:
        digest = captured["source_sha256"]
        if digest in {source["source_sha256"] for source in sources}:
            continue
        sources.append(dict(source=captured["source"], source_sha256=digest))
        positions.extend(dict(row, source_sha256=digest) for row in captured["actors"])
        interactions.extend(
            dict(row, source_sha256=digest) for row in captured["observed_interactions"]
        )
        qualified.extend(qualify(captured, native)["accepted"])
    rows = []
    for speaker in native["speakers"]:
        reference = speaker["ref"]
        observed = [row for row in positions if row["reference_id"] == reference]
        identities = {row["actor_id"] for row in observed}
        opens = [
            row
            for row in interactions
            if row["actor_matches"] and row["actor_id"] in identities
        ]
        accepted = [row for row in qualified if row["actor_id"] in identities]
        targets = [row for row in markers if reference in row["candidate_references"]]
        status = (
            "qualified_observed_initial_contract"
            if accepted
            else "observed_conditional_dialogue"
            if opens
            else "native_position_without_initial_dialogue"
            if observed
            else "quest_marker_candidate_only"
            if targets
            else "catalog_only"
        )
        rows.append(
            dict(
                reference_id=reference,
                name_es=native["translations"]["es"].get("content.7." + str(reference)),
                native_actions=speaker["actions"],
                status=status,
                original_positions=observed,
                observed_interactions=opens,
                qualified_observed_contracts=accepted,
                quest_marker_candidates=targets,
            )
        )
    return dict(
        schema="native-npc-coverage-v1",
        speaker_count=len(rows),
        sources=sources,
        counts=dict(Counter(row["status"] for row in rows)),
        speakers=rows,
        policy="Observed context proposals; no automatic world activation or inferred roots",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--quest-markers", type=Path)
    args = parser.parse_args()
    with gzip.open(args.catalog, "rt") as source:
        native = json.load(source)
    markers = json.loads(args.quest_markers.read_text()) if args.quest_markers else []
    result = coverage(
        native, [original_capture(path) for path in args.captures], markers
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(speakers=result["speaker_count"], counts=result["counts"])))
