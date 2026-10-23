"""Explicit immutable encounter completion reconstruction, using native kill.

Original selectors and self-controller relationships remain unchanged. This
policy supplies only the missing, provenance-qualified helper population.
"""
from copy import deepcopy
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_terminal_cleanup_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
        helpers = (
            [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM encounter_terminal_cleanup_helpers WHERE policy=%s ORDER BY helper_reference",
                    (policy,),
                ).fetchall()
            ]
            if row
            else []
        )
    if row is None:
        raise ValueError("Unknown immutable terminal cleanup policy")
    row = dict(row)
    for key in (
        "monster_references",
        "helper_references",
        "native_parameters",
        "native_effect_flags",
    ):
        row[key] = list(row[key])
    if (
        not row["authority"]
        or not row["helper_references"]
        or row["helper_references"] != sorted(set(row["helper_references"]))
        or [r["helper_reference"] for r in helpers] != row["helper_references"]
        or row["terminal_event"] != 1002
        or row["terminal_channel"] != 60
        or row["effect_family"] != 28
        or row["selector_mask"] != 8
        or row["area_class"] != "anD"
        or len(row["native_parameters"]) != row["parameter_count"] * 2
    ):
        raise ValueError("Invalid immutable terminal cleanup inventory")
    row["helpers"] = helpers
    return row


def _matches(row, effect):
    from .combat_encounter_owned_start_binding import _same_sequence

    return (
        effect is not None
        and effect.get("effect_class") == row["effect_family"]
        and effect.get("native_target_selector")
        == {"class": "fcE", "mask": row["selector_mask"]}
        and effect.get("area_class") == row["area_class"]
        and effect.get("criteria") == row["criterion"]
        and effect.get("parameter_count") == row["parameter_count"]
        and effect.get("native_execution_mode") == row["native_execution_mode"]
        and _same_sequence(effect.get("parameters"), row["native_parameters"])
        and _same_sequence(
            effect.get("native_effect_flags"), row["native_effect_flags"]
        )
        and not effect.get("children")
    )


def terminal_cleanup_from_record(record):
    from .combat_encounter_owned_start_binding import _same_record

    if record is not None and (
        not isinstance(record, dict)
        or not _same_record(record, _version(record.get("policy")))
    ):
        raise ValueError("Frozen terminal cleanup policy changed")
    return record


def freeze_terminal_cleanup_policy(fight, *, roles):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    if hasattr(fight, "native_encounter_terminal_cleanup_policy"):
        row = terminal_cleanup_from_record(
            fight.native_encounter_terminal_cleanup_policy
        )
    else:
        if fight.phase != "placement":
            raise ValueError("Terminal cleanup must freeze at admission")
        with _database().connection() as db:
            active = db.execute(
                "SELECT policy FROM encounter_terminal_cleanup_active WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        row = None if active is None else deepcopy(_version(active["policy"]))
    if row is not None:
        if (
            row["map_id"] != roles.map_id
            or row["monster_references"] != list(roles.monster_references)
            or row["catalog_revision"] != native_catalog.release()
        ):
            raise ValueError("Terminal cleanup differs from admission or catalog")
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json",
            "effects",
            row["cleanup_effect_reference"],
        )
        direct = native_catalog.record(
            DATA_ROOT / "native-direct-target-policies.json",
            "effects",
            row["cleanup_effect_reference"],
        )
        if not _matches(row, effect) or direct != [28, False, False]:
            raise ValueError("Terminal cleanup differs from original kill authority")
        for helper in row["helpers"]:
            creator = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json",
                "effects",
                helper["creator_effect_reference"],
            )
            if (
                not creator
                or creator.get("effect_class") != 307
                or creator.get("parameters", [None])[0] != helper["helper_reference"]
            ):
                raise ValueError("Terminal helper differs from original birth program")
    fight.native_encounter_terminal_cleanup_policy = deepcopy(row)
    return deepcopy(row)


