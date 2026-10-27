"""Source-qualified reconstruction of the original Vengeful Spirit challenge.

Guide175 explicitly grants a Neo Lieutenant/Monk and requires thirteen rounds
and 200,000 damage. Original player state9145 owns book5852 and the timed
410946/411013 terminal. Placement/controller choices are declared Wakemu policy,
not recovered original server callbacks or native summon ownership.
"""
from copy import deepcopy
from collections.abc import Mapping

from .combat_quest_scene_authority import canonical_digest

POLICY = "wakemu-spirit-scenario2710-v1"
SOURCE_PATHS = (
    "monsters.json",
    "combat-state-definitions.json",
    "native-npc-spell-effect-trees.json",
    "native-class-morph-profiles.json",
)


def _published_book():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    book = native_catalog.record(
        DATA_ROOT / "native-class-morph-profiles.json", "profiles", 5852
    )
    if book is None:
        return False  # Older publications have not admitted the original book.
    if not isinstance(book, Mapping) or {
        row["reference"] for row in book.get("abilities", ())
    } != {8485, 8486, 8487, 8488, 8489}:
        raise ValueError("Spirit challenge original player book changed")
    effect = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json", "effects", 410217
    )
    if (
        not isinstance(effect, Mapping)
        or effect.get("effect_class") != 933
        or int(effect["parameters"][0]) != 5852
        or effect.get("criteria") != "IsPlayer()"
    ):
        raise ValueError("Spirit challenge lacks its original player book producer")
    return True


def authorize_spirit_scene(
    store, db, fight, *, account_id, generation, character_id, monster_references
):
    """Admit the real singleton5848 PvE entry and its declared helper manifest.

    Achievement5691 is a reward tier, not an entry quest. Account/session,
    actual map, level96 and the original group identity are authenticated here.
    """
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if manifest is None:
        return None
    from .combat_encounter_scene_helpers import validated_manifest

    source = validated_manifest(manifest)
    if source["policy"] != POLICY:
        return None
    originals = source["originals"]
    if tuple(row["reference"] for row in originals) != (5848,):
        raise ValueError("Spirit challenge does not own its original encounter")
    if sorted(monster_references) not in ([5848], [5848, 5849, 5850]):
        raise ValueError("Spirit challenge actor source differs from its manifest")
    if not _published_book():
        return None
    from wakfu_server.inventory_owner import lock_inventory_character

    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    lock_inventory_character(store, db, account_id, generation, character_id)
    row = db.execute(
        "SELECT c.map_id,c.level,p.team,f.status,f.fight_kind "
        "FROM characters c JOIN combat_fight_participants p "
        "ON p.character_id=c.id AND p.account_id=c.account_id "
        "JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE c.id=%s AND c.account_id=%s AND f.id=%s",
        (character_id, account_id, fight.id),
    ).fetchone()
    if (
        row is None
        or row["level"] < 96
        or row["fight_kind"] != "pve"
        or row["status"] != "placement"
        or fight.phase != "placement"
    ):
        return None
    principal = fight.actors.get(character_id)
    if (
        principal is None
        or not principal.controlled
        or principal.owner_id != account_id
        or source["principal_id"] != character_id
        or source["account_id"] != account_id
        or source["map_id"] != row["map_id"]
        or principal.team != row["team"]
    ):
        raise ValueError("Spirit challenge lost its actual owned entry identity")
    from wakfu_server import native_catalog
    from .combat_encounter_actor_contract import (
        ActorRoleSpec,
        EncounterActorContract,
        freeze_actor_contract,
    )

    contract = freeze_actor_contract(
        fight,
        EncounterActorContract(
            policy=POLICY,
            version=1,
            authority="explicit_source_backed_wakemu_reconstruction",
            map_id=row["map_id"],
            initial_references=(5848,),
            catalog_revision=native_catalog.release(),
            source_paths=SOURCE_PATHS,
            roles=(
                ActorRoleSpec(
                    "boss", 5848, required_initial_states=(9150,), minimum_hp=1
                ),
                ActorRoleSpec(
                    "lieutenant",
                    5849,
                    required_initial_states=(9149, 9169),
                    minimum_hp=1,
                    scene_parent_role="boss",
                ),
                ActorRoleSpec(
                    "monk",
                    5850,
                    required_initial_states=(9169,),
                    minimum_hp=1,
                    scene_parent_role="boss",
                ),
            ),
            terminal_policies=("wakemu-spirit-thirteen-rounds-v1",),
        ),
        map_id=row["map_id"],
        initial_references=(5848,),
    )
    players = sorted(
        identity for identity, actor in fight.actors.items() if actor.controlled
    )
    admitted = dict(
        policy=POLICY,
        authority="explicit_source_backed_wakemu_reconstruction",
        scenario_id=2710,
        guide_id=175,
        victory_page=478,
        helper_page=492,
        fight_id=fight.id,
        map_id=row["map_id"],
        participant_id=character_id,
        account_id=account_id,
        player_ids=players,
        original_reference=5848,
        original_actor_id=originals[0]["id"],
        helper_manifest_digest=manifest["source_digest"],
        admission_digest=contract["admission_digest"],
        grant_state=9145,
        grant_effect=410217,
        morph_profile=5852,
    )
    result = dict(
        source=admitted,
        source_digest=canonical_digest(admitted),
        status="admitted",
        carrier_uids={},
    )
    old = getattr(fight, "native_spirit_scene_admission", None)
    if old is not None and old != result:
        raise ValueError("Spirit challenge admission cannot be replaced")
    fight.native_spirit_scene_admission = result
    from .combat_encounter_actor_contract import (
        bind_actor_role,
        validate_actor_bindings,
    )
    from .combat_encounter_scene_helpers import bind_scene_helper_controls

    bind_actor_role(fight, "boss", admitted["original_actor_id"])
    bind_scene_helper_controls(
        fight,
        source_policy=POLICY,
        source_digest=manifest["source_digest"],
    )
    validate_actor_bindings(fight)
    return deepcopy(result)


