"""Actual owned Feca casts for a native protected-health phase component.

This helper changes neither health floors nor states. Native damage callbacks
must decrease the real PA minimum before the selected cast can be committed.
"""
import struct


class NoLegalOwnedPhaseTransition(ValueError):
    def __init__(self, errors, active_book):
        super().__init__("No legal owned damage phase transition: " + repr(errors))
        self.errors = tuple(errors)
        self.active_book = tuple(active_book)


def execute_health_floor_transition(runtime, component, identity, *, stats_serializer):
    from wakfu_server.spells import validate_deck
    from wakfu_server.combat_random_transaction import rollback_external_rng
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_server.combat_los import authoritative_visible

    fight = runtime.fight
    character = component.character
    actor_id = character["id"]
    deck = component.decks[actor_id]
    active_book = validate_deck(
        deck,
        character["breed"],
        character["level"],
        character=character,
    )["active"]
    before_minimum = fight.actors[identity].effect_minima[1]
    errors = []
    for reference in active_book:

        @rollback_external_rng
        def attempt(*, rng):
            transaction = prepare_server_spell(
                struct.pack(
                    ">qqiih",
                    actor_id,
                    (actor_id << 32) | reference,
                    *fight.actors[identity].position
                ),
                character,
                fight.rift_monsters,
                fight,
                character["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                critical=False,
                rng=rng,
                player_characters=component.characters,
                deck_blobs=component.decks,
                line_of_sight=lambda origin, target, state: authoritative_visible(
                    character["map_id"],
                    origin,
                    target,
                    state,
                    blocking_footprints={
                        member.id: {member.position[:2]}
                        for member in state.actors.values()
                        if state._in_play(member)
                    },
                ),
            )
            if transaction.fight.actors[identity].effect_minima[1] >= before_minimum:
                raise ValueError("Owned cast did not advance the protected phase")
            return transaction

        try:
            transaction = attempt(rng=component.rng)
        except ValueError as error:
            if str(error).startswith(
                (
                    "Metadata requires",
                    "Unlisted bounded",
                    "Bounded document",
                    "Missing native",
                )
            ):
                raise
            errors.append(str(error))
            continue
        return commit_spell_transaction(
            runtime, transaction, stats_serializer=stats_serializer
        )
    raise NoLegalOwnedPhaseTransition(errors, active_book)
