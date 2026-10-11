"""Real generic native runtime for every installed Stasis profile and level."""
from types import SimpleNamespace
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import dungeon_scaling_catalog, dungeon_combat_scaling


class DungeonScalingRuntimeTests(PostgresCase):
    def test_every_native_profile_and_level_executes_real_generic_runtime(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_npc_initialization import _runtime
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        with self.store.connection() as db:
            supplement = dungeon_scaling_catalog.load(db)
            profiles = db.execute(
                "SELECT value FROM settings WHERE name='dungeon_difficulty_catalog'"
            ).fetchone()["value"]["profiles"]
        self.assertIsNotNone(supplement)
        npc_runtime_catalog.cache_clear()
        self.addCleanup(npc_runtime_catalog.cache_clear)
        cases = 0
        with patch.object(dungeon_scaling_catalog, "current", return_value=supplement):
            for key, profile in profiles.items():
                for index in range(10):
                    with self.subTest(profile=key, stasis=index + 1):
                        actor = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 1, 8)
                        other = Actor(-4, 0, (1, 0, 0), 100, 6, 3, 1, 8)
                        fight = Fight(
                            7,
                            [actor, other],
                            {(0, 0, 0), (1, 0, 0)},
                            {0: {(1, 0, 0)}, 1: {(0, 0, 0)}},
                        )
                        monsters = {
                            a.id: {"id": a.id, "ref": 1} for a in (actor, other)
                        }
                        initialize_fight_snapshots(
                            fight,
                            characters={},
                            monsters=monsters,
                            wp_resources={a.id: (0, 0) for a in (actor, other)},
                            running_effects={a.id: () for a in (actor, other)},
                            initial_effect_uid=100,
                        )
                        before = {
                            identity: a.max_hp for identity, a in fight.actors.items()
                        }
                        snapshot = dict(
                            schema_version=1,
                            instance_id=123,
                            selection_revision=1,
                            stasis_level=index + 1,
                            competitive=True,
                            competitive_max_level=20,
                            hp_percent=profile["hp_percent"][index],
                            damage_percent=profile["damage_percent"][index],
                            reward_rate_bp=profile["competitive_reward_percent"][index]
                            * 100,
                        )
                        db = SimpleNamespace(
                            execute=lambda *args: SimpleNamespace(
                                fetchone=lambda: {"snapshot": snapshot}
                            )
                        )

                        def factory(preview, identity):
                            runtime, _ = _runtime(monsters, identity)
                            dispatcher, _ = runtime(
                                preview,
                                {"native_retained_container": {"present": False}},
                            )
                            return dispatcher

                        preview, receipt = dungeon_combat_scaling.initialize(
                            db,
                            fight,
                            monsters,
                            catalog=supplement,
                            runtime_factory=factory,
                        )
                        self.assertEqual(preview.phase, "placement")
                        self.assertEqual(receipt["profile"], snapshot)
                        for identity, changed in preview.actors.items():
                            expected = before[identity] * snapshot["hp_percent"] / 100
                            self.assertLessEqual(abs(changed.max_hp - expected), 1)
                            self.assertEqual(changed.hp, changed.max_hp)
                            self.assertEqual(
                                fight.actors[identity].max_hp, before[identity]
                            )
                        if snapshot["damage_percent"] != 100:
                            self.assertTrue(preview.native_retained_records)
                        cases += 1
        self.assertEqual(cases, 250)

    def test_native_conditional_damage_executes_after_constructor_receipt(self):
        import test_combat_npc_attack as attack_fixture
        from test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
        )
        from wakfu_server import combat_actor_snapshot as legacy_snapshots
        from wakfu_server.combat_npc_initialization import _runtime
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        with self.store.connection() as db:
            supplement = dungeon_scaling_catalog.load(db)
        npc_runtime_catalog.cache_clear()
        self.addCleanup(npc_runtime_catalog.cache_clear)
        for percent, expected in ((100, 5), (200, 10)):
            with self.subTest(damage_percent=percent):
                fixture = NativeNpcAttackTests()
                # Reuse the authoritative snapshot fixture before its ready call.
                with patch.multiple(
                    attack_fixture, Actor=Actor, Fight=Fight
                ), patch.object(Fight, "ready"), patch.multiple(
                    legacy_snapshots,
                    build_player_snapshot=build_player_snapshot,
                    build_npc_snapshot=build_npc_snapshot,
                ):
                    fixture.setUp()
                monsters = {fixture.npc.id: fixture.monster}
                profile = dict(
                    schema_version=1,
                    instance_id=123,
                    selection_revision=1,
                    stasis_level=5,
                    competitive=True,
                    competitive_max_level=20,
                    hp_percent=100,
                    damage_percent=percent,
                    reward_rate_bp=40000,
                )
                db = SimpleNamespace(
                    execute=lambda *args: SimpleNamespace(
                        fetchone=lambda: {"snapshot": profile}
                    )
                )

                def factory(preview, identity):
                    runtime, _ = _runtime(monsters, identity)
                    dispatcher, _ = runtime(
                        preview, {"native_retained_container": {"present": False}}
                    )
                    return dispatcher

                with patch.object(
                    dungeon_scaling_catalog, "current", return_value=supplement
                ):
                    fixture.fight, receipt = dungeon_combat_scaling.initialize(
                        db,
                        fixture.fight,
                        monsters,
                        catalog=supplement,
                        runtime_factory=factory,
                    )
                    self.assertTrue(receipt["initialized"])
                    fixture.pc = fixture.fight.actors[7]
                    fixture.npc = fixture.fight.actors[-200]
                    fixture.fight.ready(9)
                    before = fixture.pc.hp
                    from wakfu_server.combat_npc_attack import execute

                    with patch.object(attack_fixture, "execute", execute), patch(
                        "wakfu_server.combat_npc_attack.static_visible",
                        return_value=True,
                    ):
                        fixture.run_attack()
                self.assertEqual(before - fixture.pc.hp, expected)