def spirit_admission(fight):
    row = getattr(fight, "native_spirit_scene_admission", None)
    if row is None:
        return None
    from .combat_encounter_actor_contract import actor_contract_admission_digest

    if (
        not isinstance(row, dict)
        or not isinstance(row.get("source"), dict)
        or row.get("status") not in ("admitted", "granted", "cleaned")
        or row.get("source_digest") != canonical_digest(row.get("source"))
        or row["source"].get("policy") != POLICY
        or row["source"].get("fight_id") != fight.id
        or row["source"].get("admission_digest")
        != actor_contract_admission_digest(fight)
        or not isinstance(row.get("carrier_uids"), dict)
    ):
        raise ValueError("Spirit challenge lost its frozen source admission")
    manifest = getattr(fight, "native_scene_helper_manifest", None)
    if (
        not isinstance(manifest, dict)
        or manifest["source_digest"] != row["source"]["helper_manifest_digest"]
    ):
        raise ValueError("Spirit challenge helper declaration changed")
    ready = row.get("ready_participants")
    if ready is not None and (
        not isinstance(ready, dict)
        or not isinstance(ready.get("source"), dict)
        or ready.get("source_digest") != canonical_digest(ready["source"])
        or ready["source"].get("fight_id") != fight.id
        or ready["source"].get("admission_digest") != row["source"]["admission_digest"]
    ):
        raise ValueError("Spirit Ready participant source changed")
    return row


