"""Owned Dofus source through real Ready, paid NPC damage and owned turn clocks."""
from copy import deepcopy
from random import Random
from types import SimpleNamespace

from postgres_case import PostgresCase
import test_equipment_level_groups_postgres as _owned_fixture
from test_equipment_hp_threshold_pipeline import advance_actual_turn
from wakfu_server.equipment_stats import bonuses, combat_resources
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_terrain import local_arena
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_retained_runtime import native_retained_condition_effects
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentOpposedDamagePostgresTests(PostgresCase):
    _owner = _owned_fixture.EquipmentLevelGroupsPostgresTests._owner
    _grant = _owned_fixture.EquipmentLevelGroupsPostgresTests._grant
    _save = _owned_fixture.EquipmentLevelGroupsPostgresTests._save

    def test_owned_complete_source_paid_damage_pending_once_start_expiry_and_recovery(
        self,
    ):
        account, generation, char = self._owner(245)
        baseline = bonuses(char)
        item = self._grant(account, generation, char, 33395, 0)
        char = self._save(account, generation, char, item, level=170)
        registry = characteristic_registry()["effects"]
        damage_pc, buff_pc = (
            registry["120"]["fixed_stat_id"],
            registry["126"]["fixed_stat_id"],
        )
        equipment = bonuses(char)
        self.assertEqual(
            equipment["stats"][damage_pc] - baseline["stats"].get(damage_pc, 0), 170
        )
        self.assertEqual(equipment["stats"][9] - baseline["stats"].get(9, 0), 3)
        resources = combat_resources(char)
        deck, rng = encode_deck([6972]), Random(33395)
        monster = owned_instance(1, 8, -200, map_id=1134, x=-7, y=-7, z=-1)
        arena = local_arena(
            1134,
            1,
            (-8, -7, -1),
            (-7, -7, -1),
            relocate_monsters=False,
            compact=True,
            minimum_dimensions=(9, 9),
        )
        fight, _ = create_placement(
            char,
            monster,
            arena,
            fight_id=33395,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=9001,
        )
        initialize_fight_snapshots(
            fight,
            characters={char["id"]: char},
            monsters={-200: monster},
            wp_resources={
                char["id"]: (resources["wp"], resources["wp"]),
                -200: (monster["wp"], monster["wp"]),
            },
            running_effects={char["id"]: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        owner = char["id"]
        before = dict(fight.actors[owner].effect_stats)

        def stats(actor, preview=None):
            if actor.controlled:
                return actual_actor_stats(
                    char,
                    actor,
                    33395,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                33395,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            )

        started, runtime, _ = prepare_ready(
            fight,
            account,
            True,
            initialize=lambda preview, action: prepare_server_initialization(
                char,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action,
                rng=rng,
                fight_start=True,
            ),
            stats_serializer=stats,
            runtime_stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                char, {-200: monster}, preview, deck, rng=rng, **boundary
            ),
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                char,
                {-200: monster},
                preview,
                deck,
                rng=rng,
                area_callbacks=True,
                **boundary
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                char,
                {-200: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        self.assertEqual(
            started.actors[owner].effect_stats[damage_pc], before[damage_pc]
        )
        self.assertEqual(
            len(
                [
                    s
                    for s in started.actors[owner].state_ledger.entries
                    if s.reference == 9364
                ]
            ),
            1,
        )
        initial_buff = started.actors[owner].effect_stats[buff_pc]

        def wait_for(actor_id):
            for _ in range(2 * len(runtime.fight.actors) + 1):
                if runtime.fight.current.id == actor_id:
                    return
                advance_actual_turn(runtime)
            self.fail("Actual turn boundary did not select expected actor")

        def pending():
            return tuple(
                row
                for row in native_retained_condition_effects(runtime.fight, owner)
                if row[0] == 417989
            )

        wait_for(-200)
        old_hp = runtime.fight.actors[owner].hp
        tx = prepare_npc_spell(
            runtime.fight,
            dict(
                type="cast",
                spellId=5767,
                level=8,
                targetId=owner,
                target=list(runtime.fight.actors[owner].position),
            ),
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            rng=rng,
        )
        self.assertGreater(tx.plan["costs"]["ap"], 0)
        self.assertLess(tx.fight.actors[owner].hp, old_hp)
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        self.assertEqual(len(pending()), 1)
        waiting_uid = pending()[0][2]
        self.assertFalse(
            any(
                s.reference == 9365
                for s in runtime.fight.actors[owner].state_ledger.entries
            )
        )

        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.combat_reproduction_actions import (
            bind_runtime,
            AUTHORITY_RECIPE,
        )
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_protocol_reconstruction import decode_packet

        stable = snapshot(runtime.fight)
        runtime.fight = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(runtime.fight), stable)
        bind_runtime(
            runtime,
            dict(
                authority_recipe=AUTHORITY_RECIPE,
                character=char,
                monsters={-200: monster},
                deck_blob=deck,
                player_characters={owner: char},
                deck_blobs={owner: deck},
                map_id=1134,
                native_events=True,
                area_callbacks=True,
            ),
            rng,
            runtime.clock,
        )
        shared = SimpleNamespace(
            runtime=runtime,
            map_id=1134,
            instance_id=0,
            join_context=dict(
                arena=arena,
                terrain_effect_id=46,
                terrain_instance_id=9001,
                leaders={0: owner, 1: -200},
            ),
        )
        stream = owned_snapshot(
            runtime.fight,
            shared,
            Session(account, owner, "dofus-recovery", 1134, 0),
            actor_payload=lambda f, actor, recipient: (stats(actor), actor_effects()),
        )
        rows = [decode_packet(op, body) for op, body in stream if op == 12613]
        self.assertEqual(len([r for r in rows if r["effect"]["uid"] == waiting_uid]), 1)
        self.assertEqual(snapshot(runtime.fight), stable)
        # This actual native spell allows only one cast per target. Preserve
        # that restriction; a rejected retry must not change the retained wait.
        retry_before = snapshot(runtime.fight)
        with self.assertRaisesRegex(ValueError, "maximum casts per target"):
            prepare_npc_spell(
                runtime.fight,
                dict(
                    type="cast",
                    spellId=5767,
                    level=8,
                    targetId=owner,
                    target=list(runtime.fight.actors[owner].position),
                ),
                char,
                {-200: monster},
                deck,
                action_id=runtime.action_id + 1,
                rng=rng,
            )
        self.assertEqual(snapshot(runtime.fight), retry_before)
        self.assertEqual([r[2] for r in pending()], [waiting_uid])
        wait_for(owner)
        self.assertEqual(
            runtime.fight.actors[owner].effect_stats[buff_pc], initial_buff + 10
        )
        self.assertEqual(
            len(
                [
                    s
                    for s in runtime.fight.actors[owner].state_ledger.entries
                    if s.reference == 9365
                ]
            ),
            1,
        )
        advance_actual_turn(runtime)
        wait_for(owner)
        self.assertFalse(
            any(
                s.reference == 9365
                for s in runtime.fight.actors[owner].state_ledger.entries
            )
        )
        self.assertEqual(
            runtime.fight.actors[owner].effect_stats[buff_pc], initial_buff
        )
        # Remove the original source through the retained inverse registry.
        preview = deepcopy(runtime.fight)
        state = next(
            s for s in preview.actors[owner].state_ledger.entries if s.reference == 9364
        )
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _ = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retention = dispatcher.native_retention
        retention.removal(retention.view()).remove((state.uid,))
        retention.synchronize()
        self.assertFalse(
            any(s.reference == 9364 for s in preview.actors[owner].state_ledger.entries)
        )
        self.assertEqual(
            preview.actors[owner].effect_stats[damage_pc], before[damage_pc]
        )
        cleared = self._save(
            account, generation, self.store.character(account, owner), level=170
        )
        self.assertNotIn(damage_pc, bonuses(cleared)["stats"])
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in cleared["inventory_items"])
        )
