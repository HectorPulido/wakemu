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
        level=200,
        breed=1,
        active_spells=None,
        select_elements=False,
        social_setup=None,
        before_initialization=None,
        administrator=False,
        monster_reference=4168,
        monster_level=190,
        monster_position=(-5, -7, -1),
    ):
        # Several actual-source cases share one isolated-schema test. Both
        # account names and character names are unique within that schema.
        fixture_index = getattr(self, "_null_fixture_index", 0) + 1
        self._null_fixture_index = fixture_index
        identity = f"{reference}-{sex}-{fixture_index}"
        account = self.store.register(
            f"null-carrier-{identity}", "local-test-password"
        )["id"]
        if administrator:
            # Native IsAdmin equipment requires actual persisted authority.
            with self.store.connection() as db:
                db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account,))
        char = self.store.create_character(
            account,
            "Null " + identity.translate(str.maketrans("0123456789", "abcdefghij")),
            breed=breed,
            sex=sex,
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, char["id"])
        if social_setup is not None:
            social_setup(account, generation, char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s,map_id=1134,instance_id=0,x=-8,y=-7,z=-1 WHERE id=%s",
                (level, char["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(level), char["id"]),
            )
        char = health_store.initialize(self.store, account, generation, char["id"])
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
        if select_elements:
            from wakfu_server.items.element_selection import select

            if select_elements is True:
                damage_mask, resistance_mask = (14, 0)
            elif (
                isinstance(select_elements, tuple)
                and len(select_elements) == 2
                and all(
                    type(value) is int and 0 <= value <= 255
                    for value in select_elements
                )
            ):
                damage_mask, resistance_mask = select_elements
            else:
                raise ValueError(
                    "select_elements must be True or a native byte-mask pair"
                )
            select(
                self.store,
                account,
                generation,
                char["id"],
                struct.pack(">qBB", gear_uid, damage_mask, resistance_mask),
            )
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in ((8, 0), (18, b"NullCarrier"), (24, level), (56, 0))
        )
        deck = encode_deck([6972] if active_spells is None else active_spells)
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
        # Use the actual equipped sheet as the combat baseline. New native
        # end-resource cases can have legitimate max-HP gear effects.
        base_maximum = char["max_hp"]
        resources = combat_resources(char)
        from wakfu_server.combat_terrain import local_arena

        initial = monster_position
        terrain = local_arena(
            1134, 1, (-8, -7, -1), initial, relocate_monsters=False, compact=True
        )
        monster = owned_instance(
            monster_reference,
            monster_level,
            -200,
            map_id=1134,
            x=initial[0],
            y=initial[1],
            z=initial[2],
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

        def stats(actor, state=None):
            current = fight if state is None else state
            if actor.id in getattr(current, "native_summon_registrations", {}):
                from wakfu_server.combat_summon_stats import registered_summon_stats

                return registered_summon_stats(actor, current, char["map_id"])
            if actor.controlled:
                return actual_actor_stats(
                    char,
                    actor,
                    7,
                    fight=current,
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
            runtime_stats_serializer=stats,
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
        self._exercise_recovery_and_removal()

    def test_generic_operation_source_13574_ready_turn_checkpoint_and_removal(self):
        """Exercise the generic operation route with one complete native source."""
        from copy import deepcopy
        from unittest.mock import patch

        from wakfu_server.combat_protocol_reconstruction import decode_packet
        from wakfu_server.combat_reproduction_state import decode_state, encode_state
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        import wakfu_server.combat_owned_equipment_pin as equipment_pin

        admitted = []
        context = {}
        original_prepare = equipment_pin.prepare

        def observe_prepare(*args, **kwargs):
            context.update(
                character=args[0],
                compiled=args[2],
                registry=args[3],
                runtime_capability=kwargs.get("runtime_capability"),
            )
            result = original_prepare(*args, **kwargs)
            admitted.extend(
                source
                for source in result["sources"]
                if source.get("_generic_operation_admission") is True
            )
            return result

        with patch.object(equipment_pin, "prepare", side_effect=observe_prepare):
            values = self._fixture(reference=13574, slot=7, level=200)

        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        fight = runtime.fight
        self.assertEqual(
            len(admitted), 1, "13574 must use the generic capability route"
        )
        source = admitted[0]
        self.assertEqual(source["source_reference"], 13574)
        self.assertEqual(source["roots"], (67259,))
        self.assertEqual(source["_generic_operation_admission"], True)
        pin = fight.native_owned_equipment_sources[str(owner)]
        self.assertEqual(pin["sources"][0]["source_reference"], 13574)
        actor = fight.actors[owner]
        state_rows = [
            row for row in actor.state_ledger.entries if row.reference == 1348
        ]
        self.assertEqual(len(state_rows), 1)
        state_uid = state_rows[0].uid

        # Ready applies the permanent 304 root only. Its 330/group listener is
        # driven by the real owner-turn 1001 producer below.
        # _fixture may advance through an initial turn-start before returning;
        # capture the committed live actor, never its pre-Ready placement copy.
        initial_ap_max = runtime.fight.actors[owner].effect_maxima[2]
        self.assertEqual(runtime.fight.actors[owner].max_ap, initial_ap_max)
        from wakfu_server.combat_protocol_reconstruction import _effect

        def active_ap_rows(candidate):
            rows = []
            for uid, row in candidate.owned_stat_effects.items():
                if (
                    row.get("state_uid") != state_uid
                    or row.get("target_id") != owner
                    or row.get("family") != "eWN"
                    or row.get("stat_id") != 2
                ):
                    continue
                effect = _effect(bytes.fromhex(row["payload"]), row["effect_class"])
                rows.append((uid, row, effect["definition"]))
            return rows

        initial_rows = active_ap_rows(runtime.fight)
        initial_row_total = sum(
            row["effective_delta"] for _uid, row, _ref in initial_rows
        )
        base_max_ap = initial_ap_max - initial_row_total
        self.assertEqual(
            len([row for row in actor.state_ledger.entries if row.reference == 1348]), 1
        )
        events = []
        with combat_diagnostic_scope(lambda **row: events.append(row), limit=4096):
            for _ in range(2):
                advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, owner)
        fired = [
            row
            for row in events
            if row.get("effect_reference") in (67472, 67470)
            and row.get("status") == "completed"
            and row.get("caster_id") == owner
            and row.get("target_id") == owner
        ]
        self.assertEqual(len(fired), 1, events)
        self.assertIn(fired[0]["effect_reference"], (67472, 67470))
        proc_rows = active_ap_rows(runtime.fight)
        self.assertEqual(len(proc_rows), 1, proc_rows)
        proc_uid, proc_row, proc_reference = proc_rows[0]
        self.assertEqual(proc_reference, fired[0]["effect_reference"])
        expected_net = (
            sum(row["effective_delta"] for _uid, row, _ref in proc_rows)
            - initial_row_total
        )
        self.assertEqual(
            runtime.fight.actors[owner].max_ap - initial_ap_max, expected_net
        )
        self.assertEqual(
            runtime.fight.actors[owner].max_ap,
            base_max_ap + sum(row["effective_delta"] for _uid, row, _ref in proc_rows),
        )
        timer = proc_row["timer"]
        self.assertIsInstance(timer, dict)
        self.assertEqual(timer.get("actor_id"), owner)
        self.assertIn(timer.get("phase"), ("start", "end"))
        self.assertGreaterEqual(
            timer.get("expiration_round"), runtime.fight.native_table_turn
        )
        self.assertEqual(
            len(
                [
                    row
                    for row in runtime.fight.actors[owner].state_ledger.entries
                    if row.reference == 1348
                ]
            ),
            1,
        )
        ready_snapshot = snapshot(runtime.fight)
        recovered = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(recovered), ready_snapshot)
        self.assertEqual(
            len(
                [
                    row
                    for row in recovered.actors[owner].state_ledger.entries
                    if row.reference == 1348
                ]
            ),
            1,
        )
        self.assertIn(proc_uid, recovered.owned_stat_effects)
        self.assertEqual(recovered.owned_stat_effects[proc_uid]["timer"], timer)
        runtime.fight = recovered

        # Expire that exact target-clock resource at its real fight boundary.
        # The permanent state/listener remains until the explicit removal below.
        for _ in range(2 * len(runtime.fight.actors)):
            previous_actor = runtime.fight.current.id
            previous_round = runtime.fight.native_table_turn
            advance_actual_turn(runtime)
            if proc_uid not in runtime.fight.owned_stat_effects:
                self.assertEqual(previous_round, timer["expiration_round"])
                if timer["phase"] == "end":
                    self.assertEqual(previous_actor, timer["actor_id"])
                else:
                    self.assertEqual(runtime.fight.current.id, timer["actor_id"])
                break
        else:
            self.fail("Native 13574 AP branch did not expire at its owned timer bucket")
        self.assertTrue(
            any(
                row.reference == 1348
                for row in runtime.fight.actors[owner].state_ledger.entries
            )
        )
        remaining_rows = active_ap_rows(runtime.fight)
        self.assertEqual(
            runtime.fight.actors[owner].max_ap,
            base_max_ap
            + sum(row["effective_delta"] for _uid, row, _ref in remaining_rows),
        )

        # Remove the owned state through the real retained-removal registry on
        # a detached transaction. This also checks that checkpointing did not
        # duplicate the source or its listener.
        preview = deepcopy(recovered)
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        before_maxima = dict(preview.actors[owner].effect_maxima)
        dispatcher.native_retention.removal(dispatcher.native_retention.view()).remove(
            (state_uid,)
        )
        dispatcher.native_retention.synchronize()
        self.assertFalse(
            any(
                row.reference == 1348
                for row in preview.actors[owner].state_ledger.entries
            )
        )
        self.assertNotIn(state_uid, preview.state_wire_payloads)
        self.assertEqual(dict(preview.actors[owner].effect_maxima), before_maxima)
        self.assertEqual(preview.actors[owner].max_ap, base_max_ap)
        removal_packets = [
            decode_packet(op, body) for op, body in outbox if op == 13560
        ]
        self.assertTrue(
            any(row["effect"]["uid"] == state_uid for row in removal_packets)
        )

    def test_live_factory_capability_census_for_17_native_sources(self):
        """Measure known source graphs with the real Ready factory routes."""
        import json
        from pathlib import Path
        from unittest.mock import patch

        import wakfu_server.combat_owned_equipment_pin as equipment_pin
        from wakfu_server.combat_equipment_operation_capability import validate_graph
        from wakfu_server.combat_equipment_initialization import plan as equipment_plan
        from wakfu_server.combat_owned_equipment_pin import compiled_with_sources

        context = {}
        original_prepare = equipment_pin.prepare

        def observe_prepare(*args, **kwargs):
            context.update(
                character=args[0],
                compiled=args[2],
                registry=args[3],
                runtime_capability=kwargs.get("runtime_capability"),
            )
            return original_prepare(*args, **kwargs)

        with patch.object(equipment_pin, "prepare", side_effect=observe_prepare):
            char, _monster, _deck, _rng, runtime, _stats = self._fixture(
                reference=13574, slot=7, level=200
            )
        self.assertEqual(runtime.fight.phase, "active")
        routes, provider = context["runtime_capability"]
        references = (
            9728,
            10632,
            12197,
            13574,
            13946,
            14057,
            14083,
            17802,
            18097,
            18604,
            19093,
            19094,
            28417,
            29456,
            29878,
            30530,
            31361,
        )
        results = []
        for index, reference in enumerate(references):
            uid = 910000000 + index
            candidate = dict(
                char,
                inventory_items=[dict(uid=uid, reference=reference, quantity=1)],
            )
            sources = equipment_plan(
                candidate,
                ordinary_only=True,
                _selected_entries=[dict(uid=uid, slot=0)],
            )
            if len(sources) != 1:
                results.append(
                    dict(
                        reference=reference,
                        status="unknown",
                        reasons=["planner did not produce one complete source"],
                    )
                )
                continue
            compiled = compiled_with_sources(context["compiled"], sources)
            outcome = validate_graph(
                sources[0],
                compiled,
                context["registry"],
                runtime_bindings=routes,
                criteria_capability=provider,
            )
            results.append(
                dict(
                    reference=reference,
                    status=outcome.status,
                    reasons=list(outcome.reasons),
                    operation_id=getattr(outcome, "operation_id", None),
                )
            )
        self.assertEqual([row["reference"] for row in results], list(references))
        path = Path(
            ".runtime/equipment-capability-census-20261021/current-live-factory-17.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")

    def test_current_registry_direct_resource_roots_18604_real_save_and_ready(self):
        """Confirm eWQ/eWR roots use the current persisted registry at Ready."""
        import json
        from pathlib import Path
        from unittest.mock import patch

        import wakfu_server.combat_owned_equipment_pin as equipment_pin
        import wakfu_server.combat_equipment_operation_capability as capability

        preparations = []
        validations = []
        node_validations = []
        context = {}
        original_prepare = equipment_pin.prepare
        original_validate = capability.validate_graph
        original_validate_effect = capability.validate_effect

        def registry_summary(registry):
            import hashlib
            import json

            def plain(value):
                if hasattr(value, "items"):
                    return {str(key): plain(child) for key, child in value.items()}
                if isinstance(value, (tuple, list)):
                    return [plain(child) for child in value]
                return value

            normalized = plain(registry)
            encoded = json.dumps(
                normalized, sort_keys=True, separators=(",", ":"), default=str
            )
            effects = (
                registry.get("effects", registry)
                if hasattr(registry, "get")
                else registry
            )
            keys = list(registry.keys()) if hasattr(registry, "keys") else []
            rows = {}
            for family in (83, 84, 85):
                value = (
                    effects.get(str(family), effects.get(family))
                    if hasattr(effects, "get")
                    else None
                )
                rows[str(family)] = value
            return {
                "length": len(registry) if hasattr(registry, "__len__") else None,
                "sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                "keys_sample": [str(key) for key in keys[:40]],
                "families_83_84_85": rows,
            }

        def observe_prepare(*args, **kwargs):
            result = original_prepare(*args, **kwargs)
            context.update(
                character=args[0],
                compiled=args[2],
                registry=args[3],
                runtime_capability=kwargs.get("runtime_capability"),
            )
            context["prepare_registry_summary"] = registry_summary(args[3])
            routes = kwargs.get("runtime_capability", (None,))[0]
            context["runtime_route_keys"] = [
                str(key) for key in getattr(routes, "routes", {}).keys()
            ]
            factory = getattr(routes, "factory", None)
            if factory is not None:
                context["factory_registry_summary"] = registry_summary(
                    factory.characteristic_registry
                )
                context["factory_route_handlers"] = {
                    str(family): getattr(
                        route.handler_type, "__name__", repr(route.handler_type)
                    )
                    for family, route in getattr(routes, "routes", {}).items()
                    if family in (83, 84, 85)
                }
            preparations.append(
                {
                    "sources": tuple(result["sources"]),
                    "deferred": tuple(result["deferred"]),
                }
            )
            return result

        def observe_validate(*args, **kwargs):
            result = original_validate(*args, **kwargs)
            registry = args[2]
            routes = kwargs.get("runtime_bindings")
            route_map = getattr(routes, "routes", routes)
            validations.append(
                {
                    "status": result.status,
                    "reasons": list(result.reasons),
                    "operation_id": getattr(result, "operation_id", None),
                    "required_context": list(getattr(result, "requires_context", ())),
                    "registry": registry_summary(registry),
                    "same_factory_registry_object": (
                        registry
                        is getattr(
                            getattr(routes, "factory", None),
                            "characteristic_registry",
                            None,
                        )
                    ),
                    "same_factory_registry_value": (
                        registry_summary(registry).get("sha256")
                        == context.get("factory_registry_summary", {}).get("sha256")
                    ),
                    "route_bound": {
                        str(family): bool(
                            route_map
                            and any(str(key) == str(family) for key in route_map)
                        )
                        for family in (83, 84, 85)
                    },
                }
            )
            return result

        def observe_validate_effect(effect, level, registry, **kwargs):
            result = original_validate_effect(effect, level, registry, **kwargs)
            node_validations.append(
                {
                    "reference": effect.get("effect_id", effect.get("reference")),
                    "family": effect.get("effect_class"),
                    "level": level,
                    "status": result.status,
                    "operation_id": getattr(result, "operation_id", None),
                    "required_context": list(getattr(result, "requires_context", ())),
                    "reasons": list(result.reasons),
                }
            )
            return result

        with patch.object(
            equipment_pin, "prepare", side_effect=observe_prepare
        ), patch.object(
            capability, "validate_graph", side_effect=observe_validate
        ), patch.object(
            capability, "validate_effect", side_effect=observe_validate_effect
        ):
            char, _monster, _deck, _rng, runtime, _stats = self._fixture(
                reference=18604, slot=23, level=200
            )

        owner = char["id"]
        self.assertEqual(runtime.fight.phase, "active")
        self.assertEqual(len(preparations), 1)
        pin = getattr(runtime.fight, "native_owned_equipment_sources", {}).get(
            str(owner), {}
        )
        evidence = {
            "reference": 18604,
            "saved_build": char.get("sheet"),
            "prepared_sources": [
                {
                    "reference": row.get("source_reference"),
                    "generic": row.get("_generic_operation_admission"),
                }
                for row in preparations[0]["sources"]
            ],
            "deferred": list(preparations[0]["deferred"]),
            "validator_calls": validations,
            "node_validations": node_validations,
            "prepare_registry": context.get("prepare_registry_summary"),
            "factory_registry": context.get("factory_registry_summary"),
            "factory_route_handlers": context.get("factory_route_handlers"),
            "runtime_route_keys": context.get("runtime_route_keys"),
            "pinned": pin,
        }
        evidence_path = Path(
            ".runtime/equipment-capability-census-20261021/18604-live-ready-diagnostic.json"
        )
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n"
        )
        self.assertEqual(
            len(preparations[0]["sources"]),
            1,
            f"18604 did not reach generic Ready admission; see {evidence_path}",
        )
        source = preparations[0]["sources"][0]
        self.assertEqual(source["source_reference"], 18604)
        self.assertIs(source.get("_generic_operation_admission"), True)
        self.assertTrue(validations)
        self.assertTrue(all(row["status"] == "supported" for row in validations))
        self.assertEqual(len(pin.get("sources", [])), 1)
        self.assertEqual(pin["sources"][0]["source_reference"], 18604)

    def test_generic_null400_source_18604_checkpoint_and_exact_state_removal(self):
        """Check the real eXE carrier and stat inverse across checkpoint restore."""
        from copy import deepcopy
        from unittest.mock import patch

        from wakfu_server.combat_reproduction_state import decode_state, encode_state
        from wakfu_server.combat_server_spell import server_runtime
        import wakfu_server.combat_owned_equipment_pin as equipment_pin

        admitted = []
        original_prepare = equipment_pin.prepare

        def observe_prepare(*args, **kwargs):
            result = original_prepare(*args, **kwargs)
            admitted.extend(
                source
                for source in result["sources"]
                if source.get("_generic_operation_admission") is True
            )
            return result

        with patch.object(equipment_pin, "prepare", side_effect=observe_prepare):
            char, monster, deck, rng, runtime, _stats = self._fixture(
                reference=18604, slot=23, level=200
            )

        owner = char["id"]
        fight = runtime.fight
        self.assertEqual(len(admitted), 1)
        source = admitted[0]
        self.assertEqual(source["source_reference"], 18604)
        self.assertIs(source.get("_generic_operation_admission"), True)

        # Resolve the actual state reference from the admitted native root,
        # then follow the executor-created state UID and child-owned effects.
        state_references = {
            int(effect["parameters"][0])
            for root in source["roots"]
            if (effect := source["effects"].get(str(root))) is not None
            and effect.get("effect_class") == 304
            and effect.get("parameters")
        }
        states = [
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.reference in state_references
        ]
        self.assertTrue(
            states, (state_references, fight.actors[owner].state_ledger.entries)
        )
        state_uids = tuple(sorted(row.uid for row in states))
        from wakfu_server.combat_static_catalogs import characteristic_registry

        registry_rows = characteristic_registry()
        registry_rows = registry_rows.get("effects", registry_rows)
        direct_stat_roots = {
            root
            for root in source["roots"]
            if registry_rows.get(
                str(source["effects"].get(str(root), {}).get("effect_class")), {}
            ).get("runner")
            in ("eWQ", "eWR")
        }
        from wakfu_server.combat_protocol_reconstruction import _effect

        owned = {}
        for uid, row in fight.owned_stat_effects.items():
            if row.get("state_uid") in state_uids:
                owned[uid] = row
                continue
            if row.get("family") not in ("eWQ", "eWR"):
                continue
            decoded = _effect(bytes.fromhex(row["payload"]), row["effect_class"])
            if decoded.get("definition") in direct_stat_roots:
                owned[uid] = row
        null_rows = {
            uid: row
            for uid, row in owned.items()
            if row.get("effect_class") == 400 and row.get("family") == "eXE"
        }
        stat_rows = {
            uid: row
            for uid, row in owned.items()
            if row.get("family") in ("eWQ", "eWR") and row.get("stat_id") is not None
        }
        self.assertTrue(null_rows, owned)
        self.assertTrue(stat_rows, owned)
        self.assertEqual(len(null_rows), len(set(null_rows)))
        self.assertEqual(len(stat_rows), len(set(stat_rows)))

        before_stats = dict(fight.actors[owner].effect_stats)
        before_null_uids = tuple(sorted(null_rows))
        before_stat_uids = tuple(sorted(stat_rows))
        expected_after_remove = dict(before_stats)
        for row in stat_rows.values():
            stat = row["stat_id"]
            direction = 1 if row["family"] == "eWQ" else -1
            expected_after_remove[stat] -= direction * row["actual"]

        checkpoint = snapshot(fight)
        recovered = decode_state(encode_state(fight))
        self.assertEqual(snapshot(recovered), checkpoint)
        recovered_owned = recovered.owned_stat_effects
        self.assertEqual(tuple(sorted(null_rows)), before_null_uids)
        self.assertEqual(tuple(sorted(stat_rows)), before_stat_uids)
        for uid, original_row in owned.items():
            self.assertIn(uid, recovered_owned)
            self.assertEqual(recovered_owned[uid], original_row)

        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _outbox = factory(
            recovered, {"native_retained_container": {"present": False}}
        )
        dispatcher.native_retention.removal(dispatcher.native_retention.view()).remove(
            state_uids
        )
        dispatcher.native_retention.synchronize()

        # Remove direct sibling operations that are not cascaded through the
        # 304 state, using the exact source-owned UIDs captured before restore.
        surviving_source_uids = tuple(
            sorted(uid for uid in owned if uid in recovered.owned_stat_effects)
        )
        if surviving_source_uids:
            dispatcher.native_retention.removal(
                dispatcher.native_retention.view()
            ).remove(surviving_source_uids)
            dispatcher.native_retention.synchronize()

        remaining = recovered.owned_stat_effects
        self.assertTrue(set(owned).isdisjoint(remaining))
        self.assertFalse(
            any(
                row.reference in state_references
                for row in recovered.actors[owner].state_ledger.entries
            )
        )
        after_stats = recovered.actors[owner].effect_stats
        self.assertEqual(after_stats, expected_after_remove)

    def test_admin_direct_root_29878_defers_without_complete_native_graph(self):
        """A partial native graph stays deferred through ordinary persisted Ready."""
        import json
        from pathlib import Path
        from unittest.mock import patch
        import wakfu_server.combat_owned_equipment_pin as equipment_pin
        import wakfu_server.combat_equipment_operation_capability as capability_module

        admitted = []
        preparations = []
        capability_observations = []
        context = {}
        original_prepare = equipment_pin.prepare
        original_validate = capability_module.validate_graph

        def observe_prepare(*args, **kwargs):
            context.update(
                character=args[0],
                compiled=args[2],
                registry=args[3],
                runtime_capability=kwargs.get("runtime_capability"),
            )
            result = original_prepare(*args, **kwargs)
            preparations.append(
                {
                    "sources": tuple(
                        (
                            source.get("source_reference"),
                            source.get("_generic_operation_admission"),
                        )
                        for source in result["sources"]
                    ),
                    "deferred": tuple(result["deferred"]),
                }
            )
            admitted.extend(
                source
                for source in result["sources"]
                if source.get("_generic_operation_admission") is True
            )
            return result

        def observe_validate(*args, **kwargs):
            result = original_validate(*args, **kwargs)
            capability_observations.append(result)
            return result

        # This native source is administrator-gated and occupies slot 7.  The
        # fixture persists real admin authority before save_build and follows
        # the ordinary Store/save/Ready pipeline; it does not inject a source.
        with patch.object(
            equipment_pin, "prepare", side_effect=observe_prepare
        ), patch.object(
            capability_module, "validate_graph", side_effect=observe_validate
        ):
            char, _monster, _deck, _rng, runtime, _stats = self._fixture(
                reference=29878, slot=7, level=200, administrator=True
            )

        owner = char["id"]
        self.assertEqual(admitted, [])
        self.assertEqual(len(preparations), 1)
        self.assertEqual(preparations[0]["sources"], ())
        self.assertEqual(len(preparations[0]["deferred"]), 1)
        deferred = preparations[0]["deferred"][0]
        self.assertEqual(
            (deferred["uid"], deferred["source_reference"]), (100000 + owner, 29878)
        )
        self.assertIn(
            "reactive_ordered_graph_incomplete_or_unknown", deferred["reason"]
        )
        self.assertEqual(runtime.fight.phase, "active")
        pinned = getattr(runtime.fight, "native_owned_equipment_sources", {})
        self.assertIn(str(owner), pinned)
        self.assertEqual(tuple(pinned[str(owner)]["sources"]), ())
        self.assertEqual(len(pinned[str(owner)]["deferred"]), 1)

        # Measure the same 17 native graphs through the current live factory
        # routes/provider captured during ordinary Ready. The temporary source
        # rows are parser inputs only; no source is installed or admitted here.
        routes, provider = context["runtime_capability"]
        from wakfu_server.combat_equipment_initialization import plan as equipment_plan
        from wakfu_server.combat_owned_equipment_pin import compiled_with_sources

        references = (
            9728,
            10632,
            12197,
            13574,
            13946,
            14057,
            14083,
            17802,
            18097,
            18604,
            19093,
            19094,
            28417,
            29456,
            29878,
            30530,
            31361,
        )
        results = []
        for index, reference in enumerate(references):
            uid = 900000000 + index
            candidate = dict(
                char,
                inventory_items=[dict(uid=uid, reference=reference, quantity=1)],
            )
            sources = equipment_plan(
                candidate,
                ordinary_only=True,
                _selected_entries=[dict(uid=uid, slot=0)],
            )
            if len(sources) != 1:
                results.append(
                    dict(
                        reference=reference,
                        status="unknown",
                        reasons=["planner did not produce one complete source"],
                    )
                )
                continue
            compiled_candidate = compiled_with_sources(context["compiled"], sources)
            outcome = original_validate(
                sources[0],
                compiled_candidate,
                context["registry"],
                runtime_bindings=routes,
                criteria_capability=provider,
            )
            results.append(
                dict(
                    reference=reference,
                    status=outcome.status,
                    reasons=list(outcome.reasons),
                    operation_id=getattr(outcome, "operation_id", None),
                )
            )
        self.assertEqual(len(results), len(references))
        census_path = Path(
            ".runtime/equipment-capability-census-20261021/current-live-factory-17.json"
        )
        measured_18604 = next(row for row in results if row["reference"] == 18604)
        self.assertIn(measured_18604["status"], ("supported", "unknown", "unsupported"))
        actual_capability = (
            dict(
                status=capability_observations[-1].status,
                reasons=list(capability_observations[-1].reasons),
            )
            if capability_observations
            else None
        )
        census_path.write_text(
            json.dumps(
                dict(actual_29878=actual_capability, graphs=results),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    def test_flag17_costume_ready_reconnect_and_exact_removal_preserve_native_hmi(self):
        self._exercise_recovery_and_removal(
            reference=12176, state_reference=1104, selected=56088, rejected=()
        )

    def test_remaining_native_cosmetic_forms_ready_preserve_sex_and_disabled_branches(
        self,
    ):
        for reference, state_reference, selected, rejected in (
            (12277, 1125, 57446, ()),
            (15057, 1582, 82539, ()),
            (15060, 1585, 82542, ()),
            (15061, 1586, 82540, ()),
            (15067, 1589, 80867, ()),
            (15105, 1594, 82541, ()),
            (15140, 2278, 103214, (103215,)),
            (17436, 2029, 97625, (97626,)),
            (17437, 2030, 97628, (97629,)),
            (17438, 2031, 97631, (97632,)),
            (18036, 2483, 108595, (108596,)),
            (18047, 2493, 108647, (108648,)),
            (20693, 4453, 184986, (184987,)),
            (22129, 4863, 199607, (199608,)),
            (17870, 2389, 107412, ()),
            (30485, 7519, 339644, (339645,)),
        ):
            with self.subTest(reference=reference):
                values = self._fixture(
                    reference=reference, administrator=reference == 20693
                )
                state, _ = self._assert_carrier(
                    values, state_reference, selected, rejected
                )
                self.assertEqual(state.level, 1)
        for reference, state_reference, selected, rejected in (
            (15140, 2278, 103215, (103214,)),
            (18047, 2493, 108648, (108647,)),
            (20693, 4453, 184987, (184986,)),
            (30485, 7519, 339645, (339644,)),
        ):
            with self.subTest(reference=reference, sex=1):
                self._assert_carrier(
                    self._fixture(
                        reference=reference, sex=1, administrator=reference == 20693
                    ),
                    state_reference,
                    selected,
                    rejected,
                )

    def test_permanent_clock_point_preapply_and_disabled_branch_recover_and_remove(
        self,
    ):
        # Each distinct newly admitted lifecycle shape uses the actual source,
        # Ready, turns, typed restore, owned bootstrap and inverse packets.
        for reference, state_reference, selected, rejected in (
            (15057, 1582, 82539, ()),
            (15140, 2278, 103214, (103215,)),
            (18047, 2493, 108647, (108648,)),
            (15067, 1589, 80867, ()),
            (12277, 1125, 57446, ()),
            (22129, 4863, 199607, (199608,)),
            (17870, 2389, 107412, ()),
            (30485, 7519, 339644, (339645,)),
        ):
            with self.subTest(reference=reference):
                self._exercise_recovery_and_removal(
                    reference, state_reference, selected, rejected
                )

    def test_owned_end_resource_state_32617_ap_gain_checkpoint_and_real_702_exclusion(
        self,
    ):
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        values = self._fixture(
            reference=32617,
            slot=17,
            level=245,
            select_elements=True,
            breed=3,
            active_spells=[2008, 2014, 2018],
        )
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        actor = runtime.fight.actors[owner]
        self.assertIn(9077, {entry.reference for entry in actor.state_ledger.entries})
        initial_max_ap = actor.max_ap

        def cast(reference, target):
            fight = runtime.fight
            grant = granted_spells(fight, owner).get(reference)
            spell_uid = grant["uid"] if grant is not None else (owner << 32) | reference
            transaction = prepare_server_spell(
                struct.pack(">qqiih", owner, spell_uid, *target),
                char,
                {-200: monster},
                fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
            self.assertTrue(any(transaction.outcomes))
            self.assertTrue(
                commit_spell_transaction(
                    runtime,
                    transaction,
                    stats_serializer=stats,
                )
            )
            self.assertIs(runtime.fight, transaction.fight)

        # A real AP-costing Enutrof spell leaves current AP below its maximum.
        # Native eWN [1, 0, 0] adds one maximum AP but leaves current AP alone;
        # the ordinary turn refresh is separate from this end-boundary effect.
        actor = runtime.fight.actors[owner]
        cast(2008, runtime.fight.actors[-200].position)
        before_end = runtime.fight.actors[owner].ap
        self.assertGreaterEqual(before_end, 1)
        self.assertLess(before_end, initial_max_ap)
        before_boundary = snapshot(runtime.fight)
        isolated_end, _ = prepare_server_turn_end(
            char,
            {-200: monster},
            runtime.fight,
            deck,
            actor_id=owner,
            action_id=runtime.action_id + 1,
            rng=rng,
        )
        self.assertEqual(isolated_end.actors[owner].ap, before_end)
        self.assertEqual(isolated_end.actors[owner].max_ap, initial_max_ap + 1)
        self.assertEqual(snapshot(runtime.fight), before_boundary)
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=4096):
            advance_actual_turn(runtime)
        gained = runtime.fight.actors[owner]
        # The live boundary preserves current AP while increasing its maximum;
        # turn refresh and expiry are verified independently below.
        self.assertEqual(gained.max_ap, initial_max_ap + 1)
        completed_child = [
            row.get("effect_reference") == 408297
            and row.get("status") == "completed"
            and row.get("caster_id") == row.get("target_id") == owner
            for row in trace
        ]
        self.assertEqual(sum(completed_child), 1, trace)
        ap_children = [
            row
            for row in runtime.fight.owned_stat_effects.values()
            if row.get("effect_class") == 31
            and row.get("target_id") == owner
            and row.get("stat_id") == 2
            and row.get("actual") == 1
        ]
        self.assertEqual(len(ap_children), 1, ap_children)
        self.assertEqual(ap_children[0]["timer"]["actor_id"], owner)
        self.assertEqual(ap_children[0]["timer"]["phase"], "end")

        # Checkpoint serialization/reconstruction preserves the applied AP
        # delta and its effect identity; a second Ready is idempotent.
        from wakfu_server.combat_reproduction_state import encode_state, decode_state

        before_checkpoint = snapshot(runtime.fight)
        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), before_checkpoint)
        runtime.fight = restored
        same, no_packets, empty = prepare_ready(
            runtime.fight,
            char["account_id"],
            True,
            initialize=lambda preview, action_id: prepare_server_initialization(
                char,
                {-200: monster},
                preview,
                char["account_id"],
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            ),
            stats_serializer=stats,
            runtime_stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        self.assertIs(same, runtime.fight)
        self.assertIsNone(no_packets)
        self.assertEqual(empty, ())
        self.assertEqual(snapshot(runtime.fight), before_checkpoint)

        # The original Enutrof 2038 cast installs genuine state702. The AP
        # criterion's `not HasState(702)` branch must then reject 408297.
        for _ in range(20):
            if runtime.fight.current.id == owner:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, owner)
        cast(2038, runtime.fight.actors[owner].position)
        self.assertIn(
            702,
            {
                entry.reference
                for entry in runtime.fight.actors[owner].state_ledger.entries
            },
        )
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=4096):
            advance_actual_turn(runtime)
        self.assertTrue(
            any(
                row.get("effect_reference") == 408296
                and row.get("status")
                in ("condition_rejected", "rejected", "skipped_condition")
                and row.get("caster_id") == row.get("target_id") == owner
                for row in trace
            ),
            trace,
        )
        self.assertFalse(
            any(
                row.get("effect_reference") == 408297
                and row.get("status") == "completed"
                for row in trace
            ),
            trace,
        )

    def _exercise_recovery_and_removal(
        self, reference=14191, state_reference=5384, selected=254678, rejected=(254679,)
    ):
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

        values = self._fixture(reference=reference)
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        state, uid = self._assert_carrier(values, state_reference, selected, rejected)
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
                if s.reference == state_reference
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
        self.assertEqual(null_rows[0]["effect"]["definition"], selected)
        self.assertIs(null_rows[0]["immediate"], False)
        self.assertFalse(
            any(p["effect"]["definition"] in rejected for p in packet_rows)
        )
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
