"""Real end/ACK and native summon serializers for bounded scene witnesses."""
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
from wakfu_server.combat_summon_stats import registered_summon_stats
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_turn_start,
    prepare_server_turn_end,
    server_runtime,
)


def native_scene_turn_runtime(fight, character, monsters, deck, *, map_id, rng):
    def stats(actor, current):
        if getattr(actor, "native_summon_source", None) is not None:
            return registered_summon_stats(actor, current, map_id)
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=current,
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, current.id, **values)
        return actual_monster_actor_stats(
            monsters[actor.id], actor, current.id, **values
        )

    runtime = RuntimeMessages(
        fight,
        runtime_stats_serializer=stats,
        turn_start_provider=lambda p, **kw: prepare_server_turn_start(
            character,
            monsters,
            p,
            deck,
            rng=rng,
            native_events=True,
            area_callbacks=True,
            **kw
        ),
        turn_end_provider=lambda p, **kw: prepare_server_turn_end(
            character, monsters, p, deck, rng=rng, **kw
        ),
        expiration_runtime_factory=lambda *, action_id: server_runtime(
            character, monsters, deck, action_id=action_id, critical=False, rng=rng
        )[0],
    )
    return runtime, stats
