"""Native item, transport, collision and presentation effects for owned stories.

The immutable configuration pins a bounded typed source extraction. This does
not scan catalogs or invent item outputs: native table resolution, inventory
wire, objective settlement and position compare-and-set use normal adapters.
"""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import secrets
import struct
from types import SimpleNamespace

from wakfu_server import owned_story_controller as controller


@lru_cache(maxsize=16)
def _sources(path, digest):
    root = Path(__file__).with_name("owned_story_profiles")
    if Path(path).name != path or not path.endswith(".json"):
        raise ValueError("Owned story native sources escape the reviewed directory")
    raw = (root / path).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Owned story native source attestation changed")
    result = json.loads(raw)
    if result.get("schema") != "owned-story-native-sources-v1":
        raise ValueError("Unsupported owned story native source schema")
    from wakfu_server import world_static

    native = {row["id"]: row for row in world_static.objects(result["map_id"])}
    for row in result["objects"]:
        actual = native.get(row["id"])
        if actual is None or any(
            actual.get(key) != row[key]
            for key in ("map_id", "type", "x", "y", "z", "payload_hex", "chunk", "auto")
        ):
            raise ValueError("Owned story source differs from the installed native map")
    for identity, approaches in result.get("interaction_approaches", {}).items():
        from wakfu_server import owned_story_generic_entry

        original = native.get(int(identity))
        if original is None:
            raise ValueError("Pinned native approaches name an absent map object")
        owned_story_generic_entry.validate_approaches(original, approaches)
    # Older reviewed source bundles carry one descriptor beside its exact
    # source, rather than in the shared program index. Normalize that shape
    # only after the pinned object and its native parameter agree.
    result.setdefault("programs", {})
    result.setdefault("native_scripts", {})
    result.setdefault("scenes", {})
    clue = result.get("reviewed_clue_source")
    if clue is not None:
        source, descriptor = clue["source"], clue["descriptor"]
        actual = native.get(source["id"])
        if actual is None or any(
            actual.get(key) != source[key]
            for key in ("map_id", "type", "x", "y", "z", "payload_hex", "chunk", "auto")
        ):
            raise ValueError("Reviewed story descriptor differs from its native source")
        payload = bytes.fromhex(source["payload_hex"])
        length = struct.unpack_from(">i", payload, 33)[0]
        if not 0 < length <= 64 or 37 + length > len(payload):
            raise ValueError(
                "Reviewed story source lacks its native descriptor parameter"
            )
        parameter = payload[37 : 37 + length].decode("ascii")
        if (
            source["type"] != "GenericActivableInteractiveElement"
            or str(descriptor["descriptor_id"]) != parameter
            or str(source["descriptor_id"]) != parameter
            or source["native_parameters"] != parameter
        ):
            raise ValueError("Reviewed story source lost its native descriptor")
        key = str(source["id"])
        if key in result["programs"] and result["programs"][key] != descriptor:
            raise ValueError(
                "Reviewed story descriptor conflicts with its program index"
            )
        result["programs"][key] = descriptor
    return result


def sources(selected):
    pin = selected.get("native_sources")
    if pin is None:
        raise ValueError("Owned story mechanics lack typed native sources")
    result = _sources(pin["path"], pin["sha256"])
    if result["map_id"] != selected["map_id"]:
        raise ValueError("Owned story native sources belong to another map")
    if selected.get("emote_triggers") is not None:
        from wakfu_server import owned_story_emotes
        from wakfu_server.combat_geometry import published_geometry

        owned_story_emotes.validate_sources(
            selected, result, published_geometry(selected["map_id"])
        )
    if selected.get("native_links") is not None:
        from wakfu_server import owned_story_native_links

        owned_story_native_links.validate_sources(selected, result)
    steps = selected.get("steps")
    if steps is None:
        from wakfu_server import owned_object_trials

        if (
            owned_object_trials.policy(
                dict(topology=dict(owned_object_trials=selected))
            )
            is None
        ):
            raise ValueError("Native source profile lacks its actual effect policy")
        steps = ()
    for step in steps:
        for effect in step["effects"]:
            if effect["kind"] == "native_item_gate":
                from wakfu_server import owned_story_item_gates

                owned_story_item_gates.validate(selected, effect, result)
            if effect["kind"] == "reviewed_item_grant":
                from wakfu_server import owned_story_reviewed_items

                owned_story_reviewed_items.validate(selected, effect, result)
            if effect["kind"] == "native_state":
                from wakfu_server.owned_story_gameplay_states import validate_descriptor

                validate_descriptor(
                    result.get("marker_states", {}).get(str(effect["state_id"])),
                    effect["state_id"],
                )
    return result


