"""Compile the reviewed final Chapter2 handoffs using existing NPC settlement.

This source-only compiler never publishes or mutates player state. Its explicit
wool debit reconstructs a missing server operand from the native predecessor
reward and handover objective, corroborated by the published walkthrough.
"""
from copy import deepcopy
from wakfu_server.achievements import conversation_story_authoring
from wakfu_server.achievements.conversation_turnin import requirement_from_entry


def compile_fragment(document, definitions, nodes, speakers, manifest):
    result = conversation_story_authoring.extend(
        document, definitions, nodes, speakers, manifest
    )
    # Original2720 gives exactly one Bovis Rockwool; native2712 asks to deliver
    # that wool and the real3281 reply acknowledges receipt. This is explicitly
    # reviewed missing-server policy, not a recovered serialized debit command.
    expected = manifest["reviewed_handoff"]
    reward = next(
        r for r in definitions[2720]["cjK"] if r["d"] == expected["source_reward_id"]
    )
    if (
        reward["aeV"] != 5
        or reward["ckl"] != [19660, 1]
        or expected["source_quest_id"] != 2720
    ):
        raise ValueError("Chapter2 wool handoff differs from its native producer")
    payment = dict(
        reference_id=3819,
        action_id=703,
        node_id=3281,
        choice_id=8087,
        item_reference=19660,
        quantity=1,
    )
    if expected["turnin"] != payment or not expected.get("evidence"):
        raise ValueError("Unreviewed Chapter2 wool handoff")
    requirement_from_entry(payment)
    same = [
        r
        for r in result.setdefault("turnins", [])
        if all(
            r[k] == payment[k]
            for k in ("reference_id", "action_id", "node_id", "choice_id")
        )
    ]
    if same and same != [payment]:
        raise ValueError("Chapter2 handoff conflicts with a published payment")
    if not same:
        result["turnins"].append(payment)
    # Keep reviewed item custody separate from the compiler's generated native
    # path guard. Both are checked by the existing terminal offer, while each
    # source declaration remains independently replayable and additive.
    final_requirements = {
        (3281, 8087): (2712, 19660),
        (3282, 8089): (2713, 19665),
        (3285, 8103): (2714, 19665),
    }
    for declaration in manifest["speakers"]:
        placement = next(
            p
            for p in result["placements"]
            if p["row"]["actor_id"] == declaration["actor_id"]
        )
        entry = declaration["objectives"][0]
        quest, reference = final_requirements[entry["node_id"], entry["choice_id"]]
        if entry["quest_id"] != quest:
            raise ValueError("Final Chapter2 item custody differs from its source")
        guard = dict(
            node_id=entry["node_id"],
            choice_id=entry["choice_id"],
            criterion=f"IsAchievementRunning({quest}) && GetItemQuantity({reference}) >= 1",
            evidence=expected["evidence"],
        )
        if guard not in placement.setdefault("choice_criteria", []):
            placement["choice_criteria"].append(guard)
    # Preserve physical Magnum and its source attestation while making the
    # already selected quest overlay available for the new genuine branch.
    placement = next(
        p for p in result["placements"] if p["row"]["actor_id"] == -1724034232352753
    )
    if (
        placement["existing_native_actor"]["source_sha256"]
        != expected["native_actor_source_sha256"]
    ):
        raise ValueError("Original Magnum actor source changed")
    if 2712 not in placement["existing_native_actor"]["quest_ids"]:
        placement["existing_native_actor"]["quest_ids"].append(2712)
    return result
