"""Database-scoped publication for original encounter table listeners."""
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_table_listener_versions WHERE policy=%s", (policy,)
        ).fetchone()
    if row is None:
        raise ValueError("Unknown encounter table listener policy")
    result = dict(row)
    references = list(result.pop("additional_effect_references", ()))
    if references != sorted(set(references)) or any(
        type(value) is not int or value <= 0 for value in references
    ):
        raise ValueError("Invalid additional encounter listener inventory")
    if references:
        with _database().connection() as db:
            callbacks = [
                dict(item)
                for item in db.execute(
                    "SELECT * FROM encounter_table_listener_callbacks WHERE policy=%s "
                    "ORDER BY effect_reference",
                    (policy,),
                ).fetchall()
            ]
        if [item["effect_reference"] for item in callbacks] != references:
            raise ValueError("Incomplete additional encounter listener inventory")
        for item in callbacks:
            _validate_callback(item, policy=policy)
        result["callbacks"] = callbacks
    result["monster_references"] = list(result["monster_references"])
    if (
        not result["authority"]
        or result["timing"] != "owned_boss_table_start"
        or result["event_id"] != 1003
        or result["channel"] != 61
    ):
        raise ValueError("Invalid encounter table listener publication contract")
    return result


def freeze_table_listener_policy(map_id, monster_references, *, required=True):
    """Freeze the admission pointer before the first score/checkpoint snapshot."""
    from copy import deepcopy
    from wakfu_server import native_catalog

    references = list(sorted(monster_references))
    with _database().connection() as db:
        row = db.execute(
            "SELECT policy FROM encounter_table_listener_active "
            "WHERE map_id=%s AND monster_references=%s::integer[]",
            (map_id, references),
        ).fetchone()
    if row is None:
        if not required:
            return None
        raise ValueError("Encounter has no published table listener policy")
    version = _version(row["policy"])
    if (
        version["map_id"] != map_id
        or version["monster_references"] != references
        or version["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Encounter table listener differs from admission or catalog")
    from wakfu_server.paths import DATA_ROOT

    metadata = native_catalog.record(
        DATA_ROOT / "native-retained-effect-metadata.json",
        "effects",
        version["effect_reference"],
    )
    effect = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json",
        "effects",
        version["effect_reference"],
    )
    state = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json",
        "states",
        version["owner_constructor_state"],
    )
    if (
        not metadata
        or not effect
        or not state
        or metadata.get("subscription") is not True
        or metadata.get("event_global_subscription") is not True
        or metadata.get("event_reverse_subscription") is not False
        or metadata.get("event_caster_code") != 2
        or metadata.get("event_target_code") != 2
        or version["effect_reference"] not in state.get("effect_ids", ())
        or version["event_id"] not in (effect["target_masks"][5] or ())
    ):
        raise ValueError(
            "Encounter table listener differs from original native metadata"
        )
    for callback in version.get("callbacks", ()):
        callback_effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json",
            "effects",
            callback["effect_reference"],
        )
        callback_metadata = native_catalog.record(
            DATA_ROOT / "native-retained-effect-metadata.json",
            "effects",
            callback["effect_reference"],
        )
        carrier = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json",
            "states",
            callback["owner_state"],
        )
        if (
            not carrier
            or callback["effect_reference"] not in carrier.get("effect_ids", ())
            or callback["owner_reference"] != version["boss_reference"]
            or not _callback_matches_native(
                callback, callback_effect, callback_metadata
            )
        ):
            raise ValueError(
                "Additional encounter listener differs from native authority"
            )
    return deepcopy(version)


def freeze_encounter_table_listener_policy(fight, *, roles):
    """Pin optional content policy once, including an explicit no-policy result."""
    if hasattr(fight, "native_encounter_table_listener_policy"):
        frozen = frozen_table_listener_policy(fight)
        if frozen is not None:
            from wakfu_server import native_catalog

            if (
                frozen["map_id"] != roles.map_id
                or frozen["monster_references"]
                != list(sorted(roles.monster_references))
                or frozen["catalog_revision"] != native_catalog.release()
            ):
                raise ValueError(
                    "Frozen table listener differs from encounter or catalog"
                )
        return frozen
    frozen = freeze_table_listener_policy(
        roles.map_id,
        roles.monster_references,
        required=False,
    )
    fight.native_encounter_table_listener_policy = frozen
    return frozen