def allowed(db, store, character, expression):
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server.dungeon_criteria import evaluate

    state = storage.load_locked(db, character["id"])
    from wakfu_server.owned_story_gameplay_states import has_state

    def is_hero():
        roster = db.execute(
            "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
            (character["account_id"],),
        ).fetchone()
        return roster is not None and roster["leader_id"] != character["id"]

    queries = dict(
        queries_from_state(state),
        HasState=lambda reference: has_state(character, reference),
        IsHero=is_hero,
    )
    return evaluate(
        store,
        expression,
        character=character,
        queries=queries,
        now_ms=int(store.now().timestamp() * 1000),
    )


def event_scenario(native, event):
    """Resolve one attested event while keeping mixed original Lua programs."""
    scenario = native.get("scenario_bindings", {}).get(
        str(event), native["scenario_id"]
    )
    if (
        type(scenario) is not int
        or scenario <= 0
        or event not in native["scenario_events"]
    ):
        raise ValueError("Owned story event lacks an installed Lua binding")
    return scenario


def scenario_packet(selected, event, arguments=()):
    native = sources(selected)
    if event not in native["scenario_events"]:
        raise ValueError("Owned story scenario event is absent from installed Lua")
    signature = native.get("event_signatures", {}).get(
        str(event), native["scenes"].get(str(event))
    )
    expected = (
        0
        if signature is None
        else signature
        if type(signature) is int
        else signature["argument_count"]
    )
    if len(arguments) != expected or any(
        type(value) is not int or not -(2**63) <= value < 2**63
        for value in arguments
    ):
        raise ValueError("Owned story scenario arguments differ from native Lua")
    return 13411, struct.pack(
        ">BiiB", 0, event, event_scenario(native, event), len(arguments)
    ) + b"".join(struct.pack(">q", value) for value in arguments)


