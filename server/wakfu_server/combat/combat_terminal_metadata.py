"""Read-only participant identities required to serialize terminal results."""


def owner_characters_for_finish(store, shared, fight, active_characters):
    """Add retained withdrawn owners without broadening active action sources.

    Active owners must already be present in ``active_characters`` from
    ``CombatSessionAdapter.player_sources``. A missing source is tolerated only
    for an explicitly withdrawn historical player that still matches the
    durable shared participant identity.
    """
    if not isinstance(active_characters, dict):
        raise ValueError("Terminal player sources must be a mapping")
    result = dict(active_characters)
    participants = getattr(shared, "participants", None)
    if not isinstance(participants, dict):
        raise ValueError("Terminal fight has no retained participant roster")
    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Terminal fight has invalid native summon registrations")
    for actor in fight.actors.values():
        if not actor.controlled:
            continue
        if actor.id in registrations:
            _registered_summon(fight, actor.id, registrations[actor.id])
            # A controlled summon is still a native monster in the report; its
            # UID is not a character row and must never reach Store.character.
            continue
        source = result.get(actor.id)
        if source is not None:
            if (
                source.get("id") != actor.id
                or source.get("account_id") != actor.owner_id
            ):
                raise ValueError("Terminal active owner source identity changed")
            continue
        if not getattr(actor, "pve_withdrawn", False):
            raise ValueError("Active terminal actor has no current owner source")
        participant = participants.get(actor.owner_id)
        if participant is None or participant.account_id != actor.owner_id:
            raise ValueError(
                "Withdrawn terminal actor has no retained owner participant"
            )
        if participant.character_id != actor.id:
            connection = getattr(store, "connection", None)
            if not callable(connection):
                raise ValueError(
                    "Withdrawn terminal actor has no retained owner participant with durable membership authority"
                )
            with connection() as db:
                durable = db.execute(
                    "SELECT 1 FROM combat_fight_participants p JOIN combat_pve_withdrawals w "
                    "ON w.fight_id=p.fight_id AND w.character_id=p.character_id "
                    "WHERE p.fight_id=%s AND p.character_id=%s AND p.account_id=%s "
                    "AND p.session_generation=%s",
                    (fight.id, actor.id, actor.owner_id, participant.generation),
                ).fetchone()
                if durable is None:
                    raise ValueError("Withdrawn hero lacks frozen durable membership")
        historical = store.character(participant.account_id, actor.id)
        if (
            historical.get("id") != actor.id
            or historical.get("account_id") != actor.owner_id
            or historical.get("deleted_at") is not None
        ):
            raise ValueError("Withdrawn terminal actor character identity changed")
        result[actor.id] = historical
    return result


def registered_summon_actor_ids(fight):
    """Validate and return summon UIDs so owner-source loaders skip them."""
    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Terminal fight has invalid native summon registrations")
    for identity, registration in registrations.items():
        _registered_summon(fight, identity, registration)
    return frozenset(registrations)


def registered_summon_metadata(fight):
    """Return native monster report rows for registered summon UIDs only."""
    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Terminal fight has invalid native summon registrations")
    result = {}
    for identity, registration in registrations.items():
        actor, authority = _registered_summon(fight, identity, registration)
        # fight_report's monster branch serializes identity + native breed ref;
        # this preserves summon identity without pretending it is a PC.
        result[identity] = {"kind": "monster", "ref": authority["breed_id"]}
    return result


def _registered_summon(fight, identity, registration):
    if (
        type(identity) is not int
        or not isinstance(registration, dict)
        or registration.get("actor_id") != identity
        or not isinstance(registration.get("authority"), dict)
        or registration["authority"].get("is_summon") is not True
    ):
        raise ValueError("Invalid registered terminal summon")
    actor = fight.actors.get(identity)
    authority = registration["authority"]
    source = getattr(actor, "native_summon_source", None) if actor is not None else None
    controller_id = registration.get("controller_id")
    controller = fight.actors.get(controller_id)
    if (
        actor is None
        or getattr(actor, "is_summon", None) is False
        or not isinstance(source, dict)
        or source.get("ref") != authority.get("breed_id")
        or source.get("level") != authority.get("native_real_level")
        or source.get("controller_id") != controller_id
        or source.get("caster_id") != registration.get("caster_id")
        or (
            "native_relation_source" in source
            and source["native_relation_source"]
            != "big.new_bje.fdt_initial_registration"
        )
        or (
            getattr(actor, "native_controller_id", None) is not None
            and actor.native_controller_id != controller_id
        )
        or controller is None
        or actor.controlled != controller.controlled
        or actor.owner_id != controller.owner_id
        or (
            authority.get("native_controller_id") is not None
            and authority["native_controller_id"] != controller_id
        )
        or type(authority.get("breed_id")) is not int
        or authority["breed_id"] <= 0
    ):
        raise ValueError("Registered terminal summon authority changed")
    return actor, authority
