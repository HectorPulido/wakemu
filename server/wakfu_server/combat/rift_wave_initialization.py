"""Initialize a registered native Rift successor before its birth snapshots."""


def initialize_registered_wave(dispatcher, *, actors, monsters, player_ids):
    """Stage native gameplay and equipment reactions on the accepted preview.

    All ordinary actors, QI slots and innate sources already exist. The caller
    publishes every birth before this dispatcher's state packets and commits
    their checkpoint and transaction RNG together.
    """
    from wakfu_server.rift_native_gameplay import (
        install_wave_state,
        distribute_unclaimed_artifacts,
    )
    from wakfu_server.rift_artifact_generation import spawn_artifacts
    from wakfu_server.rift_artifact_inheritance import inherit_artifact_grants
    from wakfu_server.combat_equipment_wave_events import deliver_registered_wave

    fight = dispatcher.native_retention.fight
    next_wave = fight.rift_wave_state["pending_wave"]["completed_wave"] + 1
    install_wave_state(
        dispatcher,
        actor_ids=tuple(actor.id for actor in actors),
        wave=next_wave,
    )
    inherit_artifact_grants(
        dispatcher,
        actor_ids=tuple(actor.id for actor in actors),
        wave=next_wave,
    )
    distribute_unclaimed_artifacts(dispatcher, before_wave=next_wave)
    deliver_registered_wave(
        dispatcher,
        actors=actors,
        monsters=monsters,
        player_ids=player_ids,
    )
    spawn_artifacts(dispatcher, wave=next_wave)