def _arguments(db, character, effect, selected, *, store=None):
    native = sources(selected)
    roles = native.get("argument_sources", {}).get(str(effect["event"]), {})
    result = []
    for role in effect.get("arguments", ()):
        if type(role) is int and role == 0:
            result.append(0)
        elif role == "owner":
            result.append(character["id"])
        elif role == "source_object":
            # The source must be the native artifact chest for this literal Lua
            # signature, never an actor identity supplied by the client.
            if type(roles.get("source_object")) is not int:
                raise ValueError("Source-object cinematic argument is unqualified")
            result.append(roles["source_object"])
        elif role == "boss_trigger":
            if type(roles.get("boss_trigger")) is not int:
                raise ValueError("Boss trigger cinematic argument is unqualified")
            result.append(roles["boss_trigger"])
        elif isinstance(role, str) and role.startswith("story_npc:"):
            reference = roles.get("story_npcs", {}).get(role)
            if (
                type(reference) is not int
                or reference <= 0
                or role != f"story_npc:{reference}"
            ):
                raise ValueError("Owned scenario NPC argument is not source-qualified")
            from wakfu_server.owned_story_npcs import argument_actor

            identity = argument_actor(db, store, character, reference)
            from wakfu_server import npc_world

            if (
                type(identity) is not int
                or not npc_world.MIN_ID <= identity <= npc_world.MAX_ID
            ):
                raise ValueError("Owned scenario NPC has no actual scoped actor")
            result.append(identity)
        elif isinstance(role, str) and role.startswith("story_target:"):
            target = roles.get("story_targets", {}).get(role)
            if type(target) is not int or role != f"story_target:{target}":
                raise ValueError("Owned scenario NPC target is not source-qualified")
            from wakfu_server import owned_story_npcs

            result.append(
                owned_story_npcs.argument_target(db, store, character, target)
            )
        elif isinstance(role, str) and role.startswith("scene_actor:"):
            from wakfu_server.owned_story_admission import scene_actor_rows

            matches = [
                row
                for row in scene_actor_rows(db, store, character)
                if "scene_actor:" + row["role"] == role
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Native scenario has no genuine scoped render-only actor"
                )
            result.append(matches[0]["actor_id"])
        elif isinstance(role, str) and role.startswith("room_actor:"):
            source = roles.get("room_actors", {}).get(role)
            if (
                not isinstance(source, dict)
                or set(source) != {"room_order", "index", "reference"}
                or type(source["room_order"]) is not int
                or source["room_order"] <= 0
                or type(source["index"]) is not int
                or source["index"] < 0
                or type(source["reference"]) is not int
                or source["reference"] <= 0
                or role != f'room_actor:{source["room_order"]}:{source["index"]}'
            ):
                raise ValueError("Owned scenario room actor role is unqualified")
            spawned = db.execute(
                "SELECT g.members,g.status,r.asset_map_id FROM dungeon_room_spawn_receipts r "
                "JOIN combat_groups g ON g.map_id=r.asset_map_id "
                "AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
                "WHERE r.instance_id=%s AND r.room_order=%s",
                (character["instance_id"], source["room_order"]),
            ).fetchone()
            members = [] if spawned is None else spawned["members"]
            index = source["index"]
            if (
                spawned is None
                or spawned["asset_map_id"] != selected["map_id"]
                or spawned["status"] not in ("available", "fighting", "defeated")
                or not isinstance(members, list)
                or index >= len(members)
                or members[index].get("ref") != source["reference"]
                or type(members[index].get("id")) is not int
                or members[index]["id"] >= 0
            ):
                raise ValueError("Owned scenario lacks its actual native room actor")
            result.append(members[index]["id"])
        elif role == "boss_actor":
            actor_source = native.get("actor_sources", {}).get(role)
            if actor_source is None:
                raise ValueError(
                    "Owned scenario actor role lacks its original formation"
                )
            row = db.execute(
                "SELECT g.members FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
                "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
                "WHERE r.instance_id=%s AND r.room_order=%s",
                (character["instance_id"], actor_source["room_order"]),
            ).fetchone()
            bosses = (
                []
                if row is None
                else [
                    m["id"]
                    for m in row["members"]
                    if m["ref"] == actor_source["reference"]
                ]
            )
            if len(bosses) != 1:
                raise ValueError("Owned boss scene lacks its actual native fighter")
            result.append(bosses[0])
        else:
            raise ValueError("Unknown owned scenario argument role")
    return result


def move(db, character, position, *, direction=3):
    if (
        not isinstance(position, (tuple, list))
        or len(position) != 3
        or any(type(value) is not int for value in position)
        or type(direction) is not int
        or not 0 <= direction < 8
    ):
        raise ValueError("Malformed owned native relocation")
    from wakfu_server import dungeon_runtime

    _, configuration = dungeon_runtime.configuration_for_instance(
        db, character["instance_id"]
    )
    geometry = configuration["topology"]["exploration_geometry"]
    # Callers additionally bind the target to the native program or Lua. This
    # guard prevents a reviewed action from putting an actor off its real floor.
    if tuple(position) not in set(map(tuple, geometry["cells"])):
        raise ValueError("Owned native relocation has no published map surface")
    previous = tuple(character[key] for key in ("x", "y", "z"))
    updated = db.execute(
        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s "
        "AND map_id=%s AND instance_id=%s AND x=%s AND y=%s AND z=%s",
        (
            *position,
            character["id"],
            character["account_id"],
            character["map_id"],
            character["instance_id"],
            *previous,
        ),
    )
    if updated.rowcount != 1:
        raise ValueError("Owned native relocation lost its committed position")
    character.update(zip(("x", "y", "z"), position))
    return 13530, struct.pack(">qiihBi", character["id"], *position, direction, -1)


