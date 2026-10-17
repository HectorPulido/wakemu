"""Persisted null carriers: native Ready, owned turns, recovery and inverse."""
from random import Random
import struct

from postgres_case import PostgresCase
from wakfu_server import health_store, wire
from wakfu_server.progression import level_xp
from wakfu_server.equipment_stats import combat_resources
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.monsters import owned_instance
from wakfu_server.spells import encode_deck

# unittest discovery adds server/tests but does not add server/tools. Resolve
# this existing API driver explicitly and restore the process import path.
from pathlib import Path
import sys

_tools = next(
    parent / "server" / "tools"
    for parent in Path(__file__).resolve().parents
    if (parent / "server" / "tools" / "combat_audit_turns.py").is_file()
)
_saved_path = list(sys.path)
try:
    sys.path.insert(0, str(_tools))
    import combat_audit_turns as _turn_driver

    if (
        Path(_turn_driver.__file__).resolve()
        != (_tools / "combat_audit_turns.py").resolve()
    ):
        raise ImportError("Combat turn driver has a foreign source origin")
    advance_actual_turn = _turn_driver.advance_actual_turn
finally:
    sys.path[:] = _saved_path


from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_area_transaction import prepare_area_movement


class EquipmentNullCarrierPipelineTests(PostgresCase):
    def _fixture(
        self,
        reference=14191,
        sex=0,
        slot=23,
        social_setup=None,
        before_initialization=None,
    ):
        account = self.store.register(
            f"null-carrier-{reference}-{sex}", "local-test-password"
        )["id"]
        char = self.store.create_character(
            account,
            "Null "
            + {
                14191: "Stream",
                13716: "Dark",
                10424: "Plain",
                17713: "Survivor",
                9727: "Nation",
                13408: "Guild",
            }[reference]
            + (" Male" if sex == 0 else " Female"),
            breed=1,
            sex=sex,
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        if social_setup is not None:
            social_setup(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200,map_id=1134,instance_id=0,x=-8,y=-7,z=-1 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(200), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
        base_maximum = char["max_hp"]
        gear_uid = 100000 + char["id"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    gear_uid,
                    char["id"],
                    reference,
                    1,
                    char["inventory_containers"][0]["uid"],
                    0,
                ),
            )
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"NullCarrier"), (24, (1 << 64) - 1), (56, 0))
        )
        deck = encode_deck([6972])
        char = self.store.save_build(
            account,
            generation,
            char["id"],
            0,
            dict(
                sheet=sheet,
                equipment=wire.proto_field(
                    10, wire.proto_field(8, gear_uid) + wire.proto_field(16, slot)
                ),
                deck=deck,
                aptitudes=b"",
            ),
        )
        char = self.store.character(account, char["id"])
        resources = combat_resources(char)
        from wakfu_server.combat_terrain import local_arena

        initial = (-5, -7, -1)
        terrain = local_arena(
            1134, 1, (-8, -7, -1), initial, relocate_monsters=False, compact=True
        )
        monster = owned_instance(
            4168, 190, -200, map_id=1134, x=initial[0], y=initial[1], z=initial[2]
        )
        fight, _ = create_placement(
            char,
            monster,
            terrain,
            fight_id=7,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=46,
            terrain_instance_id=9001,
        )
        actor_id = char["id"]
        initialize_fight_snapshots(
            fight,
            characters={actor_id: char},
            monsters={-200: monster},
            wp_resources={
                actor_id: (resources["wp"], resources["wp"]),
                -200: (monster["wp"], monster["wp"]),
            },
            running_effects={actor_id: (), -200: ()},
            initial_effect_uid=1,
        )
        for actor in fight.actors.values():
            actor.direction = 0 if actor.controlled else 3
        rng = Random(7)

        def initialize(preview, action_id):
            if before_initialization is not None:
                before_initialization(preview, action_id, char, monster, deck, rng)
            return prepare_server_initialization(
                char,
                {-200: monster},
                preview,
                account,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def stats(actor):
            if actor.controlled:
                return actual_actor_stats(
                    char,
                    actor,
                    7,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["wp"],
                )
            return actual_monster_actor_stats(
                monster, actor, 7, wp_current=monster["wp"], wp_maximum=monster["wp"]
            )

        before = snapshot(fight)
        started, runtime, packets = prepare_ready(
            fight,
            account,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                char, {-200: monster}, p, deck, rng=rng, **b
            ),
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                char, {-200: monster}, p, deck, rng=rng, area_callbacks=True, **b
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
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(packets)
        for _ in range(len(started.actors)):
            if runtime.fight.current.id == actor_id:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, actor_id)
        self.assertEqual(char["max_hp"], base_maximum)
        runtime.null_test_ready_packets = tuple(packets)
        runtime.null_test_arena = terrain
        return char, monster, deck, rng, runtime, stats

    @staticmethod
    def _nulls(fight, owner, definitions):
        from wakfu_server.combat_protocol_reconstruction import _effect

        return {
            uid: (row, _effect(bytes.fromhex(row["payload"]), 400))
            for uid, row in fight.owned_stat_effects.items()
            if row["effect_class"] == 400
            and row["target_id"] == owner
            and _effect(bytes.fromhex(row["payload"]), 400)["definition"] in definitions
        }

    def _assert_carrier(self, values, state_reference, selected, rejected=()):
        char, monster, deck, rng, runtime, stats = values
        owner, fight = char["id"], runtime.fight
        state = next(
            entry
            for entry in fight.actors[owner].state_ledger.entries
            if entry.reference == state_reference
        )
        self.assertEqual(
            (state.level, state.duration, state.realtime_duration), (1, -1, -1000)
        )
        rows = self._nulls(fight, owner, (selected, *rejected))
        self.assertEqual(len(rows), 1)
        uid, (row, decoded) = next(iter(rows.items()))
        self.assertEqual(
            (row["stat_id"], row["actual"], row["state_uid"]), (None, 0, state.uid)
        )
        self.assertEqual(
            (
                decoded["uid"],
                decoded["definition"],
                decoded["caster"],
                decoded["target"],
            ),
            (uid, selected, owner, owner),
        )
        self.assertEqual(
            (decoded["container_type"], decoded["container_id"]),
            (1, (state_reference << 16) | 1),
        )
        self.assertIn(uid, fight.native_retained_order)
        self.assertIn(state.uid, fight.native_retained_order)
        self.assertNotEqual(uid, state.uid)
        self.assertEqual(fight.native_retained_records[uid]["manager_id"], owner)
        from wakfu_server.combat_protocol_reconstruction import decode_packet

        packets = [
            decode_packet(op, body)
            for op, body in runtime.null_test_ready_packets
            if op == 12613
        ]
        received = [
            p
            for p in packets
            if p["effect"]["family"] == 400
            and p["effect"]["definition"] in (selected, *rejected)
        ]
        self.assertEqual(len(received), 1)
        self.assertIs(received[0]["immediate"], False)
        self.assertEqual(received[0]["effect"]["uid"], uid)
        self.assertEqual(received[0]["effect"]["definition"], selected)
        return state, uid

    def test_persisted_male_female_and_unconditional_native_null_carriers_ready(self):
        # IDs are source-bound test oracles, never runtime qualification allowlists.
        for reference, sex, slot, state_reference, selected, rejected in (
            (14191, 0, 23, 5384, 254678, (254679,)),
            (14191, 1, 23, 5384, 254679, (254678,)),
            (13716, 1, 23, 1317, 108933, (108932,)),
            (10424, 0, 17, 955, 44086, ()),
            (17713, 1, 23, 2261, 102943, (102942,)),
        ):
            with self.subTest(reference=reference, sex=sex):
                values = self._fixture(reference, sex, slot)
                char = values[0]
                self.assertEqual(int(char["sex"]), sex)
                self._assert_carrier(values, state_reference, selected, rejected)
                # Retain the original actual HMI route; a zero stat delta does
                # not substitute for a documented native appearance action.
                from wakfu_server.combat_server_spell import compiled_runtime_catalog

                actions = compiled_runtime_catalog().effects[str(selected)][
                    "native_hmi_actions"
                ]
                self.assertTrue(actions["rze"])
                self.assertIn("COSTUME", {a["type"] for a in actions["rze"]})
                self.assertTrue(
                    {a["type"] for a in actions["rze"]}
                    <= {"COSTUME", "SKIN_PART_VISIBILITY"}
                )

    def test_real_turns_typed_recovery_owned_bootstrap_and_exact_removal(self):
        from copy import deepcopy
        from types import SimpleNamespace
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.combat_reproduction_actions import (
            bind_runtime,
            AUTHORITY_RECIPE,
        )
        from wakfu_server.combat_shared import Session
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_protocol_reconstruction import decode_packet

        values = self._fixture()
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        state, uid = self._assert_carrier(values, 5384, 254678, (254679,))
        original_payload = runtime.fight.owned_stat_effects[uid]["payload"]
        for _ in range(2 * len(runtime.fight.actors)):
            advance_actual_turn(runtime)
        self.assertEqual(
            runtime.fight.owned_stat_effects[uid]["payload"], original_payload
        )
        self.assertEqual(
            next(
                s.uid
                for s in runtime.fight.actors[owner].state_ledger.entries
                if s.reference == 5384
            ),
            state.uid,
        )
        before = snapshot(runtime.fight)
        recovered = decode_state(encode_state(runtime.fight))
        self.assertIsNot(recovered, runtime.fight)
        self.assertEqual(snapshot(recovered), before)
        runtime.fight = recovered
        inputs = dict(
            authority_recipe=AUTHORITY_RECIPE,
            character=char,
            monsters={-200: monster},
            deck_blob=deck,
            player_characters={owner: char},
            deck_blobs={owner: deck},
            map_id=1134,
            native_events=True,
            area_callbacks=True,
        )
        bind_runtime(runtime, inputs, rng, runtime.clock)
        shared = SimpleNamespace(
            runtime=runtime,
            map_id=1134,
            instance_id=0,
            join_context=dict(
                arena=runtime.null_test_arena,
                terrain_effect_id=46,
                terrain_instance_id=9001,
                leaders={0: owner, 1: -200},
            ),
        )
        session = Session(char["account_id"], owner, "null-carrier-recovery", 1134, 0)

        def actor_payload(fight, actor, recipient):
            if actor.controlled:
                payload = actual_actor_stats(
                    char,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )
            else:
                payload = actual_monster_actor_stats(
                    monster,
                    actor,
                    fight.id,
                    wp_current=monster["wp"],
                    wp_maximum=monster["wp"],
                )
            return payload, actor_effects()

        stable = snapshot(recovered)
        stream = owned_snapshot(recovered, shared, session, actor_payload=actor_payload)
        self.assertEqual(snapshot(recovered), stable)
        packet_rows = [decode_packet(op, body) for op, body in stream if op == 12613]
        null_rows = [p for p in packet_rows if p["effect"]["uid"] == uid]
        self.assertEqual(len(null_rows), 1)
        self.assertEqual(null_rows[0]["effect"]["definition"], 254678)
        self.assertIs(null_rows[0]["immediate"], False)
        self.assertFalse(any(p["effect"]["definition"] == 254679 for p in packet_rows))
        self.assertEqual(recovered.owned_stat_effects[uid]["payload"], original_payload)
        # Use the production retained-removal registry on a detached transaction
        # preview. This is an owned inverse witness, not a fabricated cast.
        preview = deepcopy(recovered)
        factory, _ = server_runtime(
            char, {-200: monster}, deck, action_id=99, critical=False, rng=rng
        )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        other_uids = set(preview.native_retained_order) - {uid, state.uid}
        before_stats = dict(preview.actors[owner].effect_stats)
        retention = dispatcher.native_retention
        retention.removal(retention.view()).remove((state.uid,))
        retention.synchronize()
        self.assertEqual(set(preview.native_retained_order), other_uids)
        self.assertNotIn(uid, preview.owned_stat_effects)
        self.assertNotIn(state.uid, preview.state_wire_payloads)
        self.assertEqual(dict(preview.actors[owner].effect_stats), before_stats)
        removals = [decode_packet(op, body) for op, body in outbox if op == 13560]
        selected = [p for p in removals if p["effect"]["uid"] in (uid, state.uid)]
        self.assertEqual([p["effect"]["family"] for p in selected], [400, 310])
        self.assertTrue(all(p["removal_target"] == owner for p in selected))
        self.assertEqual(snapshot(recovered), stable)

    def test_missing_native_sex_rejects_without_selecting_a_default_or_mutating_source(
        self,
    ):
        from copy import deepcopy
        from wakfu_server.combat_conditions import UnknownCondition

        values = self._fixture()
        char, monster, deck, rng, runtime, stats = values
        missing = deepcopy(char)
        missing.pop("sex")
        preview = deepcopy(runtime.fight)
        # Re-evaluate the original selected conditional against the ordinary
        # runtime's actual authority producer, never a replacement predicate.
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        before, random_before = snapshot(preview), rng.getstate()
        factory, _ = server_runtime(
            missing, {-200: monster}, deck, action_id=101, critical=False, rng=rng
        )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        with self.assertRaises(UnknownCondition):
            dispatcher.execute(
                EffectInvocation(
                    254678,
                    1,
                    char["id"],
                    char["id"],
                    preview.actors[char["id"]].position,
                    native_explicit_target=True,
                )
            )
        self.assertEqual(snapshot(preview), before)
        self.assertEqual(rng.getstate(), random_before)
        self.assertEqual(outbox, [])
