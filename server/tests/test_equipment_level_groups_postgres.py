"""Actual owned Neo groups: saved builds, authority, Ready and recovery."""
import json
from random import Random
from types import SimpleNamespace
import uuid

from postgres_case import PostgresCase
from wakfu_server import builds, health_store, wire
from wakfu_server.character_levels import XP_BY_LEVEL
from wakfu_server.equipment import RULES
from wakfu_server.equipment_stats import bonuses, combat_resources
from wakfu_server.inventory_items import grant
from wakfu_server.equipment_level_groups import project


class EquipmentLevelGroupsPostgresTests(PostgresCase):
    def _owner(self, level):
        token = uuid.uuid4().hex[:8]
        account = self.store.register("group-" + token, "local-password")["id"]
        name = "Group " + token.translate(str.maketrans("0123456789", "abcdefghij"))
        owner = self.store.create_character(account, name, breed=1)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s,map_id=1134,instance_id=0,x=-8,y=-7,z=-1 WHERE id=%s",
                (level, owner["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[level], owner["id"]),
            )
        return (
            account,
            generation,
            health_store.initialize(self.store, account, generation, owner["id"]),
        )

    def _mode(self, enabled):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES('dungeon_server_mode',%s::jsonb) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (json.dumps(dict(version=1, is_neo_server=enabled)),),
            )

    def _save(self, account, generation, owner, item=None, level=None):
        level = owner["level"] if level is None else level
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in ((8, 0), (18, b"Native group"), (24, level), (56, 0))
        )
        equipment = (
            builds.EMPTY_EQUIPMENT
            if item is None
            else wire.proto_field(
                10,
                wire.proto_field(8, item["uid"])
                + wire.proto_field(16, RULES[item["reference"]]["slots"][0]),
            )
        )
        return self.store.save_build(
            account,
            generation,
            owner["id"],
            0,
            dict(sheet=sheet, equipment=equipment, deck=b"", aptitudes=b""),
        )

    def _grant(self, account, generation, owner, reference, slot):
        container = next(
            r["uid"] for r in owner["inventory_containers"] if r["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            owner["id"],
            reference=reference,
            quantity=1,
            container=container,
            slot=slot,
            allowed_references={reference},
        )

    def _completed_fixture(self, owner):
        # These original achievements are application preconditions, not new
        # gameplay completion routes. Use actual owned authority persistence.
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_achievement_authority SET snapshot=%s::jsonb WHERE character_id=%s",
                (
                    json.dumps(
                        dict(running=[], completed=[5614, 5618, 5622], objectives=[])
                    ),
                    owner["id"],
                ),
            )

    def test_upgraded_source_still_requires_actual_owned_completion(self):
        self._mode(True)
        account, generation, owner = self._owner(245)
        item = self._grant(account, generation, owner, 32705, 0)
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self._save(account, generation, owner, item)
        saved = self.store.character(account, owner["id"])
        self.assertTrue(
            any(
                row["uid"] == item["uid"] and row["quantity"] == 1
                for row in saved["inventory_items"]
            )
        )

    def test_all_four_actual_sources_levels_mode_authority_siblings_and_removal(self):
        from wakfu_server.profession_equipment_modifiers import aggregate
        from wakfu_server.combat_static_catalogs import characteristic_registry

        damage = characteristic_registry()["effects"]["120"]["fixed_stat_id"]
        for level in (1, 245):
            account, generation, owner = self._owner(level)
            self._completed_fixture(owner)
            self._mode(True)
            owner = self.store.character(account, owner["id"])
            self.assertIs(owner["equipment_criterion_context"]["is_neo_server"], True)
            baseline = bonuses(owner)
            base_resources = combat_resources(owner)
            base_hp = owner["max_hp"]
            for slot, (reference, ratio, hp_ratio, willpower, increments) in enumerate(
                (
                    (32704, 100, 200, 5, (0, 0, 0)),
                    (32705, 150, 300, 10, (0, 1, 0)),
                    (32706, 200, 400, 15, (0, 1, 2)),
                    (32707, 200, 400, 20, (1, 1, 2)),
                )
            ):
                with self.subTest(level=level, reference=reference):
                    item = self._grant(account, generation, owner, reference, slot)
                    equipped = self._save(account, generation, owner, item)
                    result = bonuses(equipped)
                    self.assertEqual(result["unsupported"], [])
                    self.assertEqual(
                        result["stats"][damage] - baseline["stats"].get(damage, 0),
                        level * ratio // 100,
                    )
                    self.assertEqual(
                        result["stats"][1] - baseline["stats"].get(1, 0),
                        level * hp_ratio // 100,
                    )
                    self.assertEqual(
                        result["stats"][86] - baseline["stats"].get(86, 0), willpower
                    )
                    self.assertEqual((result["stats"][9], result["stats"][87]), (3, 3))
                    self.assertEqual(
                        equipped["max_hp"], base_hp + level * hp_ratio // 100
                    )
                    resources = combat_resources(equipped)
                    self.assertEqual(
                        tuple(resources[k] for k in ("ap", "mp", "wp")),
                        tuple(
                            base_resources[k] + n
                            for k, n in zip(("ap", "mp", "wp"), increments)
                        ),
                    )
                    self.assertEqual(
                        aggregate(equipped, 64, is_neo_server=True)["collect_quantity"],
                        50,
                    )
                    reopened = self.store.character(account, owner["id"])
                    self.assertEqual(
                        bonuses(reopened)["stat_operations"], result["stat_operations"]
                    )
                    self.assertTrue(
                        any(
                            r["uid"] == item["uid"] and r["quantity"] == 1
                            for r in reopened["inventory_items"]
                        )
                    )
                    self._mode(False)
                    disabled = self.store.character(account, owner["id"])
                    self.assertEqual(bonuses(disabled)["stats"], baseline["stats"])
                    self.assertEqual(
                        aggregate(disabled, 64, is_neo_server=False)[
                            "collect_quantity"
                        ],
                        0,
                    )
                    self._mode(True)
                    cleared = self._save(
                        account, generation, self.store.character(account, owner["id"])
                    )
                    self.assertEqual(bonuses(cleared)["stats"], baseline["stats"])
                    self.assertEqual(cleared["max_hp"], base_hp)
                    owner = cleared

    def _ready(self, owner, account):
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
            actor_effects,
        )
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck

        arena = local_arena(
            1134, 1, (-8, -7, -1), (-5, -7, -1), relocate_monsters=False, compact=True
        )
        monster = owned_instance(4168, 190, -200, map_id=1134, x=-5, y=-7, z=-1)
        resources = combat_resources(owner)
        fight, _ = create_placement(
            owner,
            monster,
            arena,
            fight_id=7,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=9001,
        )
        initialize_fight_snapshots(
            fight,
            characters={owner["id"]: owner},
            monsters={-200: monster},
            wp_resources={
                owner["id"]: (resources["wp"], resources["wp"]),
                -200: (monster["wp"], monster["wp"]),
            },
            running_effects={owner["id"]: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        initial_stats = dict(fight.actors[owner["id"]].effect_stats)
        deck, rng = encode_deck([6972]), Random(7)

        def actor_payload(f, actor, recipient=None):
            if actor.controlled:
                result = actual_actor_stats(
                    owner,
                    actor,
                    7,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )
            else:
                result = actual_monster_actor_stats(
                    monster,
                    actor,
                    7,
                    wp_current=monster["wp"],
                    wp_maximum=monster["wp"],
                )
            return result, actor_effects()

        started, runtime, packets = prepare_ready(
            fight,
            account,
            True,
            initialize=lambda preview, action: prepare_server_initialization(
                owner,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action,
                rng=rng,
                fight_start=True,
            ),
            stats_serializer=lambda actor: actor_payload(fight, actor)[0],
            effects_serializer=actor_effects,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                owner,
                {-200: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        return started, runtime, packets, arena, actor_payload, initial_stats

    def test_adjusted_level_ready_no_double_and_typed_reconnect(self):
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_protocol_reconstruction import decode_packet

        self._mode(True)
        account, generation, owner = self._owner(245)
        self._completed_fixture(owner)
        item = self._grant(account, generation, owner, 32705, 0)
        owner = self._save(account, generation, owner, item, level=50)
        damage = characteristic_registry()["effects"]["120"]["fixed_stat_id"]
        self.assertEqual((owner["level"], owner["effective_level"]), (245, 50))
        before = bonuses(owner)
        self.assertEqual((before["stats"][damage], before["stats"][1]), (75, 150))
        self.assertEqual(plan(owner, ordinary_only=True), ())
        fight, runtime, packets, arena, actor_payload, initial_stats = self._ready(
            owner, account
        )
        actor = fight.actors[owner["id"]]
        self.assertEqual(actor.max_hp, owner["max_hp"])
        self.assertEqual(actor.effect_stats[damage], initial_stats[damage])
        self.assertEqual(initial_stats[damage], 75)
        roots = {
            r["id"]
            for r in project(
                32705,
                actor_level=50,
                container_level=0,
                criterion_context={"is_neo_server": True},
            )
        }
        from wakfu_server.combat_protocol_reconstruction import _effect

        definitions = {
            _effect(bytes.fromhex(row["payload"]), row["effect_class"])["definition"]
            for row in fight.owned_stat_effects.values()
        }
        self.assertFalse(definitions & roots)
        stable = snapshot(fight)
        restored = decode_state(encode_state(fight))
        self.assertEqual(snapshot(restored), stable)
        runtime.fight = restored
        shared = SimpleNamespace(
            runtime=runtime,
            map_id=1134,
            instance_id=0,
            join_context=dict(
                arena=arena,
                terrain_effect_id=46,
                terrain_instance_id=9001,
                leaders={0: owner["id"], 1: -200},
            ),
        )
        session = Session(account, owner["id"], "group-reconnect", 1134, 0)
        stream = owned_snapshot(restored, shared, session, actor_payload=actor_payload)
        self.assertEqual(snapshot(restored), stable)
        rows = [decode_packet(op, body) for op, body in stream if op == 12613]
        self.assertFalse(any(row["effect"]["definition"] in roots for row in rows))
        reopened = self.store.character(account, owner["id"])
        self.assertEqual(bonuses(reopened)["stats"], before["stats"])
        cleared = self._save(account, generation, reopened, level=50)
        self.assertNotIn(damage, bonuses(cleared)["stats"])
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in cleared["inventory_items"])
        )
