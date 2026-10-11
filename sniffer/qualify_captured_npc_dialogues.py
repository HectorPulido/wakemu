"""Qualify observed native NPC initial responses without inventing story state.

Output is an offline proposal, never an unconditional population import. Native
captured spawn scope and subsequent movement must be reviewed before activation.
"""
import argparse
import gzip
import json
from pathlib import Path


def qualify(capture, native):
    speakers = {row["ref"]: row for row in native["speakers"]}
    nodes = {row["id"]: row for row in native["nodes"]}
    accepted, withheld = [], []
    for event in capture["observed_interactions"]:
        reasons = []
        spawn, response = event["spawn"], event["response"]
        if not event["actor_matches"] or spawn is None:
            reasons.append("no_matching_native_actor_spawn")
        speaker = speakers.get(spawn["reference_id"]) if spawn else None
        action = (
            next(
                (row for row in speaker["actions"] if row["id"] == event["action_id"]),
                None,
            )
            if speaker
            else None
        )
        node = nodes.get(response["node_id"])
        if action is None:
            reasons.append("no_native_speaker_action")
        elif action.get("criteria"):
            reasons.append("native_action_requires_story_state")
        if node is None:
            reasons.append("missing_native_node")
        elif node.get("criteria"):
            reasons.append("native_node_requires_story_state")
        elif spawn and node.get("native_cmT") not in (
            "",
            "npc" + str(spawn["reference_id"]),
        ):
            reasons.append("native_portrait_mismatch")
        # A single action may choose roots using server state absent from the
        # extracted node criteria. Require one observed response per actor/action.
        roots = {
            other["response"]["node_id"]
            for other in capture["observed_interactions"]
            if other["actor_id"] == event["actor_id"]
            and other["action_id"] == event["action_id"]
            and other["actor_matches"]
        }
        if len(roots) != 1:
            reasons.append("multiple_observed_initial_roots")
        record = dict(
            event,
            withholding_reasons=reasons,
            scope="observed_native_capture_context",
            source_sha256=capture["source_sha256"],
        )
        (withheld if reasons else accepted).append(record)
    return dict(
        schema="qualified-captured-npc-dialogues-v1",
        accepted=accepted,
        withheld=withheld,
        unconditional_world_activation=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with gzip.open(args.catalog, "rt") as source:
        result = qualify(json.loads(args.capture.read_text()), json.load(source))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "qualified_observed_interactions=",
        len(result["accepted"]),
        "withheld=",
        len(result["withheld"]),
    )