def frozen_table_listener_policy(fight):
    """Keep historical score records valid without inferring new policies."""
    frozen = getattr(fight, "native_encounter_table_listener_policy", None)
    profile = getattr(fight, "boss_score_profile", None)
    historical = (
        profile.get("table_listener_policy") if isinstance(profile, dict) else None
    )
    if not hasattr(fight, "native_encounter_table_listener_policy"):
        frozen = historical
    elif historical is not None and historical != frozen:
        raise ValueError("Encounter table listener differs from score publication")
    if frozen is not None and (
        not isinstance(frozen, dict) or frozen != _version(frozen.get("policy"))
    ):
        raise ValueError("Frozen encounter table listener policy changed")
    return frozen


def deliver_owned_table_listeners(dispatcher, *, boss_id, snapshot):
    """Use only retained UIDs of an authentic owned native constructor."""
    from .combat_event_replay import NativeExternalEvent

    fight = dispatcher.native_retention.fight
    frozen = frozen_table_listener_policy(fight)
    if frozen is None:
        return (), ()  # Existing fights without the new admission keep their policy.
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(boss_id, {})
    if (
        receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == frozen["boss_constructor_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Table listener lacks its native boss constructor")
    outcomes, deliveries = [], []
    owners = []
    if frozen["owner_reference"] == frozen["boss_reference"]:
        owner = fight.actors.get(boss_id)
        if owner is None or owner.controlled:
            raise ValueError("Table listener owner is not its native boss")
        if owner.hp > 0:
            owners.append(owner)
    for owner in (
        fight.actors.values()
        if frozen["owner_reference"] != frozen["boss_reference"]
        else ()
    ):
        source = getattr(owner, "native_summon_source", None)
        if (
            not isinstance(source, dict)
            or source.get("ref") != frozen["owner_reference"]
        ):
            continue
        from .combat_runtime_adapter import NativeActorAuthority

        registration = getattr(fight, "native_summon_registrations", {}).get(owner.id)
        if not isinstance(registration, dict) or not isinstance(
            registration.get("authority"), dict
        ):
            raise ValueError("Table listener owner lacks an authentic native birth")
        try:
            metadata = NativeActorAuthority(**registration["authority"])
        except TypeError as error:
            raise ValueError(
                "Table listener owner lacks an authentic native birth"
            ) from error
        controller_id = registration.get("controller_id")
        controller = fight.actors.get(controller_id)
        if (
            source.get("caster_id") != boss_id
            or source.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
            or registration.get("actor_id") != owner.id
            or registration.get("caster_id") != boss_id
            or type(controller_id) is not int
            or controller is None
            or source.get("controller_id") != controller_id
            or getattr(owner, "native_controller_id", None) != controller_id
            or metadata.native_controller_id != controller_id
            or metadata.native_npc_prototype_ref != frozen["owner_reference"]
            or metadata.breed_id != frozen["owner_reference"]
            or source.get("level") != metadata.native_real_level
            or metadata.is_summon is not True
            or metadata.is_player is not False
            or owner.controlled
            or owner.controlled != controller.controlled
            or owner.owner_id != controller.owner_id
        ):
            raise ValueError("Table listener owner lacks an authentic native birth")
        if owner.hp > 0:
            owners.append(owner)
    if len(owners) > 1:
        raise ValueError("Encounter table listener has multiple native owners")
    for owner in owners:
        states = {
            entry.uid
            for entry in owner.state_ledger.entries
            if entry.reference == frozen["owner_constructor_state"]
            and entry.target_id == owner.id
        }
        selected = frozenset(
            entry.uid
            for entry in snapshot
            if entry.manager_id == owner.id
            and entry.generic_effect == frozen["effect_reference"]
        )
        if not states:
            if frozen["owner_reference"] == frozen["boss_reference"] and not selected:
                # A native timer may retire itself while its boss remains alive.
                deliveries.append(
                    dict(policy=frozen["policy"], owner_id=owner.id, eligible_uids=[])
                )
                continue
            raise ValueError("Table listener owner lacks its native constructor state")
        for uid in selected:
            retained = fight.native_owned_group_effects.get(uid, {})
            if retained.get("invocation", {}).get("state_uid") not in states:
                raise ValueError(
                    "Table listener UID does not belong to its native constructor"
                )
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(owner.id, (frozen["event_id"],), frozen["channel"]),
                authority=dispatcher.native_clone_authority,
                eligible_uids=selected,
            )
        )
        deliveries.append(
            dict(
                policy=frozen["policy"],
                owner_id=owner.id,
                eligible_uids=sorted(selected),
            )
        )
    return tuple(outcomes), tuple(deliveries)


