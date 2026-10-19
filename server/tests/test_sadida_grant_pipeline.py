"""Sadida acquired seed, tree and Voodoll actions through actual native casting."""
import os
import struct
import unittest

import test_sadida_initialization_pipeline as initialization


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaGrantPipelineTests(unittest.TestCase):
    fixture = initialization.SadidaInitializationPipelineTests.fixture

    def cast(self, data, reference, *, target=None, action_id=10):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng, _ = data
        grants = granted_spells(fight, 7)
        identity = (
            grants[reference]["uid"] if reference in grants else (7 << 32) | reference
        )
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=action_id, critical=False, rng=rng
        )

        def los(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        if target is None:
            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                identity,
                adapter=adapter,
                line_of_sight=los,
                actor_id=7,
                limit=128,
                maximum_eligible=16,
            )
            self.assertTrue(selection["eligible"], selection)
            candidates = selection["eligible"]
            if reference == 8137:
                occupied = {a.position for a in fight.actors.values() if a.hp > 0}
                candidates = [
                    row for row in candidates if tuple(row["target"]) not in occupied
                ]
                self.assertTrue(candidates, selection)
            target = candidates[0]["target"]
        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, identity, *target),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return tx

    def test_actual_semilla_produces_owned_seed_area(self):
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        tx = self.cast(data, 8137)
        self.assertTrue(tx.fight.native_effect_areas)
        areas = list(tx.fight.native_effect_areas.values())
        self.assertTrue(
            any(a.get("reference") == 1835 for a in areas),
            [(a.get("reference"), a.get("caster_id")) for a in areas],
        )
        current_registry(tx.fight)

    def test_paid_seed_reconnect_projects_live_creator_once_and_does_not_resurrect_retired_seed(
        self,
    ):
        import json
        from types import SimpleNamespace

        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_remote_effects import decode_remote_effects
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_wire import arena, decode_actor_state, decode_bootstrap
        from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot

        data = self.fixture()
        character, monster, initial_fight = data[:3]
        seed_cell = (-7, -7, -1)
        self.assertIn(seed_cell, initial_fight.walkable)
        self.assertNotIn(
            seed_cell,
            {actor.position for actor in initial_fight.actors.values() if actor.hp > 0},
        )
        seed = self.cast(data, 8137, target=seed_cell, action_id=10)
        fight = seed.fight
        seed_areas = {
            int(row["uid"]): row
            for row in fight.native_effect_areas.values()
            if row.get("reference") == 1835 and row.get("owner_id") == 7
        }
        expected_creators = {
            int(uid): row["effect_class"]
            for uid, row in fight.native_owned_area_effects.items()
            if row.get("executed") is True
            and row.get("native_private_area") is None
            and row.get("area_uid") in seed_areas
        }
        self.assertTrue(seed_areas)
        self.assertTrue(expected_creators)
        self.assertEqual(seed.plan["costs"]["wp"], 1)

        # This is the actual checkpoint container round-trip supported by the
        # server. Reconnection below operates on the still-authoritative fight;
        # it does not claim to restore a Fight object from a JSON checkpoint.
        checkpoint = snapshot(fight)
        checkpoint_copy = Checkpoints._read_snapshot(json.loads(json.dumps(checkpoint)))
        checkpoint_areas = {
            int(uid): row for uid, row in checkpoint_copy["native_effect_areas"].items()
        }
        for area_uid, row in seed_areas.items():
            restored = checkpoint_areas[area_uid]
            for key in (
                "uid",
                "reference",
                "effect_uid",
                "owner_id",
                "level",
                "direction",
                "native_area_contract",
            ):
                self.assertEqual(restored[key], row[key], (area_uid, key))
            self.assertEqual(tuple(restored["cell"]), tuple(row["cell"]))

        shared = SimpleNamespace(
            runtime=SimpleNamespace(
                native_action_id=900,
                turn_deadline=None,
                awaiting_ack=None,
            ),
            map_id=character["map_id"],
            instance_id=0,
            is_duel=False,
            join_context=dict(
                arena=arena(
                    character["map_id"],
                    0,
                    fight.walkable,
                    {0: fight.actors[7].position, 1: fight.actors[-7].position},
                ),
                terrain_effect_id=99,
                terrain_instance_id=0,
                leaders={0: 7, 1: -7},
                monsters={-7: dict(monster, level=fight.actors[-7].effective_level)},
            ),
        )
        adapter = SimpleNamespace(
            store=SimpleNamespace(character=lambda _account_id, _identity: character),
            registry=SimpleNamespace(lookup=lambda _identity: shared),
        )
        session = SimpleNamespace(account_id=character["account_id"], character_id=7)

        def actor_payload(current_fight, actor, current_session):
            return CombatSessionAdapter.actor_payload(
                adapter, current_fight, actor, current_session
            )

        def inspect_owner(current_fight, action_id):
            before = snapshot(current_fight)
            shared.runtime.native_action_id = action_id
            packets = owned_snapshot(
                current_fight, shared, session, actor_payload=actor_payload
            )
            bootstrap = decode_bootstrap(
                next(payload for opcode, payload in packets if opcode == 12847)
            )
            owner = next(
                row for row in bootstrap["participants"] if row["actor_id"] == 7
            )
            bootstrap_ids = {
                _identity_fields(row.payload, integer_fields=(1,)).get(1)
                for row in decode_remote_effects(owner["myF"])
            }
            reset_ids = set()
            for opcode, payload in packets:
                if opcode != 13912:
                    continue
                state = decode_actor_state(opcode, payload)
                if state["actor_id"] == 7:
                    reset_ids = {
                        _identity_fields(row.payload, integer_fields=(1,)).get(1)
                        for row in decode_remote_effects(state["state"])
                    }
                    break
            carrier_ids = set()
            for opcode, payload in packets:
                if opcode != 12613 or len(payload) < 19:
                    continue
                _, _, _, _, _, size = struct.unpack_from(">iiiBih", payload)
                carrier_ids.add(
                    _identity_fields(payload[19 : 19 + size], integer_fields=(1,)).get(
                        1
                    )
                )
            self.assertEqual(snapshot(current_fight), before)
            return bootstrap_ids, reset_ids, carrier_ids

        bootstrap_ids, reset_ids, carrier_ids = inspect_owner(fight, 900)
        self.assertTrue(expected_creators.keys().isdisjoint(bootstrap_ids))
        self.assertTrue(expected_creators.keys().isdisjoint(reset_ids))
        self.assertTrue(expected_creators.keys() <= carrier_ids)

        # A real transformation consumes the same seed area; the next owned
        # reconnect must not recreate its retired native area from stale Qf data.
        tree = self.cast(
            (*data[:2], fight, *data[3:]), 8137, target=seed_cell, action_id=11
        )
        from wakfu_server.combat_summon_spellbook import actor_action_book

        self.assertTrue(
            any(
                getattr(actor, "native_summon_source", None)
                and actor.hp > 0
                and actor_action_book(actor)["profile"] == 5577
                for actor in tree.fight.actors.values()
            )
        )
        self.assertTrue(seed_areas.keys().isdisjoint(tree.fight.native_effect_areas))
        after_bootstrap, after_reset, after_carriers = inspect_owner(tree.fight, 901)
        current_owner_effects = CombatSessionAdapter.actor_payload(
            adapter, tree.fight, tree.fight.actors[7], session
        )[1]
        current_qf_ids = {
            _identity_fields(row.payload, integer_fields=(1,)).get(1)
            for row in decode_remote_effects(current_owner_effects)
        }
        live_current_area_creators = {
            int(uid)
            for uid, row in tree.fight.native_owned_area_effects.items()
            if row.get("executed") is True
            and row.get("native_private_area") is None
            and row.get("area_uid") in tree.fight.native_effect_areas
        }
        expected_owner_state = current_qf_ids - live_current_area_creators
        # The actual tree can add another live Qs creator, so only exclude its
        # creator from the ordinary Qf owner body. Retired seed Qs creators
        # follow the actual current Qf snapshot and must never be replayed as
        # 12613 carriers.
        self.assertEqual(after_bootstrap, expected_owner_state)
        self.assertEqual(after_reset, expected_owner_state)
        self.assertTrue(expected_creators.keys().isdisjoint(after_carriers))

    def test_actual_vudul_grant_registers_profile_and_native_book(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned
        from wakfu_server.combat_qi_fight import current_registry

        tx = self.cast(self.fixture(), 926)
        actors = [
            a
            for a in tx.fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        ]
        self.assertEqual(len(actors), 1)
        actor = actors[0]
        self.assertEqual(actor_action_book(actor)["profile"], 3745)
        self.assertEqual(
            {a["reference"] for a in actor_action_book(actor)["actions"]}, {8140}
        )
        self.assertTrue(fresh_summon_slot_owned(tx.fight, actor))
        self.assertEqual(actor.team, tx.fight.actors[7].team)
        self.assertIn(3616, {s.reference for s in actor.state_ledger.entries})
        current_registry(tx.fight)
