"""Owned normal-player Nox actions using the declared production scene."""
from random import Random
import struct


class NativeNoxOffense:
    def __init__(
        self,
        store,
        *,
        name_prefix,
        owner_count=1,
        additional_actives=(),
        party_builds=None
    ):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from test_ultimate_encounter_scene_recipes import (
            UltimateEncounterSceneRecipeTests,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )

        self.scene = UltimateEncounterSceneRecipeTests().scene(5664)
        self.layout = resolve_supreme_scene(5664, self.scene)
        if type(owner_count) is not int or not 1 <= owner_count <= 6:
            raise ValueError("One to six actual owned Nox participants required")
        from dataclasses import replace

        baseline = native_endgame_iop_build()
        build = replace(
            baseline, active_spells=(*baseline.active_spells, *additional_actives)
        )
        builds = (build,) * owner_count if party_builds is None else tuple(party_builds)
        if len(builds) != owner_count:
            raise ValueError("Every actual Nox owner requires one admitted build")
        (
            fight,
            self.characters,
            self.monsters,
            self.decks,
            _,
            _,
            self.construction,
        ) = native_paid_party_fixture(
            store,
            self.scene,
            builds,
            tuple(self.layout["party_placement_cells"][:owner_count]),
            name_prefix=name_prefix,
            encounter_layout=self.layout,
            production_scene=True,
        )
        self.identity = next(iter(self.characters))
        self.rng = Random(7)
        self.common = dict(
            player_characters=self.characters, deck_blobs=self.decks, rng=self.rng
        )
        character, deck = self.characters[self.identity], self.decks[self.identity]
        self.runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=self.stats,
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                character, self.monsters, phase, deck, **self.common, **kw
            ),
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                character, self.monsters, phase, deck, **self.common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                self.monsters,
                deck,
                action_id=action_id,
                critical=False,
                **self.common
            )[0],
        )

    @property
    def fight(self):
        return self.runtime.fight

    def stats(self, actor, current):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats

        if getattr(actor, "native_summon_source", None) is not None:
            return registered_summon_stats(actor, current, self.scene["map_id"])
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=current,
        )
        if actor.id in self.characters:
            return actual_actor_stats(
                self.characters[actor.id], actor, current.id, **values
            )
        return actual_monster_actor_stats(
            self.monsters[actor.id], actor, current.id, **values
        )

    def acknowledge(self):
        for _ in range(32):
            if self.runtime.awaiting_ack is None:
                return
            self.runtime.acknowledge_turn(struct.pack(">i", self.runtime.awaiting_ack))
        raise AssertionError("Native Nox acknowledgment chain exceeded32")

    def advance(self):
        from tools.combat_audit_turns import advance_actual_turn

        self.acknowledge()
        advance_actual_turn(self.runtime)
        self.acknowledge()

    def opening(self):
        self.acknowledge()
        for boundary in range(5):
            if self.fight.current.id == self.identity:
                return boundary
            if boundary == 4:
                break
            self.advance()
        raise AssertionError("No owned opening within four actual Nox boundaries")

    def move(self, path):
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client

        self.acknowledge()
        identity = self.identity
        request = struct.pack(">q", identity) + b"".join(
            struct.pack(">iih", *cell) for cell in path
        )
        return apply_client(
            self.runtime,
            self.characters[identity]["account_id"],
            request,
            lambda actor: self.stats(actor, self.fight),
            runtime_stats_serializer=self.stats,
            area_provider=lambda current, **kw: prepare_area_movement(
                self.characters[identity],
                self.monsters,
                current,
                self.decks[identity],
                **self.common,
                **kw
            ),
        )

    def cast(self, reference, target, *, granted=False):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells

        self.acknowledge()
        identity = self.identity
        uid = (
            granted_spells(self.fight, identity)[reference]["uid"]
            if granted
            else (identity << 32) | reference
        )
        transaction = prepare_server_spell(
            struct.pack(">qqiih", identity, uid, *target),
            self.characters[identity],
            self.monsters,
            self.fight,
            self.characters[identity]["account_id"],
            self.decks[identity],
            action_id=self.runtime.action_id + 1,
            critical=None,
            **self.common,
            line_of_sight=lambda origin, destination, current: authoritative_visible(
                self.scene["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )
        )
        commit_spell_transaction(self.runtime, transaction, stats_serializer=self.stats)
        return transaction