_CALLBACK_KEYS = frozenset(
    (
        "policy",
        "effect_reference",
        "owner_reference",
        "owner_state",
        "forbidden_state",
        "event_id",
        "channel",
        "timing",
        "effect_family",
        "selector_class",
        "selector_mask",
        "parameter_count",
        "native_parameters",
        "criterion",
        "area_class",
        "children",
        "execution_count",
        "reverse_subscription",
        "global_subscription",
        "event_caster_code",
        "event_target_code",
        "owner_on_caster",
        "definition_type",
        "effect_flags",
    )
)


def _validate_callback(row, *, policy):
    if (
        set(row) != _CALLBACK_KEYS
        or row["policy"] != policy
        or row["timing"] != "owned_boss_post_start"
        or row["channel"] != 60
        or row["event_id"] <= 0
        or row["effect_family"] != 330
        or row["selector_class"] != "fcE"
        or row["selector_mask"] < 0
        or row["area_class"] != "anD"
        or row["parameter_count"] * 2 != len(row["native_parameters"])
        or any(type(value) not in (int, float) for value in row["native_parameters"])
        or row["reverse_subscription"] is not True
        or row["global_subscription"] is not False
        or row["owner_on_caster"] is not False
        or row["event_caster_code"] != 2
        or row["event_target_code"] != 2
        or row["definition_type"] != 2
        or type(row["execution_count"]) is not int
        or row["execution_count"] == 0
        or any(
            type(row[key]) is not int or row[key] <= 0
            for key in (
                "effect_reference",
                "owner_reference",
                "owner_state",
                "forbidden_state",
            )
        )
    ):
        raise ValueError("Invalid additional encounter listener descriptor")
    row["children"] = list(row["children"])
    row["effect_flags"] = list(row["effect_flags"])


def _callback_matches_native(row, effect, metadata):
    if not effect or not metadata:
        return False
    parameters = effect.get("parameters")
    masks = effect.get("target_masks")
    return (
        effect.get("effect_class") == row["effect_family"]
        and type(parameters) in (list, tuple)
        and all(type(value) in (int, float) for value in parameters)
        and list(parameters) == row["native_parameters"]
        and effect.get("parameter_count") == row["parameter_count"]
        and effect.get("criteria") == row["criterion"]
        and effect.get("area_class") == row["area_class"]
        and effect.get("native_target_selector")
        == {"class": row["selector_class"], "mask": row["selector_mask"]}
        and list(effect.get("children", ())) == row["children"]
        and list(effect.get("native_effect_flags", ())) == row["effect_flags"]
        and isinstance(masks, (list, tuple))
        and len(masks) == 7
        and tuple(masks[5] or ()) == (row["event_id"],)
        and all(not masks[index] for index in (0, 1, 2, 3, 4, 6))
        and metadata.get("subscription") is True
        and metadata.get("effect_class") == row["effect_family"]
        and metadata.get("event_reverse_subscription") is row["reverse_subscription"]
        and metadata.get("event_global_subscription") is row["global_subscription"]
        and metadata.get("owner_on_caster") is row["owner_on_caster"]
        and metadata.get("event_caster_code") == row["event_caster_code"]
        and metadata.get("event_target_code") == row["event_target_code"]
        and metadata.get("event_execution_count") == row["execution_count"]
        and metadata.get("event_execution_count_per_level") == 0
        and metadata.get("definition_type") == row["definition_type"]
    )