def prepare_terminal_cleanup(fight, frozen):
    """Pure plan from committed journals and native birth/KO lineage.

    It also qualifies an explicitly authorized post-KO policy transition; it
    never freezes an active pointer or supplies synthetic END/death events.
    """
    from .combat_encounter_roles import frozen_roles
    from .combat_summon_retirement import _registration

    frozen = terminal_cleanup_from_record(frozen)
    if frozen is None:
        return None
    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Terminal cleanup role scope mismatch")
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    bosses = [
        a
        for a in fight.actors.values()
        if receipts.get(a.id, {}).get("ref") == frozen["boss_reference"]
    ]
    if len(bosses) != 1:
        raise ValueError("Terminal cleanup requires one original boss")
    boss = bosses[0]
    if boss.hp > 0:
        return None
    receipt = receipts[boss.id]
    if (
        boss.controlled
        or boss.team != roles.npc_team
        or receipt.get("initialized") is not True
        or not any(
            r.get("state_id") == frozen["boss_constructor_state"]
            for r in receipt.get("resolved_states", ())
        )
        or not all(
            any(s.reference == ref for s in boss.state_ledger.entries)
            for ref in (frozen["boss_phase_state"], frozen["success_state"])
        )
    ):
        raise ValueError("Terminal cleanup lacks original successful boss state")
    extra = max(
        (
            s.level
            for s in boss.state_ledger.entries
            if s.reference == frozen["extension_state"]
        ),
        default=0,
    )
    expected_table = frozen["terminal_table"] + extra
    events = list(fight.events)
    anchors = []
    for index, event in enumerate(events):
        if (
            event.get("kind") != "kill_hp_minimum_update"
            or event.get("effect_class") != 28
            or event.get("target_id") != boss.id
            or event.get("hp") != 0
            or event.get("hp_before", 0) <= 0
        ):
            continue
        previous = next(
            (r for r in reversed(events[:index]) if r.get("kind") == "turn_started"),
            None,
        )
        if previous is None or previous.get("actor_id") != boss.id:
            continue
        turn = previous.get("turn_id")
        owned = getattr(fight, "native_turn_event_deliveries", {}).get(
            f"{turn}:{boss.id}:end", {}
        )
        if owned != dict(
            actor_id=boss.id, turn_id=turn, event_id=1002, phase="end", suppressed=False
        ):
            continue
        calendar = getattr(fight, "native_encounter_post_start_deliveries", {}).values()
        if not any(
            r.get("actor_id") == boss.id
            and r.get("turn_id") == turn
            and r.get("table_turn") == expected_table
            for r in calendar
        ):
            continue
        if not any(
            r.get("kind") == "death"
            and r.get("actor_id") == boss.id
            and r.get("sequence", 0) > event.get("sequence", 0)
            for r in events[index + 1 :]
        ):
            continue
        contexts = [
            r.get("invocation", {}).get("native_trigger_context")
            for r in getattr(fight, "native_owned_group_effects", {}).values()
        ]
        if event.get("generic_effect") == frozen[
            "boss_kill_effect_reference"
        ] and isinstance(event.get("native_container"), dict):
            contexts.append(
                dict(
                    uid=event["uid"],
                    generic_effect=event["generic_effect"],
                    effect_action_id=28,
                    caster_id=event["source_id"],
                    target_id=event["target_id"],
                    native_events_verified=True,
                    native_container=event["native_container"],
                )
            )
        context = next(
            (
                r
                for r in contexts
                if isinstance(r, dict)
                and r.get("uid") == event.get("uid")
                and r.get("generic_effect") == frozen["boss_kill_effect_reference"]
                and r.get("effect_action_id") == 28
                and r.get("caster_id") == event.get("source_id")
                and r.get("target_id") == boss.id
                and r.get("native_events_verified") is True
                and r.get("native_container", {}).get("is_state") is True
                and r.get("native_container", {}).get("state_id")
                == frozen["boss_phase_state"]
            ),
            None,
        )
        caster = fight.actors.get(event.get("source_id"))
        if (
            context is not None
            and caster is not None
            and caster.controlled
            and caster.team == roles.player_team
        ):
            anchors.append(
                dict(
                    turn_id=turn,
                    table_turn=expected_table,
                    boss_id=boss.id,
                    caster_id=caster.id,
                    kill_uid=event["uid"],
                    kill_sequence=event["sequence"],
                )
            )
    if len(anchors) != 1:
        raise ValueError(
            "Terminal cleanup lacks its exact committed native terminal KO"
        )
    anchor = anchors[0]
    targets = []
    helper_map = {r["helper_reference"]: r for r in frozen["helpers"]}
    for actor in fight.actors.values():
        source = getattr(actor, "native_summon_source", None)
        if (
            not isinstance(source, dict)
            or source.get("ref") not in helper_map
            or source.get("caster_id") != boss.id
        ):
            continue
        if actor.hp <= 0:
            continue
        registered, registration, _source, _captured, _copied = _registration(
            fight, actor.id
        )
        authority = registration["authority"]
        if (
            registered is not actor
            or actor.controlled
            or actor.team != roles.npc_team
            or authority.get("native_controller_id") != actor.id
            or authority.get("summon_root_id") != actor.id
        ):
            raise ValueError(
                "Terminal helper differs from original self-controlled birth"
            )
        helper = helper_map[source["ref"]]
        from .combat_retained_summon import retained_summon_actor
        from .combat_effect_removal import _identity_fields
        import struct

        delivery = getattr(fight, "native_summon_creation_deliveries", {}).get(actor.id)
        if not isinstance(delivery, dict) or delivery.get("opcode") != 12613:
            raise ValueError("Terminal helper lacks original native creation delivery")
        wire = bytes.fromhex(delivery["payload_hex"])
        header_size = struct.calcsize(">iiiBih")
        if len(wire) < header_size:
            raise ValueError("Truncated original helper creation delivery")
        fight_id, action_id, observed, execute, family, length = struct.unpack(
            ">iiiBih", wire[:header_size]
        )
        payload = wire[header_size:]
        fields = _identity_fields(payload)
        if (
            fight_id != fight.id
            or action_id <= 0
            or observed != -1
            or execute != 1
            or family != 307
            or length != len(payload)
            or fields.get(3) != helper["creator_effect_reference"]
            or fields.get(4) != helper["helper_reference"]
            or fields.get(6) != boss.id & ((1 << 64) - 1)
            or retained_summon_actor(payload) != actor.id
        ):
            raise ValueError(
                "Terminal helper differs from its declared original creation effect"
            )
        if not any(
            s.reference == helper["constructor_state"]
            for s in actor.state_ledger.entries
        ):
            raise ValueError("Terminal helper lacks its original constructor state")
        targets.append(actor.id)
    phase = next(
        s
        for s in boss.state_ledger.entries
        if s.reference == frozen["boss_phase_state"]
    )
    return dict(
        anchor,
        policy=frozen["policy"],
        phase_state_uid=phase.uid,
        target_ids=sorted(targets),
    )


