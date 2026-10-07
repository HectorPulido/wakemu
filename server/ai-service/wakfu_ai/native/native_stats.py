"""Native roster statistics using each actor's complete owned authority."""
from copy import deepcopy
import struct

from .native_actor_source import registered_source


class NativeStats:
    def __init__(self, *, characters, monsters, fight_id, registrations=None):
        self.characters = deepcopy(characters)
        self.monsters = deepcopy(monsters)
        self.fight_id = fight_id
        self.registrations = deepcopy(registrations or {})

    def for_fight(self, fight):
        if fight.id != self.fight_id:
            raise ValueError("Statistics belong to another native encounter")
        return NativeStats(
            characters=self.characters,
            monsters=self.monsters,
            fight_id=self.fight_id,
            registrations=getattr(fight, "native_summon_registrations", {}),
        )

    def __call__(self, actor, fight=None):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        if fight is not None and fight.id != self.fight_id:
            raise ValueError("Statistics belong to another native encounter")
        stats, maxima = actor.effect_stats, actor.effect_maxima
        if (
            not isinstance(stats, dict)
            or not isinstance(maxima, dict)
            or 4 not in stats
            or 4 not in maxima
        ):
            raise ValueError("Missing authoritative native WP snapshot")
        registrations = (
            self.registrations
            if fight is None
            else getattr(fight, "native_summon_registrations", {})
        )
        if actor.id in registrations:
            return self.summon_stats(actor, registrations[actor.id])
        source = (
            self.characters.get(actor.id)
            if actor.controlled
            else self.monsters.get(actor.id)
        )
        if source is None:
            raise ValueError("Missing owned native statistics source")
        encoder = actual_actor_stats if actor.controlled else actual_monster_actor_stats
        return encoder(
            source, actor, self.fight_id, wp_current=stats[4], wp_maximum=maxima[4]
        )

    def summon_stats(self, actor, registration):
        from wakfu_server.combat_actor import monster_actor_stats
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        descriptor = registered_source(actor, registration)
        source = actor.native_summon_source
        descriptor["id"] = -actor.id
        body = monster_actor_stats(
            descriptor,
            self.fight_id,
            direction=getattr(actor, "direction", source["direction"]),
            obstacle_id=actor.native_obstacle_id,
            characteristics_payload=snapshot_characteristics(actor),
        )
        # eHj's final identity is signed and cjU's UID lookup accepts summons.
        # Reuse the native body encoder, replacing only this known identity
        # field to bypass its ordinary-NPC negative-ID input guard. No actor
        # identity or combat state is modified.
        tail = struct.calcsize(">qBqBh")
        if struct.unpack_from(">q", body, len(body) - tail)[0] != -actor.id:
            raise ValueError("Native statistics identity layout changed")
        return body[:-tail] + struct.pack(">q", actor.id) + body[-tail + 8 :]