def _visit_artifact_guard(character, selected, native, table, expression):
    """Keep a required native puzzle artifact available after story completion.

    Only deterministic items required by the pinned nonconsuming internal
    transports qualify. Currency, random drops and ordinary story rewards do
    not borrow this mechanical exception.
    """
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )

    quest = selected["admission"]["continuation_quest_id"]
    if expression != f"not IsAchievementComplete({quest})":
        return False
    required = {}
    for transfer in selected.get("native_transfers", ()):
        for group in (
            native["programs"].get(str(transfer["source_id"]), {}).get("groups", ())
        ):
            if group.get("cof") is False and group.get("cod", 0) > 0:
                required[group["cod"]] = max(
                    required.get(group["cod"], 0), group["coe"]
                )
    entries = table.get("gBN", ())
    return bool(entries) and all(
        row.get("aAi") in required
        and row.get("cmY") == 1.0
        and row.get("cqy") == row.get("cqz") == 1
        and row.get("czk") == expression
        and not row.get("gBO")
        and complete_owned_item_quantity(character, (row["aAi"],))
        < required[row["aAi"]]
        for row in entries
    )


def _loot(db, store, character, selected, table_id):
    from wakfu_server.random_item_actions import draw_products
    from wakfu_server.achievements import rewards

    native = sources(selected)

    def lookup(reference):
        table = native["loot_tables"].get(str(reference))
        if table is None:
            raise ValueError("Owned story loot table was not explicitly frozen")
        return table

    products = draw_products(
        table_id,
        lookup,
        SimpleNamespace(randbelow=secrets.randbelow),
        entry_allowed=lambda expression: allowed(db, store, character, expression)
        or _visit_artifact_guard(
            character, selected, native, lookup(table_id), expression
        ),
    )
    packets = []
    for reference, quantity in sorted(products.items()):
        packets.extend(rewards._item(db, store, character, reference, quantity))
    return packets


def native_transfer(db, store, character, selected, source_id, effect_reference):
    from wakfu_server.exploration_artifact_actions import _teleport, _script_packet
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )
    from wakfu_server.native_generic_rewards import _payment

    native = sources(selected)
    program = native["programs"].get(str(source_id))
    candidates = (
        []
        if program is None
        else [
            (group, action, effect)
            for group in program["groups"]
            for action in group["actions"]
            for effect in action["effects"]
            if effect["effect_type"] == 3
            and effect["action_reference"] == effect_reference
        ]
    )
    if len(candidates) != 1:
        raise ValueError("Owned story travel has no exact native program")
    group, action, effect = candidates[0]
    if (
        action["wire_action"] != 0
        or action["raw_cob"] != 1.0
        or group["cnd"] != 0
        or group["cog"] != 0
        or not allowed(db, store, character, action["criterion"])
        or not allowed(db, store, character, effect["criterion"])
    ):
        raise ValueError("Owned story travel failed its actual native access rule")
    packets = []
    if group["cod"]:
        if complete_owned_item_quantity(character, (group["cod"],)) < group["coe"]:
            raise ValueError("Owned story travel requires its actual native artifact")
        if group["cof"] is True:
            _, payment_packets, _ = _payment(
                db,
                store,
                character,
                dict(group_cod=group["cod"], group_coe=group["coe"]),
            )
            packets.extend(payment_packets)
        elif group["cof"] is not False:
            raise ValueError(
                "Owned story travel has an invalid native consumption flag"
            )
    target, direction, delay_ms = _teleport(effect)
    if target["map_id"] != character["map_id"] or delay_ms:
        raise ValueError(
            "Owned story internal travel must retain its native asset and immediate deadline"
        )
    for visual in action["effects"]:
        proof = native["native_scripts"].get(str(visual["action_reference"]))
        if (
            proof
            and proof["present"]
            and allowed(db, store, character, visual["criterion"])
        ):
            packets.append(
                _script_packet(character["id"], source_id, visual["action_reference"])
            )
    packets.append(
        move(db, character, [target[k] for k in ("x", "y", "z")], direction=direction)
    )
    return packets


