import struct
import json
from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints


class CheckpointTests(PostgresCase):
    def test_cast_limits_preserved_in_durable_checkpoint(self):
        from wakfu_server.combat_spell_usage import validate_usage, consume_usage

        caster = self.fight.actors[self.character]
        for actor in self.fight.actors.values():
            actor.physical_radius = 0
        for _ in range(2):
            rule = validate_usage(self.fight, caster, 4776, 20, (1, 0, 0))
            consume_usage(
                self.fight, dict(actor_id=caster.id, spell_id=4776, native_usage=rule)
            )
        self.checkpoints.save(self.account, self.generation, self.fight)
        saved = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        usage = saved["native_spell_usage"][str(caster.id)]
        self.assertEqual(usage["casts"]["4776"], 2)
        self.assertEqual(usage["targets"]["4776"]["-200"], 2)
        self.assertEqual(saved["native_table_turn"], self.fight.native_table_turn)
        with self.assertRaisesRegex(ValueError, "per target"):
            validate_usage(self.fight, caster, 4776, 20, (1, 0, 0))

    def test_placement_orientation_survives_combat_start_and_checkpoint_roundtrip(self):
        from wakfu_server.combat_orientation import apply
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        runtime = RuntimeMessages(self.fight)
        self.fight.phase = "placement"
        self.fight.ready_owners.clear()
        actor = self.fight.actors[self.character]
        apply(runtime, self.account, struct.pack(">qB", self.character, 7))
        self.assertEqual(actor.direction, 7)

        self.fight.ready(self.account)
        self.assertEqual(self.fight.phase, "active")
        self.assertEqual(actor.direction, 7)
        payloads = {identity: (b"", b"") for identity in self.fight.actors}
        runtime.combat_started(payloads)
        self.assertEqual(actor.direction, 7)

        self.checkpoints.save(
            self.account, self.generation, self.fight, runtime=runtime
        )
        snapshot = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        self.assertEqual(snapshot["actors"][str(self.character)]["direction"], 7)
        self.assertEqual(snapshot["runtime"]["action_id"], runtime.action_id)

    @classmethod
    def setUpClass(cls):
        # Catalogue I/O is unrelated to the session lease under test. Load it
        # before opening sessions so slow machines do not expire a fresh lease.
        from wakfu_server.spell_audit import states_catalog

        cls.state_catalog = states_catalog()

    def test_cost_modifier_snapshot_preserves_unknown_empty_and_live_values(self):
        actor = self.fight.actors[self.character]
        rev = self.checkpoints.save(self.account, self.generation, self.fight)
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertIsNone(snap["spell_ap_cost_modifiers"])
        actor.spell_ap_cost_modifiers = {}
        rev = self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=rev
        )
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(snap["spell_ap_cost_modifiers"], {})
        actor.spell_ap_cost_modifiers = {8: -1, 11: 2}
        self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=rev
        )
        snap = self.checkpoints.read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(snap["spell_ap_cost_modifiers"], {"8": -1, "11": 2})

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account = self.store.register("local", "testing-local")["id"]
        self.character = self.store.create_character(self.account, "Own Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'active')",
                (77,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (77, self.character, self.account),
            )
        self.checkpoints = Checkpoints(self.store)
        pc = Actor(self.character, 0, (0, 0, 0), 60, 6, 3, 10, 1, self.account, True)
        npc = Actor(-200, 1, (1, 0, 0), 12, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(self.account)

    def test_native_hud_breed_and_resource_survive_checkpoint_read(self):
        actor = self.fight.actors[self.character]
        actor.native_hud_breed = 11
        actor.effect_stats = {50: 35}
        self.checkpoints.save(self.account, self.generation, self.fight)
        saved = Checkpoints(self.store).read(self.account, 77)["snapshot"]["actors"][
            str(self.character)
        ]
        self.assertEqual(saved["native_hud_breed"], 11)
        self.assertEqual(saved["effect_stats"]["50"], 35)

    def test_owned_hp_resources_states_and_events_survive_reopen(self):
        self.fight.apply_state(
            self.character,
            -200,
            3442,
            20,
            catalog=self.state_catalog,
            uid=901,
        )
        from wakfu_server.combat_state_ledger import StateTimeline

        self.fight.apply_state(
            self.character,
            -200,
            8913,
            30,
            catalog=self.state_catalog,
            uid=902,
            timeline=StateTimeline(1, self.character, 0, 0, "active"),
        )
        self.fight.actors[-200].combat_states = {
            8913: dict(level=30, expires_at_caster_start=2)
        }
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        self.fight.apply_damage(self.character, -200, 5)
        revision = self.checkpoints.save(
            self.account, self.generation, self.fight, expected_revision=revision
        )
        row = Checkpoints(self.store).read(self.account, 77)
        npc = row["snapshot"]["actors"]["-200"]
        self.assertEqual((npc["hp"], npc["max_hp"], npc["max_mp"]), (7, 12, 3))
        self.assertEqual(npc["combat_states"]["8913"]["level"], 30)
        running = npc["state_ledger"]["entries"][0]
        self.assertEqual(
            (
                running["uid"],
                running["reference"],
                running["level"],
                running["caster_id"],
                running["target_id"],
            ),
            (901, 3442, 20, self.character, -200),
        )
        timer = npc["state_ledger"]["entries"][1]["timer"]
        self.assertEqual(
            timer, dict(actor_id=self.character, expiration_round=2, phase="start")
        )
        self.assertEqual(row["snapshot"]["events"][-1]["kind"], "damage")
        json.dumps(row, default=lambda value: value.isoformat())
        self.assertEqual(
            self.checkpoints.end(
                self.account, self.generation, 77, expected_revision=revision
            ),
            3,
        )

    def test_owned_effect_uid_sequence_and_payloads_are_checkpointed(self):
        self.fight.native_effect_uid_next = 903
        self.fight.native_start_event_delivered = True
        self.fight.native_class_initializations = {self.character: {"breed": 11}}
        self.fight.state_wire_payloads[901] = "0102"
        self.fight.owned_stat_effects[902] = dict(
            uid=902,
            state_uid=901,
            target_id=self.character,
            actual=1,
            stat_id=2,
            payload="0304",
        )
        self.checkpoints.save(self.account, self.generation, self.fight)
        state = Checkpoints(self.store).read(self.account, 77)["snapshot"]
        self.assertEqual(state["native_effect_uid_next"], 903)
        self.assertTrue(state["native_start_event_delivered"])
        self.assertEqual(
            state["native_class_initializations"][str(self.character)], {"breed": 11}
        )
        self.assertEqual(state["state_wire_payloads"]["901"], "0102")
        self.assertEqual(state["owned_stat_effects"]["902"]["state_uid"], 901)

    def test_cas_foreign_account_and_replaced_generation_rejected(self):
        revision = self.checkpoints.save(self.account, self.generation, self.fight)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, self.generation, self.fight, expected_revision=0
            )
        with self.assertRaises(ValueError):
            self.checkpoints.read(self.account + 1, 77)
        new = self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, self.generation, self.fight, expected_revision=revision
            )
        self.store.select_character(self.account, new, self.character)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.account, new, self.fight, expected_revision=revision
            )

    def test_recovery_preserves_hp_and_does_not_resume_fight(self):
        self.fight.apply_damage(self.character, -200, 5)
        self.checkpoints.save(self.account, self.generation, self.fight)
        self.assertEqual(self.checkpoints.recover_interrupted(), 1)
        self.assertEqual(self.checkpoints.recover_interrupted(), 0)
        row = self.checkpoints.read(self.account, 77)
        self.assertEqual(row["status"], "aborted")
        self.assertEqual(row["snapshot"]["actors"]["-200"]["hp"], 7)