def freeze_spirit_participants(fight, characters):
    """Pin the complete Ready provider after its durable participant fences.

    World refresh_participants supplies these owned character sources before
    class initialization. Heroes joining after initial placement are included;
    native summons/companions are distinct and never impersonate human owners.
    """
    receipt = spirit_admission(fight)
    if receipt is None:
        return None
    if fight.phase != "active" or fight.turn_id != 1 or receipt["status"] != "admitted":
        raise ValueError("Spirit participant freeze requires its actual Ready preview")
    from .combat_companions import registered_companion_ids
    from .combat_terminal_metadata import registered_summon_actor_ids

    dependants = registered_companion_ids(fight) | registered_summon_actor_ids(fight)
    humans = sorted(
        identity
        for identity, actor in fight.actors.items()
        if actor.controlled and identity not in dependants
    )
    rows = []
    for identity in humans:
        actor, source = fight.actors[identity], characters.get(identity)
        if (
            not isinstance(source, Mapping)
            or source.get("id") != identity
            or source.get("account_id") != actor.owner_id
        ):
            raise ValueError("Spirit Ready lacks its actual owned human source")
        rows.append(dict(actor_id=identity, account_id=actor.owner_id))
    if receipt["source"]["participant_id"] not in humans:
        raise ValueError("Spirit Ready lost the admitted principal participant")
    source = dict(
        authority="existing_ready_refreshed_owned_participant_provider",
        fight_id=fight.id,
        admission_digest=receipt["source"]["admission_digest"],
        players=rows,
    )
    frozen = dict(source=source, source_digest=canonical_digest(source))
    if receipt.get("ready_participants") not in (None, frozen):
        raise ValueError("Spirit Ready participant ownership changed")
    fight.native_spirit_scene_admission = dict(receipt, ready_participants=frozen)
    return deepcopy(frozen)


def spirit_result_player(fight):
    """Select a live original Ready carrier, recording every earned handoff.

    Original admission and helper ownership never change. A departed leader
    cannot keep the team's original timed program attached to an absent actor.
    """
    receipt = spirit_admission(fight)
    if receipt is None or receipt.get("ready_participants") is None:
        return None
    ready = receipt["ready_participants"]
    candidates = {}
    for row in ready["source"]["players"]:
        identity = row["actor_id"]
        actor = fight.actors.get(identity)
        uid = receipt["carrier_uids"].get(str(identity))
        if (
            actor is not None
            and actor.controlled
            and actor.owner_id == row["account_id"]
            and not getattr(actor, "pve_withdrawn", False)
            and fight._in_play(actor)
            and any(
                entry.uid == uid
                and entry.reference == 9145
                and entry.caster_id == identity
                and entry.target_id == identity
                for entry in actor.state_ledger.entries
            )
        ):
            candidates[identity] = actor
    old = getattr(fight, "native_spirit_result_leadership", None)
    if old is not None and (
        old.get("admission_digest") != receipt["source"]["admission_digest"]
        or old.get("ready_digest") != ready["source_digest"]
    ):
        raise ValueError("Spirit result leadership lost its original party source")
    current = (
        old["actor_id"] if old is not None else receipt["source"]["participant_id"]
    )
    if current in candidates:
        chosen = current
    else:
        order = [identity for identity in fight.order if identity in candidates]
        chosen = order[0] if order else next(iter(candidates), None)
    if chosen is None:
        return None
    history = [] if old is None else list(old["handoffs"])
    if chosen != current:
        history.append(
            dict(
                from_actor_id=current,
                actor_id=chosen,
                turn_id=fight.turn_id,
                source="original_ready_carrier_withdrawn_or_out_of_play",
            )
        )
    fight.native_spirit_result_leadership = dict(
        admission_digest=receipt["source"]["admission_digest"],
        ready_digest=ready["source_digest"],
        actor_id=chosen,
        handoffs=history,
    )
    return candidates[chosen]