def deliver_terminal_helper_cleanup(dispatcher):
    from .combat_effect_dispatch import EffectInvocation

    fight = dispatcher.native_retention.fight
    frozen = terminal_cleanup_from_record(
        getattr(fight, "native_encounter_terminal_cleanup_policy", None)
    )
    plan = prepare_terminal_cleanup(fight, frozen)
    if plan is None:
        return ()
    journal = getattr(fight, "native_encounter_terminal_cleanup_deliveries", {})
    key = f"{plan['policy']}:{plan['kill_uid']}"
    if key in journal:
        return ()
    effect = dispatcher.effects.get(str(frozen["cleanup_effect_reference"]))
    if not _matches(frozen, effect):
        raise ValueError("Terminal cleanup execution descriptor changed")
    for identity in plan["target_ids"]:
        actor = fight.actors[identity]
        invocation = EffectInvocation(
            frozen["cleanup_effect_reference"],
            1,
            plan["caster_id"],
            identity,
            tuple(actor.position),
            native_explicit_target=True,
            state_uid=plan["phase_state_uid"],
        )
        if dispatcher.execute(invocation) is not True or fight.actors[identity].hp != 0:
            raise ValueError("Original helper kill did not complete")
    fight.native_encounter_terminal_cleanup_deliveries = {
        **journal,
        key: deepcopy(plan),
    }
    return tuple(plan["target_ids"])