class MechanicPackets(list):
    """Wire packets plus exact skipped scenes requiring mechanical completion."""

    def __init__(self):
        super().__init__()
        self.skipped_scenes = set()
        self.suppressed_presentations = False
        self.presentation_delivered = False


def _presentation_claim(db, character, selected, native, effect):
    """Deduplicate actual scenes/guides, never native mechanical events."""
    from wakfu_server.achievements import tutorial_presentation_once

    identity = (effect["scenario"], effect["event"])
    groups = [
        group
        for group in native.get("presentation_groups", ())
        if effect["event"] in group["events"]
    ]
    if len(groups) > 1:
        raise ValueError("Native presentation belongs to multiple groups")
    # Reviewed source metadata classifies presentation independently of its
    # scenario number. Unlisted Lua events remain mechanical and repeatable.
    guide = native.get("guides", {}).get(str(effect["event"]))
    if guide is None:
        guide = {(1722, 14199): 173}.get(identity)
    if guide is not None and (type(guide) is not int or guide <= 0):
        raise ValueError("Owned story guide lacks its actual native identity")
    scene = str(effect["event"]) in native["scenes"]
    # Native14244 only focuses the camera/particle for the room2 exit (6s).
    camera = identity == (1722, 14244) or effect["event"] in native.get(
        "presentations", ()
    )
    if guide is None and not scene and not camera and not groups:
        return True
    if guide is None:
        from wakfu_server.achievements import storage

        state = storage.load_locked(db, character["id"])
        required = native.get("presentation_quests", {}).get(str(effect["event"]))
        if required is not None:
            if type(required) is not int or required <= 0:
                raise ValueError("Native presentation has an invalid quest identity")
            if required not in set(state["running"]) - set(state["completed"]):
                return False
        admission = selected["admission"]
        from wakfu_server.owned_story_entry_variants import quest_ids

        assigned = quest_ids(admission)
        if not (assigned & set(state["running"]) - set(state["completed"])):
            # A content visit does not consume the first later story viewing.
            return False
    if groups:
        return tutorial_presentation_once.claim_group_event(
            db, character, groups[0], *identity
        )
    steps = [step for step in selected["steps"] if effect in step["effects"]]
    legacy = tuple(
        dict(
            prefix=f'owned-story:{selected["id"]}:',
            payload=dict(
                schema=controller.SCHEMA, owner=character["id"], step=step["id"]
            ),
            exclude_payload=dict(presentation_suppressed=True),
        )
        for step in steps
    )
    if guide is not None:
        return tutorial_presentation_once.claim_guide(
            db, character["id"], guide, legacy=legacy
        )
    return tutorial_presentation_once.claim(
        db, character["id"], *identity, legacy=legacy
    )


