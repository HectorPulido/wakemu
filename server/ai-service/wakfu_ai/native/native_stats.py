"""Native roster statistics using each actor's complete owned authority."""
from copy import deepcopy


class NativeStats:
    def __init__(
        self, *, characters, monsters, fight_id, registrations=None, map_id=None
    ):
        self.characters = deepcopy(characters)
        self.monsters = deepcopy(monsters)
        self.fight_id = fight_id
        self.registrations = deepcopy(registrations or {})
        if map_id is not None and (type(map_id) is not int or map_id <= 0):
            raise ValueError("Invalid owned native statistics map")
        self.map_id = map_id

    def for_fight(self, fight):
        if fight.id != self.fight_id:
            raise ValueError("Statistics belong to another native encounter")
        return NativeStats(
            characters=self.characters,
            monsters=self.monsters,
            fight_id=self.fight_id,
            registrations=getattr(fight, "native_summon_registrations", {}),
            map_id=self.map_id,
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
            return self.summon_stats(actor, registrations[actor.id], fight)
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

    def summon_stats(self, actor, registration, fight=None):
        from wakfu_server.combat_summon_stats import registered_summon_stats

        # Tactical movement refreshes every fighter. Use the same live QI
        # registration serializer as normal casts, turns and reconnects;
        # ordinary NPC encoding clears pW.Uh even when its UID is replaced.
        if fight is None:
            raise ValueError("Registered summon stats require current fight")
        if (
            getattr(fight, "native_summon_registrations", {}).get(actor.id)
            != registration
        ):
            raise ValueError("Missing current registered summon authority")
        if self.map_id is None:
            raise ValueError("Registered summon stats require owned encounter map")
        return registered_summon_stats(actor, fight, self.map_id)