def apply_spirit_start(fight, runtime_factory, packets):
    """Grant the genuine original player program after ordinary actor birth."""
    receipt = spirit_admission(fight)
    if receipt is None or receipt["status"] != "admitted":
        return False
    if fight.phase != "active":
        raise ValueError("Spirit player program requires its real active opening")
    ready = receipt.get("ready_participants")
    if ready is None:
        raise ValueError("Spirit player program lacks its complete fenced Ready roster")
    from .combat_encounter_actor_contract import (
        bind_actor_role,
        validate_actor_bindings,
    )
    from .combat_encounter_scene_helpers import bind_scene_helper_controls

    bind_actor_role(fight, "boss", receipt["source"]["original_actor_id"])
    bind_scene_helper_controls(
        fight,
        source_policy=POLICY,
        source_digest=receipt["source"]["helper_manifest_digest"],
    )
    validate_actor_bindings(fight)
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    dispatcher, outbox = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    retention, handler = dispatcher.native_retention, dispatcher.native_state_handler
    if retention.fight is not fight or handler.fight is not fight:
        raise ValueError("Spirit player grant changed preview ownership")
    profile = state_profile(handler.catalog, 9145, 1)
    if 410217 not in profile["effects"] or 410946 not in profile["effects"]:
        raise ValueError("Spirit original book or owned terminal root is absent")
    carrier = StateCarrierContext(
        profile["duration"],
        profile["realtime_duration"],
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=profile["realtime_duration"]),
    )
    carriers = {}
    for participant in ready["source"]["players"]:
        identity = participant["actor_id"]
        actor = fight.actors[identity]
        if (
            not actor.controlled
            or actor.owner_id != participant["account_id"]
            or any(e.reference == 9145 for e in actor.state_ledger.entries)
        ):
            raise ValueError("Spirit player carrier existed before its admitted source")
        if not retention.apply_state_reference(
            handler,
            EffectInvocation(2226, 1, actor.id, actor.id, actor.position),
            9145,
            1,
            carrier_context=carrier,
        ):
            raise ValueError("Original Spirit player program was not applied")
        entries = [
            entry for entry in actor.state_ledger.entries if entry.reference == 9145
        ]
        if len(entries) != 1:
            raise ValueError("Spirit player carrier has ambiguous original identity")
        carriers[str(identity)] = entries[0].uid
    fight.native_spirit_scene_admission = dict(
        receipt, status="granted", carrier_uids=carriers
    )
    packets.extend(outbox)
    return True


def install_spirit_objective(dispatcher):
    """Pin the source result contract after genuine native1003 publication."""
    fight = dispatcher.native_retention.fight
    receipt = spirit_admission(fight)
    if receipt is None or receipt["status"] != "granted":
        return None
    from .combat_encounter_objective_policy import bound_objective_policy
    from .combat_encounter_objective import install_objective_policy

    policy = bound_objective_policy(5848, receipt["source"]["map_id"])
    return install_objective_policy(
        fight,
        policy.record(),
        objective_player_id=receipt["source"]["participant_id"],
    )


def deliver_spirit_early_defeat(dispatcher):
    """Run the original helper failure branch after actual last-human KO/out.

    HP alone is insufficient proof. Every human must have its real native death
    delivery or authenticated PvE departure. This does not assign a winner or
    manufacture damage; original411015 dispels410754 and kills its helper Pv.
    """
    fight = dispatcher.native_retention.fight
    if (
        getattr(dispatcher, "native_spirit_failure_running", False)
        or getattr(fight, "native_encounter_objective_policy", None) is None
        or fight.phase != "active"
    ):
        return False
    receipt = spirit_admission(fight)
    if (
        receipt is None
        or receipt["status"] != "granted"
        or receipt.get("ready_participants") is None
    ):
        return False
    from .combat_encounter_objective_policy import require_admitted_policy
    from .combat_encounter_objective import _score_scope, _admission

    policy = require_admitted_policy(fight.native_encounter_objective_policy)
    if policy.reference != 5848:
        return False
    _, boss = _score_scope(fight, policy)
    _admission(fight, policy)
    players = receipt["ready_participants"]["source"]["players"]
    if any(
        fight._in_play(fight.actors[row["actor_id"]])
        and not getattr(fight.actors[row["actor_id"]], "pve_withdrawn", False)
        for row in players
    ):
        return False
    from .combat_pve_departure import retired_pve_actor_ids

    departed = retired_pve_actor_ids(fight)
    native_deaths = getattr(fight, "native_death_event_deliveries", {})
    proofs = []
    for row in players:
        identity = row["actor_id"]
        actor = fight.actors[identity]
        if actor.owner_id != row["account_id"] or not actor.controlled:
            raise ValueError("Spirit failure lost its owned human identity")
        if identity in departed:
            proofs.append(dict(actor_id=identity, source="actual_owned_pve_departure"))
            continue
        delivered = [
            (sequence, event)
            for sequence, event in native_deaths.items()
            if event.get("actor_id") == identity
            and event.get("event_id") == 1013
            and event.get("policy") == "wakemu.owned-ko-and-death-v3"
            and any(
                original.get("kind") == "death"
                and original.get("actor_id") == identity
                and str(original.get("sequence")) == str(sequence)
                for original in fight.events
            )
        ]
        if actor.hp > 0 or not delivered:
            return False  # Raw fixture HP0 is never a scenario failure producer.
        proofs.append(
            dict(
                actor_id=identity,
                source="actual_native_death",
                sequence=str(delivered[-1][0]),
            )
        )
    manifest = fight.native_scene_helper_manifest["source"]
    helpers = [fight.actors[row["actor_id"]] for row in manifest["helpers"]]
    pending = [actor.id for actor in helpers if fight._in_play(actor)]
    if not pending:
        return False
    old = getattr(fight, "native_spirit_failure_result", None)
    if old is not None:
        if old["admission_digest"] != receipt["source"]["admission_digest"]:
            raise ValueError("Spirit native failure receipt changed")
        return False
    from .combat_effect_dispatch import EffectInvocation

    # Dead Pv remain authentic native source identities; this is the original
    # failure helper subtree, not a forced selected target or replacement kill.
    source = fight.actors[receipt["source"]["participant_id"]]
    hp_before = boss.hp
    dispatcher.native_spirit_failure_running = True
    try:
        dispatcher.execute(
            EffectInvocation(
                411015,
                source.effective_level,
                source.id,
                source.id,
                source.position,
                native_retained_container={"present": False},
            )
        )
    finally:
        dispatcher.native_spirit_failure_running = False
    if boss.hp != hp_before or any(fight._in_play(fight.actors[i]) for i in pending):
        raise ValueError(
            "Original Spirit failure program did not settle its native helpers"
        )
    fight.native_spirit_failure_result = dict(
        admission_digest=receipt["source"]["admission_digest"],
        ready_digest=receipt["ready_participants"]["source_digest"],
        effect_reference=411015,
        proofs=proofs,
        helper_actor_ids=pending,
        source="actual_last_human_native_ko_or_owned_departure",
    )
    return True