def executor(selected):
    """Bind the trusted normal native adapters for the pinned declared story."""

    def apply(db, store, character, effects):
        packets = MechanicPackets()
        for effect in effects:
            kind = effect["kind"]
            if kind == "scenario_event":
                if effect["scenario"] != event_scenario(
                    sources(selected), effect["event"]
                ):
                    raise ValueError(
                        "Owned story event belongs to another installed Lua script"
                    )
                native = sources(selected)
                if not _presentation_claim(db, character, selected, native, effect):
                    packets.suppressed_presentations = True
                    if str(effect["event"]) in native["scenes"]:
                        packets.skipped_scenes.add(effect["event"])
                    continue
                if any(
                    isinstance(role, str) and role.startswith("scene_actor:")
                    for role in effect.get("arguments", ())
                ):
                    from wakfu_server.owned_story_admission import scene_actor_packets

                    packets.extend(scene_actor_packets(db, store, character))
                packets.append(
                    scenario_packet(
                        selected,
                        effect["event"],
                        _arguments(db, character, effect, selected, store=store),
                    )
                )
                if (
                    str(effect["event"]) in native["scenes"]
                    or effect["event"] in native.get("presentations", ())
                    or str(effect["event"]) in native.get("guides", {})
                    or any(
                        effect["event"] in group["events"]
                        for group in native.get("presentation_groups", ())
                    )
                    or (effect["scenario"], effect["event"])
                    in ((1722, 14199), (1722, 14244))
                ):
                    packets.presentation_delivered = True
            elif kind == "element_state":
                projection = dict(
                    selected,
                    initial_elements=[],
                    steps=[dict(id="effect", effects=[effect])],
                )
                packets.extend(controller.element_packets(projection, {"effect"}))
            elif kind == "context_refresh":
                packets.refresh_context = True
            elif kind == "native_state":
                from wakfu_server import owned_story_gameplay_states

                packets.extend(
                    owned_story_gameplay_states.apply(
                        db, store, character, selected, effect
                    )
                )
            elif kind == "native_item_gate":
                from wakfu_server import owned_story_item_gates

                packets.extend(
                    owned_story_item_gates.apply(db, store, character, selected, effect)
                )
            elif kind == "reviewed_item_grant":
                from wakfu_server import owned_story_reviewed_items

                packets.extend(
                    owned_story_reviewed_items.apply(
                        db, store, character, selected, effect
                    )
                )
            elif kind == "native_loot":
                if "source_id" in effect:
                    native = sources(selected)
                    program = native["programs"].get(str(effect["source_id"]))
                    choices = (
                        []
                        if program is None
                        else [
                            (group, action, item)
                            for group in program["groups"]
                            for action in group["actions"]
                            for item in action["effects"]
                            if item["effect_type"] == 4
                            and item["action_reference"] == effect["effect_reference"]
                            and item["parameters"] == [str(effect["table_id"])]
                        ]
                    )
                    if len(choices) != 1:
                        raise ValueError(
                            "Story loot lost its actual source's native table effect"
                        )
                    group, action, item = choices[0]
                    if not allowed(
                        db, store, character, action["criterion"]
                    ) or not allowed(db, store, character, item["criterion"]):
                        continue
                packets.extend(
                    _loot(db, store, character, selected, effect["table_id"])
                )
            elif kind == "native_transfer":
                packets.extend(
                    native_transfer(
                        db,
                        store,
                        character,
                        selected,
                        effect["source_id"],
                        effect["effect_reference"],
                    )
                )
            elif kind == "stage_position":
                native = sources(selected)
                declaration = native.get("reviewed_stage_positions", {}).get(
                    str(effect["event"])
                )
                if (
                    not isinstance(declaration, dict)
                    or set(declaration) != {"position", "authority"}
                    or declaration["position"] != effect["position"]
                    or not declaration["authority"]
                    or effect["event"] not in native["scenario_events"]
                ):
                    raise ValueError(
                        "Owned stage relocation lacks its reviewed native floor declaration"
                    )
                packets.append(move(db, character, effect["position"]))
            elif kind == "scene_position":
                native = sources(selected)
                if (
                    effect["scenario"] != native["scenario_id"]
                    or native.get("scene_positions", {}).get(str(effect["event"]))
                    != effect["position"]
                ):
                    raise ValueError(
                        "Owned scene relocation differs from installed Lua"
                    )
                packets.append(move(db, character, effect["position"]))
            elif kind == "quest_objective":
                from wakfu_server.achievements import storage
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
                    earned_packets = _advance(
                        db,
                        store,
                        character,
                        dict(quest_id=effect["quest_id"]),
                        effect["objective_id"],
                        f'owned-story-objective:{selected["id"]}:{character["instance_id"]}:{effect["objective_id"]}',
                        dict(
                            policy=selected["id"], instance_id=character["instance_id"]
                        ),
                    )
                except ObjectivePrerequisiteUnavailable:
                    # Physical practice remains usable before its story stage.
                    # This skip grants no credit or reward and consumes no
                    # objective receipt. Malformed native effects still fail.
                    continue
                packets.extend(earned_packets)
            else:
                raise ValueError("Unsupported owned story native mechanic")
        return packets

    return apply


