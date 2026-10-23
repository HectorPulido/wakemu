"""Durable owned-companion combat, settlement, report, and return cycle."""
import copy
import struct

from test_combat_companions_postgres import OwnedCompanionCombatPostgresTests
from wakfu_server.inventory_items import grant


class CompanionCombatLifecyclePostgresTests(OwnedCompanionCombatPostgresTests):
    def test_companion_checkpoint_settlement_report_return_and_readmission(self):
        from wakfu_server import fight_store
        from wakfu_server.characters import companion_equipment, companions
        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.combat_lifecycle import prepare_finish_shared, return_to_world
        from wakfu_server.combat_rewards import Policy
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_companions import loot_profiles, native_stats
        from wakfu_server.combat_drops import resolve as resolve_drops, report_loots
        from wakfu_server.combat_drop_delivery import apply as deliver_drops
        from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook
        from wakfu_server.wire import proto_fields

        # The shared fixture creates a placement row for admission. Close that
        # unused row so a genuine owned equipment save can precede the fight.
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='aborted' WHERE id=%s",
                (self.fight_id,),
            )
        self.container = next(
            row["uid"] for row in self.main["inventory_containers"] if row["kind"] == 0
        )
        gear = self._grant(13601, slot=0)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                "VALUES(%s,4,8) ON CONFLICT(uid) DO UPDATE SET damage_elements=4,resistance_elements=8",
                (gear["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) "
                "VALUES(%s,false,13601) ON CONFLICT(uid) DO UPDATE SET bound=false,template_reference=13601",
                (gear["uid"],),
            )
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self._save_body(self.companion_id, gear["uid"]),
            in_fight=False,
        )

        # Reopen a new durable placement after equipment custody is committed.
        self.fight_id = fight_store.create(
            self.store, self.account, self.generation, self.main["id"], team=0
        )
        self.fight.id = self.fight_id
        placement_template = copy.deepcopy(self.fight)
        with self.store.connection() as db:
            admitted = self._admit(db)
        self.fight = admitted["fight"]

        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        ready = CombatSessionAdapter(self.store).ready_transition(
            self.session, self.fight, None, True, {-200: self.enemy}
        )
        fight = ready.fight
        actor = fight.actors[self.companion_id]
        source = fight.native_companion_sources[str(self.companion_id)]
        self.assertEqual(5, source["native_actor_type"])
        self.assertEqual(self.account, actor.owner_id)
        self.assertTrue(actor.controlled)
        self.assertTrue(source["equipment_stat_bonuses"])
        self.assertEqual(source["max_hp"], actor.max_hp)
        self.assertEqual(
            gear["uid"], source["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        self.assertIn(
            "inventory_item_elements",
            source["equipment_entries"][0]["entry"]["metadata"],
        )
        self.assertEqual(
            4,
            source["equipment_entries"][0]["entry"]["metadata"][
                "inventory_item_elements"
            ]["damage_elements"],
        )
        self.assertFalse(
            source["equipment_entries"][0]["entry"]["metadata"][
                "inventory_item_bindings"
            ]["bound"]
        )
        spellbook = ordinary_npc_spellbook(fight, actor, source)
        self.assertTrue(spellbook.levels)
        spell_uid = next(iter(spellbook.levels))
        self.assertGreater(companions.level_for_xp(source["xp"]), 0)

        # Persist and decode the actual source, actor kind/controller, gear and
        # native spell authority through the production checkpoint boundary.
        checkpoints = Checkpoints(self.store)
        revision = checkpoints.save(self.account, self.generation, fight)
        saved = checkpoints.read(self.account, self.fight_id)
        restored = Checkpoints._read_snapshot(saved["snapshot"])
        self.assertEqual(revision, saved["revision"])
        restored_source = restored["native_companion_sources"][str(self.companion_id)]
        self.assertEqual(5, restored_source["native_actor_type"])
        self.assertEqual(self.main["id"], restored_source["owner_character_id"])
        self.assertEqual(
            source["equipment_stat_bonuses"],
            {
                int(key): value
                for key, value in restored_source["equipment_stat_bonuses"].items()
            },
        )
        self.assertEqual(source["max_hp"], restored_source["max_hp"])
        self.assertEqual(
            list(source["equipment_entries"]), restored_source["equipment_entries"]
        )
        self.assertEqual(
            gear["uid"], restored_source["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        self.assertEqual(
            source["equipment_entries"][0]["entry"]["metadata"],
            restored_source["equipment_entries"][0]["entry"]["metadata"],
        )
        self.assertIn(
            spell_uid, [row["spell_id"] for row in restored_source["native_abilities"]]
        )
        restored_actor = restored["actors"][str(self.companion_id)]
        self.assertTrue(restored_actor["controlled"])
        self.assertEqual(self.account, restored_actor["owner_id"])

        # Finish from the prepared native roster. A low sidekick HP tests the
        # native postfight full-heal rule while the owner earns a known 100 XP.
        actor.hp = 1
        fight.actors[-200].hp = 0
        fight.phase, fight.winner = "finished", 0
        runtime = RuntimeMessages(fight)
        calls = {"rng": 0}

        def loot_resolver(db, member, reward):
            profiles = loot_profiles(fight, member["character_id"])
            batch = resolve_drops(
                self.store,
                db,
                account_id=member["account_id"],
                generation=member["session_generation"],
                character_id=member["character_id"],
                fight_id=fight.id,
                monsters=[{"actor_id": -200, "reference": 5525}],
                prospecting_bonus=0,
                can_loot=True,
                fight_context={},
                rng=lambda upper: (calls.__setitem__("rng", calls["rng"] + 1) or 0),
                companion_rolls=profiles,
            )
            packets = deliver_drops(self.store, db, batch)
            return {"loots": report_loots(batch), "packets": packets}

        metadata = {
            self.main["id"]: dict(
                kind="player",
                account_id=self.account,
                name=self.main["name"],
                breed=self.main["breed"],
                is_male=self.main["sex"] == 0,
            ),
            -200: dict(kind="monster", ref=5525),
            self.companion_id: dict(kind="monster", ref=source["ref"]),
        }
        kwargs = dict(
            duration_ms=1200,
            fight_instance_id=fight.id,
            policy_resolver=lambda *_: Policy(xp=100, kamas=0),
            loot_resolver=loot_resolver,
            expected_accounts={self.account},
        )
        owner_packets = prepare_finish_shared(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            runtime,
            metadata,
            **kwargs
        )

        with self.store.connection() as db:
            settled = db.execute(
                "SELECT c.xp,c.hp,c.max_hp,p.owner_experience_award,p.experience_award,"
                "p.experience_settled_at,p.health_settled_at FROM account_companions c "
                "JOIN combat_fight_companions p ON p.companion_id=c.id "
                "WHERE c.id=%s AND p.fight_id=%s",
                (self.companion_id, fight.id),
            ).fetchone()
            reward = db.execute(
                "SELECT xp FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight.id, self.main["id"]),
            ).fetchone()
            batch_snapshot = db.execute(
                "SELECT snapshot FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s",
                (fight.id, self.main["id"]),
            ).fetchone()["snapshot"]
        expected_max = native_stats(
            source["ref"],
            source["level"],
            equipment_entries=source["equipment_entries"],
            owner=self.main,
        )["max_hp"]
        self.assertEqual(100, reward["xp"])
        self.assertEqual(150, settled["xp"])
        self.assertEqual(
            (100, 150), (settled["owner_experience_award"], settled["experience_award"])
        )
        self.assertIsNotNone(settled["experience_settled_at"])
        self.assertIsNotNone(settled["health_settled_at"])
        self.assertEqual(
            (expected_max, expected_max), (settled["hp"], settled["max_hp"])
        )
        self.assertEqual(
            [self.companion_id],
            [row["actor_id"] for row in batch_snapshot["companion_rolls"]],
        )

        report_packet = next(
            body for opcode, body in owner_packets[self.account] if opcode == 12755
        )
        report = dict(proto_fields(report_packet[12:]))
        npc_rows = [
            dict(proto_fields(value))
            for tag, value in proto_fields(report[42])
            if tag == 26
        ]
        report_companion = next(
            row for row in npc_rows if row.get(8) == self.companion_id
        )
        self.assertEqual(self.account, report_companion[16])
        xp_info = dict(proto_fields(report_companion[42]))
        self.assertEqual((150, 150), (xp_info[8], xp_info[16]))
        companion_loots = [
            dict(proto_fields(value))
            for tag, value in proto_fields(report_companion.get(34, b""))
            if tag == 34
        ]
        # This actual NPC (5525) has no successful loot rows in its native drop
        # table. The committed companion-roll profile is still present above;
        # the report must accurately carry an empty loot line.
        self.assertFalse(companion_loots)

        # Replaying the exact prepared settlement reuses owner/drop receipts;
        # the RNG must not run again and neither sidekick XP nor HP is doubled.
        rng_calls = calls["rng"]
        replay_packets = prepare_finish_shared(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            runtime,
            metadata,
            **kwargs
        )
        self.assertEqual(rng_calls, calls["rng"])
        original_reports = [
            body for opcode, body in owner_packets[self.account] if opcode == 12755
        ]
        replay_reports = [
            body for opcode, body in replay_packets[self.account] if opcode == 12755
        ]
        self.assertEqual(len(original_reports), len(replay_reports))
        # The native report packet carries a per-send action sequence in its
        # first eight bytes; compare the serialized fight report payload.
        self.assertEqual(
            [body[8:] for body in original_reports],
            [body[8:] for body in replay_reports],
        )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                150,
                db.execute(
                    "SELECT xp FROM account_companions WHERE id=%s",
                    (self.companion_id,),
                ).fetchone()["xp"],
            )

        returned = return_to_world(
            self.store,
            self.account,
            self.generation,
            self.store.character(self.account, self.main["id"]),
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        self.assertTrue(returned["applied"])

        # A fresh durable fight admits the same account-owned companion again.
        next_fight_id = fight_store.create(
            self.store, self.account, self.generation, self.main["id"], team=0
        )
        next_fight = placement_template
        next_fight.id = next_fight_id
        with self.store.connection() as db:
            admitted_again = self._admit(db, next_fight)
            membership = db.execute(
                "SELECT account_id,owner_character_id,team FROM combat_fight_companions "
                "WHERE fight_id=%s AND companion_id=%s",
                (next_fight_id, self.companion_id),
            ).fetchone()
        self.assertEqual((self.account, self.main["id"], 0), tuple(membership.values()))
        self.assertIn(self.companion_id, admitted_again["fight"].actors)
        self.assertEqual(
            source["equipment_stat_bonuses"],
            {
                int(key): value
                for key, value in admitted_again["sources"][self.companion_id][
                    "equipment_stat_bonuses"
                ].items()
            },
        )
        self.assertEqual(
            source["max_hp"], admitted_again["sources"][self.companion_id]["max_hp"]
        )
        self.assertEqual(
            gear["uid"],
            admitted_again["sources"][self.companion_id]["equipment_entries"][0][
                "entry"
            ]["item"]["uid"],
        )

    def _admit(self, db, fight=None):
        from wakfu_server.combat_companions import admit_owned_companions

        return admit_owned_companions(
            db,
            self.store,
            self.session,
            self.fight if fight is None else fight,
            owner_character=self.main,
        )

    def _grant(self, reference, *, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    @staticmethod
    def _save_body(identity, uid, slot=0):
        return struct.pack(">qhBbq", identity, 1, 1, slot, uid)


def load_tests(loader, tests, pattern):
    # The imported fixture owns setup only. Run this module's lifecycle case,
    # not its unrelated inherited tests a second time.
    return loader.loadTestsFromName(
        __name__
        + ".CompanionCombatLifecyclePostgresTests.test_companion_checkpoint_settlement_report_return_and_readmission"
    )