def cleanup_spirit_scene(fight, runtime_factory, packets, *, actor_ids=None):
    """Remove only the granted original carriers through native933 unapply."""
    receipt = spirit_admission(fight)
    if receipt is None or receipt["status"] != "granted":
        return False
    selected = (
        set(map(int, receipt["carrier_uids"])) if actor_ids is None else set(actor_ids)
    )
    if any(type(identity) is not int for identity in selected):
        raise ValueError("Spirit cleanup requires actual actor identities")
    cleaned = set(receipt.get("cleaned_actor_ids", ()))
    selected &= set(map(int, receipt["carrier_uids"])) - cleaned
    if not selected:
        return False
    dispatcher, outbox = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    if dispatcher.native_retention.fight is not fight:
        raise ValueError("Spirit cleanup changed preview ownership")
    for identity, uid in receipt["carrier_uids"].items():
        if int(identity) not in selected:
            continue
        actor = fight.actors[int(identity)]
        entries = [entry for entry in actor.state_ledger.entries if entry.uid == uid]
        if entries:
            if entries[0].reference != 9145:
                raise ValueError("Spirit cleanup source carrier changed")
            dispatcher.native_retention.removal(
                dispatcher.native_retention.view()
            ).remove((uid,))
    marker = getattr(fight, "native_encounter_objective_markers", {}).get(
        "wakemu-spirit-thirteen-rounds-v1"
    )
    if isinstance(marker, dict):
        sources = [*marker.get("previous_markers", ()), marker]
        for owned in sources:
            if (
                owned.get("actor_id") not in selected
                or owned.get("owns_marker") is not True
            ):
                continue
            actor = fight.actors[owned["actor_id"]]
            entries = [
                entry
                for entry in actor.state_ledger.entries
                if entry.uid == owned.get("marker_uid")
            ]
            if entries:
                if entries[0].reference != 9178:
                    raise ValueError("Spirit cleanup earned marker identity changed")
                dispatcher.native_retention.removal(
                    dispatcher.native_retention.view()
                ).remove((owned["marker_uid"],))
    cleaned |= selected
    complete = cleaned == set(map(int, receipt["carrier_uids"]))
    fight.native_spirit_scene_admission = dict(
        receipt,
        status="cleaned" if complete else "granted",
        cleaned_actor_ids=sorted(cleaned),
    )
    packets.extend(outbox)
    return True