def pending_reset(db, character):
    """Read one durable, unconsumed native fall timer for the current owner."""
    prefix = f'owned-story-trap-fall:{character["instance_id"]}:'
    row = db.execute(
        "SELECT e.event_key,e.payload FROM character_achievement_events e "
        "WHERE e.character_id=%s AND left(e.event_key,%s)=%s AND NOT EXISTS("
        "SELECT 1 FROM character_achievement_events done WHERE done.character_id=e.character_id "
        "AND done.event_key='owned-story-trap-reset:' || e.event_key) "
        "ORDER BY e.created_at,e.event_key LIMIT 1",
        (character["id"], len(prefix), prefix),
    ).fetchone()
    if row is None:
        return None
    data = row["payload"]
    if (
        data.get("owner") != character["id"]
        or data.get("instance_id") != character["instance_id"]
        or type(data.get("reset")) is not dict
        or type(data["reset"].get("due_ms")) is not int
    ):
        raise ValueError("Native fall timer differs from the current owned story")
    return row


def complete_reset(db, store, character, selected):
    """Move through the owned registry only after the native1600ms fall timer."""
    receipt = pending_reset(db, character)
    if (
        receipt is None
        or int(store.now().timestamp() * 1000) < receipt["payload"]["reset"]["due_ms"]
    ):
        return []
    reset = receipt["payload"]["reset"]
    trap = selected.get("trap_cycle")
    if (
        trap is None
        or reset["position"] != trap["reset_position"]
        or reset["scenario"] != trap["scenario"]
        or reset["native_event"] != trap["fall_event"]
        or reset["delay_ms"] != trap["fall_animation_ms"]
    ):
        raise ValueError("Native fall reset differs from the frozen trap cycle")
    packets = [move(db, character, reset["position"])]
    from wakfu_server.achievements import storage

    if not storage.record_event(
        db,
        character["id"],
        "owned-story-trap-reset:" + receipt["event_key"],
        dict(
            owner=character["id"],
            instance_id=character["instance_id"],
            source=receipt["event_key"],
            reset_position=reset["position"],
        ),
    ):
        raise ValueError("Native fall reset raced its position commit")
    return packets


def authorize_action(db, store, character, selected, source_id, action_id):
    """Honor the literal offered native action, including system configuration."""
    native = sources(selected)
    descriptor = native["programs"].get(str(source_id))
    actions = (
        []
        if descriptor is None
        else [
            action
            for group in descriptor["groups"]
            for action in group["actions"]
            if action["wire_action"] == action_id
        ]
    )
    if len(actions) != 1 or actions[0]["raw_cob"] != 1.0:
        raise ValueError("Owned story action has no unique native descriptor")
    if not allowed(db, store, character, actions[0]["criterion"]):
        raise ValueError(
            "Owned story action is unavailable in the native system configuration"
        )
    return actions[0]


def object_visuals(db, store, character, selected, source_id, action_id):
    """Keep native default feedback when a story objective has not unlocked."""
    from wakfu_server.exploration_artifact_actions import _script_packet

    native = sources(selected)
    action = authorize_action(db, store, character, selected, source_id, action_id)
    return [
        _script_packet(character["id"], source_id, effect["action_reference"])
        for effect in action["effects"]
        if effect["effect_type"] == 1
        and native["native_scripts"]
        .get(str(effect["action_reference"]), {})
        .get("present")
        is True
        and allowed(db, store, character, effect["criterion"])
    ]