def deliver_owned_post_start_listeners(dispatcher, *, actor_id):
    """Reconstructed calendar publication; never pretend that movement occurred.

    The frozen DB descriptor identifies an original retained consumer. Its own
    unchanged criterion decides the calendar/difficulty condition. Snapshot
    only pre-existing UIDs, so a listener born inside the callback cannot hear
    this same event. Ordinary and historically frozen fights stay unchanged.
    """
    from .combat_event_replay import NativeExternalEvent

    fight = dispatcher.native_retention.fight
    frozen = frozen_table_listener_policy(fight)
    callbacks = frozen.get("callbacks", ()) if frozen is not None else ()
    if not callbacks:
        return ()
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Calendar listener requires the actual active owned start")
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor_id, {})
    if receipt.get("ref") != frozen["boss_reference"]:
        return ()
    actor = fight.current
    start = getattr(fight, "native_turn_event_deliveries", {}).get(
        f"{fight.turn_id}:{actor_id}:start", {}
    )
    table = getattr(fight, "native_table_turn", None)
    if (
        actor.controlled
        or actor.hp <= 0
        or receipt.get("initialized") is not True
        or not any(
            item.get("state_id") == frozen["boss_constructor_state"]
            for item in receipt.get("resolved_states", ())
        )
        or type(table) is not int
        or table < 1
        or start.get("actor_id") != actor_id
        or start.get("turn_id") != fight.turn_id
        or start.get("event_id") != 1001
        or start.get("phase") != "start"
    ):
        raise ValueError("Calendar listener lacks its authentic post-start boundary")
    key = f"{frozen['policy']}:{actor_id}:{table}"
    journal = getattr(fight, "native_encounter_post_start_deliveries", {})
    if key in journal:
        return ()
    snapshot = tuple(dispatcher.native_retention.view().entries)
    selections = []
    for callback in callbacks:
        if callback["owner_reference"] != receipt["ref"]:
            raise ValueError("Calendar listener owner differs from its native boss")
        effect = dispatcher.effects.get(str(callback["effect_reference"]))
        metadata = dispatcher.native_retention.metadata["effects"].get(
            str(callback["effect_reference"])
        )
        if not _callback_matches_native(callback, effect, metadata):
            raise ValueError(
                "Calendar listener execution differs from frozen descriptor"
            )
        states = {
            entry.uid
            for entry in actor.state_ledger.entries
            if entry.reference == callback["owner_state"]
            and entry.target_id == actor_id
            and entry.caster_id == actor_id
        }
        forbidden = any(
            entry.reference == callback["forbidden_state"]
            for entry in actor.state_ledger.entries
        )
        selected = frozenset(
            entry.uid
            for entry in snapshot
            if entry.manager_id == actor_id
            and entry.generic_effect == callback["effect_reference"]
        )
        if forbidden or not states:
            selected = frozenset()
        for uid in selected:
            invocation = fight.native_owned_group_effects.get(uid, {}).get(
                "invocation", {}
            )
            if (
                invocation.get("reference") != callback["effect_reference"]
                or invocation.get("state_uid") not in states
                or invocation.get("caster_id") != actor_id
                or invocation.get("target_id") != actor_id
            ):
                raise ValueError(
                    "Calendar listener UID lacks its native carrier binding"
                )
        selections.append((callback, selected))
    outcomes = []
    for callback, selected in selections:
        if selected:
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(
                        actor_id, (callback["event_id"],), callback["channel"]
                    ),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=selected,
                )
            )
    fight.native_encounter_post_start_deliveries = {
        **journal,
        key: dict(
            actor_id=actor_id,
            turn_id=fight.turn_id,
            table_turn=table,
            callbacks=[
                dict(
                    effect_reference=row["effect_reference"], eligible_uids=sorted(uids)
                )
                for row, uids in selections
            ],
        ),
    }
    return tuple(outcomes)
