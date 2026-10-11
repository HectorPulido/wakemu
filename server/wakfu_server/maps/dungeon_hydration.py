"""Prepare native dungeon hydration before a worker mutates its world state."""

from dataclasses import dataclass

from wakfu_server import dungeon_context, native_transports, party_wire


_LOCATION = ("map_id", "instance_id", "x", "y", "z")


@dataclass(frozen=True)
class HydrationPlan:
    character: dict
    packets: tuple


def prepare_transition(
    store, account_id, generation, character_id, event, *, fixture_provider=None
):
    """Validate the live destination and pinned context, then encode all packets.

    If fixture_provider is omitted, the caller owns build profile publication.
    The caller owns socket/WORLD/POSITIONS changes. A successful plan is not an
    outbox ACK; delivery must complete before the existing consumer acknowledges
    its event with a second database generation/location check.
    """
    if (
        event.get("character_id") != character_id
        or event.get("session_generation") != generation
        or not store.current_session(account_id, generation)
    ):
        raise ValueError("Stale dungeon hydration session")
    character = store.character(account_id, character_id)
    if any(
        type(event.get("destination_" + field)) is not int
        or character.get(field) != event["destination_" + field]
        for field in _LOCATION
    ):
        raise ValueError("Dungeon hydration destination changed")
    if character["map_id"] <= 0:
        raise ValueError("Dungeon hydration requires a valid destination")
    party_packets = ()
    if event.get("transition_kind", "enter") == "exit":
        # The durable event must be authorized by returned membership even
        # after the final member closes the run; arbitrary instance-zero input
        # is not sufficient to clear the native dungeon context.
        with store.connection() as db:
            authorized = db.execute(
                "SELECT 1 FROM dungeon_transition_outbox o "
                "JOIN dungeon_instance_members m USING(instance_id,character_id) "
                "WHERE o.event_id=%s AND o.character_id=%s AND o.session_generation=%s "
                "AND o.status='pending' AND o.transition_kind='exit' "
                "AND o.destination_instance_id=0 AND m.status='returned' "
                "AND m.session_generation=%s",
                (event.get("event_id"), character_id, generation, generation),
            ).fetchone()
            dissolved_party = db.execute(
                "SELECT p.id FROM player_parties p "
                "JOIN dungeon_transition_outbox o ON o.party_id=p.id "
                "WHERE o.event_id=%s AND p.leader_id IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM player_party_members m "
                "WHERE m.party_id=p.id) "
                "AND NOT EXISTS (SELECT 1 FROM player_party_members m "
                "WHERE m.character_id=%s)",
                (event.get("event_id"), character_id),
            ).fetchone()
        if character["instance_id"] != 0 or authorized is None:
            raise ValueError("Dungeon exterior hydration is not authorized")
        context = None
        if dissolved_party is not None:
            party_packets = (party_wire.removed(dissolved_party["id"], [character_id]),)
    else:
        if character["instance_id"] <= 0:
            raise ValueError("Dungeon hydration requires a private destination")
        context = dungeon_context.for_instance(
            store, character["instance_id"], fight_in_progress=False
        )
    build_packets = ()
    if fixture_provider is not None:
        from wakfu_server.characters.dungeon_modulation_publication import (
            packets as build_publication,
            owned_hero_role,
        )

        with store.connection() as db:
            is_hero = owned_hero_role(db, account_id, character_id)
        build_packets = build_publication(
            character,
            fixture_provider,
            owned_characters=store.characters(account_id),
            owned_hero=is_hero,
        )
    bootstrap = tuple(native_transports.bootstrap(character, dungeon_context=context))
    # Native ctB13256 tears down the old scene; install the owned profile after
    # that cleanup and before csW13974 applies the destination, as at login.
    packets = (bootstrap[0], *build_packets, *bootstrap[1:], *party_packets)
    return HydrationPlan(character=dict(character), packets=packets)
