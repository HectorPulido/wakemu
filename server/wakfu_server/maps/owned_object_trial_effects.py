"""Normal native effect adapters for declared owned object challenges."""

import struct

from wakfu_server.achievements import storage
from wakfu_server import owned_story_mechanics


class Packets(list):
    def __init__(self):
        super().__init__()
        self.presentation_due_ms = 0


def executor(selected):
    def apply(db, store, character, effects):
        packets = Packets()
        for effect in effects:
            kind = effect.get("kind")
            if kind == "scenario_event":
                native = owned_story_mechanics.sources(selected)
                identity = str(effect["event"])
                signature = native.get("event_signatures", {}).get(identity)
                if effect["scenario"] != native["scenario_id"] or signature is None:
                    raise ValueError(
                        "Trial event lacks its original installed Lua signature"
                    )
                arguments = [
                    character["id"] if value == "owner" else value
                    for value in effect.get("arguments", ())
                ]
                if len(arguments) != signature["argument_count"] or any(
                    type(value) is not int or not -(2**63) <= value < 2**63
                    for value in arguments
                ):
                    raise ValueError("Trial event arguments differ from original Lua")
                if signature.get("presentation") is True:
                    from wakfu_server.achievements import tutorial_presentation_once

                    state = storage.load_locked(db, character["id"])
                    quest_id = selected.get("story_quest_id")
                    if quest_id is not None and (
                        quest_id not in state["running"]
                        or quest_id in state["completed"]
                    ):
                        continue
                    if not tutorial_presentation_once.claim(
                        db, character["id"], effect["scenario"], effect["event"]
                    ):
                        continue
                    packets.presentation_due_ms = max(
                        packets.presentation_due_ms,
                        int(store.now().timestamp() * 1000) + signature["duration_ms"],
                    )
                packets.append(
                    (
                        13411,
                        struct.pack(
                            ">BiiB",
                            0,
                            effect["event"],
                            effect["scenario"],
                            len(arguments),
                        )
                        + b"".join(struct.pack(">q", value) for value in arguments),
                    )
                )
            elif kind == "quest_objective":
                from wakfu_server.achievements.owned_quest_encounters import _advance
                from wakfu_server.achievements.mission_progress import (
                    ObjectivePrerequisiteUnavailable,
                )

                state = storage.load_locked(db, character["id"])
                if (
                    effect["quest_id"] not in state["running"]
                    or effect["quest_id"] in state["completed"]
                ):
                    continue
                try:
                    earned = _advance(
                        db,
                        store,
                        character,
                        dict(quest_id=effect["quest_id"]),
                        effect["objective_id"],
                        f'owned-object-objective:{selected["id"]}:{character["instance_id"]}:{effect["objective_id"]}',
                        dict(
                            policy=selected["id"], instance_id=character["instance_id"]
                        ),
                    )
                except ObjectivePrerequisiteUnavailable:
                    # Content-only attempts remain mechanical successes; a
                    # missing prior hand-in never grants this story objective.
                    continue
                packets.extend(earned)
            elif kind == "information":
                from wakfu_server.ecology_feedback import information

                text = effect["text"]
                if isinstance(text, list):
                    if any(type(part) not in (str, int) for part in text):
                        raise ValueError(
                            "Trial information contains an unresolved server fact"
                        )
                    text = "".join(map(str, text))
                if not isinstance(text, str):
                    raise ValueError(
                        "Trial information must be native text or resolved progress"
                    )
                packets.append(information(text))
            elif kind == "inventory_transfer":
                # The signed declaration qualifies outputs; the client supplies
                # only its native object action, never item IDs or quantities.
                transfer = {
                    key: effect[key] for key in ("reference", "quantity", "direction")
                }
                if transfer not in selected.get("allowed_item_transfers", ()):
                    raise ValueError(
                        "Trial inventory transfer lacks its native declaration"
                    )
                if transfer["direction"] == "give":
                    from wakfu_server.achievements.rewards import _item

                    packets.extend(
                        _item(
                            db,
                            store,
                            character,
                            transfer["reference"],
                            transfer["quantity"],
                        )
                    )
                elif transfer["direction"] == "take":
                    from wakfu_server.native_generic_rewards import _payment

                    _, rows, _ = _payment(
                        db,
                        store,
                        character,
                        dict(
                            group_cod=transfer["reference"],
                            group_coe=transfer["quantity"],
                        ),
                    )
                    packets.extend(rows)
                else:
                    raise ValueError("Invalid trial inventory transfer direction")
            elif kind == "relocate":
                # The reducer resolves failure_cell only from the server's
                # authenticated accepted path; normal native-floor CAS applies.
                packets.append(
                    owned_story_mechanics.move(db, character, effect["position"])
                )
            elif kind == "element_state":
                from wakfu_server import owned_story_controller

                packets.extend(
                    owned_story_controller.element_packets(
                        dict(
                            selected,
                            initial_elements=[],
                            steps=[dict(id="trial-state", effects=[effect])],
                        ),
                        {"trial-state"},
                    )
                )
            elif kind == "story_event":
                from wakfu_server import owned_story_controller

                if (
                    set(effect) != {"kind", "reference"}
                    or type(effect["reference"]) is not int
                    or effect["reference"] <= 0
                    or not any(
                        effect in trial["effects"]["success"]
                        for trial in selected["trials"]
                    )
                ):
                    raise ValueError(
                        "Story trial event lacks its declared success edge"
                    )
                story, completed = owned_story_controller._scope(db, store, character)
                outcome = owned_story_controller._settle(
                    db,
                    store,
                    character,
                    story,
                    completed,
                    kind="trial_success",
                    reference=effect["reference"],
                    evidence=dict(
                        trial_policy=selected["id"],
                        instance_id=character["instance_id"],
                    ),
                    apply_effects=owned_story_mechanics.executor(story),
                )
                packets.extend(outcome["packets"])
            else:
                raise ValueError("Unsupported declared object trial effect")
        return packets

    return apply
