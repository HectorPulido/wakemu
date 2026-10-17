import unittest

from tools.combat_movement_differential import (
    DifferentialSetupError,
    compare_movement,
    observe_movement,
)


class MovementDifferentialTests(unittest.TestCase):
    def compare(self, legacy, candidate=None, **kwargs):
        return compare_movement(
            case_id="fixture",
            make_world=lambda context: {"position": [0, 0], "ap": 6},
            legacy=legacy,
            candidate=legacy if candidate is None else candidate,
            project_state=lambda world: world,
            **kwargs,
        )

    def test_independent_inputs_rng_clock_events_and_exact_recipient_packets(self):
        inputs = {"path": [1, 2]}

        def move(world, arguments, context):
            world["position"] = arguments["path"]
            arguments["path"].append(3)
            world["ap"] -= 1
            context.event(("move", context.rng.randrange(100), context.clock_ns()))
            context.packet(7, 315, b"\x00\x01")
            return True

        report = self.compare(move, inputs=inputs)
        self.assertTrue(report["equivalent"])
        self.assertTrue(report["actions_succeeded"])
        self.assertEqual(inputs, {"path": [1, 2]})
        self.assertEqual(report["legacy"]["clock_reads"], 1)
        self.assertFalse(report["live_delivery"])
        self.assertFalse(report["native_client_qualified"])

    def test_resources_and_packet_order_are_not_normalized(self):
        def old(world, inputs, context):
            world["ap"] -= 1
            context.packet(7, 315, b"first")
            context.packet(7, 315, b"second")

        def new(world, inputs, context):
            world["ap"] -= 2
            context.packet(7, 315, b"second")
            context.packet(7, 315, b"first")

        report = self.compare(old, new)
        self.assertFalse(report["equivalent"])
        self.assertTrue(
            any(row["path"].startswith("/state/") for row in report["differences"])
        )
        self.assertTrue(
            any(row["path"].startswith("/packets/") for row in report["differences"])
        )
        self.assertEqual(
            {row["classification"] for row in report["differences"]}, {"unresolved"}
        )

    def test_event_packet_interleaving_is_not_hidden_by_equal_separate_journals(self):
        def old(world, inputs, context):
            context.packet(7, 315, b"same")
            context.event(("area-entry", 8))

        def new(world, inputs, context):
            context.event(("area-entry", 8))
            context.packet(7, 315, b"same")

        report = self.compare(old, new)
        self.assertEqual(report["legacy"]["events"], report["candidate"]["events"])
        self.assertEqual(report["legacy"]["packets"], report["candidate"]["packets"])
        self.assertFalse(report["equivalent"])
        self.assertEqual(report["legacy"]["observations"][0]["kind"], "packet")
        self.assertEqual(report["candidate"]["observations"][0]["kind"], "event")
        self.assertTrue(
            all(
                row["path"].startswith("/observations/")
                for row in report["differences"]
            )
        )

    def test_equal_exceptions_are_equivalence_not_success(self):
        def reject(world, inputs, context):
            raise ValueError("blocked")

        report = self.compare(reject)
        self.assertTrue(report["equivalent"])
        self.assertFalse(report["actions_succeeded"])
        self.assertEqual(report["legacy"]["error"]["type"], "builtins.ValueError")

    def test_success_and_exception_differ(self):
        def reject(world, inputs, context):
            raise ValueError("blocked")

        report = self.compare(lambda *args: None, reject)
        self.assertFalse(report["equivalent"])
        self.assertFalse(report["actions_succeeded"])

    def test_shared_mutable_world_is_rejected_before_execution(self):
        shared = {"position": [0, 0]}
        with self.assertRaisesRegex(DifferentialSetupError, "share mutable"):
            compare_movement(
                case_id="alias",
                make_world=lambda context: shared,
                legacy=lambda *args: None,
                candidate=lambda *args: None,
                project_state=lambda world: world,
            )

    def test_real_observable_stats_hidden_shared_fight_is_rejected(self):
        from test_combat_state import FightStateTests
        from wakfu_server.combat_characteristic_link import (
            ObservableCharacteristicStats,
        )

        owner = FightStateTests().fight()
        with self.assertRaisesRegex(DifferentialSetupError, "share mutable"):
            compare_movement(
                case_id="shared-observable-owner",
                make_world=lambda context: {
                    "stats": ObservableCharacteristicStats({2: 6}, owner, 100)
                },
                legacy=lambda *args: None,
                candidate=lambda *args: None,
                project_state=lambda world: {"stats": dict(world["stats"])},
            )

    def test_real_pointer_checkpoints_hidden_shared_qi_is_rejected(self):
        from test_combat_position_mutation import PositionMutationTests
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

        owner, _, _ = PositionMutationTests().fixture(pointer=True)
        qi = owner.native_pointer_checkpoint._qi
        with self.assertRaisesRegex(DifferentialSetupError, "share mutable"):
            compare_movement(
                case_id="shared-checkpoint-owner",
                make_world=lambda context: {"checkpoint": NativePointerCheckpoint(qi)},
                legacy=lambda *args: None,
                candidate=lambda *args: None,
                project_state=lambda world: dict(world["checkpoint"]),
            )

    def test_independent_real_observable_and_pointer_owners_are_accepted(self):
        from copy import deepcopy
        from test_combat_position_mutation import PositionMutationTests
        from wakfu_server.combat_characteristic_link import (
            ObservableCharacteristicStats,
        )

        def factory(context):
            fight, identity, _ = PositionMutationTests().fixture(pointer=True)
            actor = fight.actors[identity]
            actor.effect_stats = ObservableCharacteristicStats(
                {2: actor.ap, 3: actor.mp}, fight, identity
            )
            # Trove cells normally borrow one cached read-only catalog dict.
            # This strict isolation recipe detaches it while retaining aliases
            # among cells within the same world; the guard stays unchanged.
            detached_contracts = {}
            for cell in fight.native_pointer_checkpoint._qi.cells.values():
                identity = id(cell.contract)
                if identity not in detached_contracts:
                    detached_contracts[identity] = deepcopy(cell.contract)
                cell.contract = detached_contracts[identity]
            return fight

        report = compare_movement(
            case_id="independent-live-owners",
            make_world=factory,
            legacy=lambda *args: None,
            candidate=lambda *args: None,
            project_state=lambda world: world,
        )
        self.assertTrue(report["equivalent"])

    def test_event_capture_is_not_changed_by_later_mutation(self):
        def operation(world, inputs, context):
            event = [1]
            context.event(event)
            event.append(2)

        report = self.compare(operation)
        self.assertTrue(report["equivalent"])
        self.assertEqual(len(report["legacy"]["events"][0]["nodes"][0]["items"]), 1)

    def test_unobserved_random_consumption_is_a_difference(self):
        def candidate(world, inputs, context):
            context.rng.random()

        report = self.compare(lambda *args: None, candidate)
        self.assertTrue(
            any(row["path"].startswith("/rng_state/") for row in report["differences"])
        )

    def test_expected_correction_does_not_erase_difference(self):
        report = self.compare(
            lambda *args: False,
            lambda *args: True,
            classify_difference=lambda row: "expected",
        )
        self.assertFalse(report["equivalent"])
        self.assertEqual(report["differences"][0]["classification"], "expected")


class ActualPositionDifferentialTests(unittest.TestCase):
    def test_actual_walking_whole_route_rejection_and_callback_interruption(self):
        from test_combat_state import FightStateTests
        from wakfu_server.combat_movement import movement
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_reproduction_state import decode_state

        def factory(context):
            fight = FightStateTests().fight()
            fight.ready(1)
            return fight

        self.walking_reports = {}
        for scenario in ("whole-route", "invalid-route", "callback-interruption"):

            def operation():
                def walk(fight, inputs, context):
                    origin = fight.actors[100].position

                    def callback(preview, actor, before, destination):
                        context.event(("step", before, destination, actor.mp))
                        move_registered_actor(preview, actor, (0, 1, 0))
                        context.event(("callback-relocation", actor.position))

                    event = fight.move(
                        1,
                        100,
                        inputs["path"],
                        step_callback=callback
                        if scenario == "callback-interruption"
                        else None,
                    )
                    context.event(event)
                    opcode, payload = movement(
                        fight.id, 1, 100, [origin, *event["path"]], 0
                    )
                    context.packet(1, opcode, payload)
                    return event

                return walk

            with self.subTest(scenario=scenario):
                path = (
                    [(1, 0, 0), (3, 0, 0)]
                    if scenario == "invalid-route"
                    else [(1, 0, 0), (2, 0, 0)]
                )
                report = observe_movement(
                    case_id="actual-walking-" + scenario,
                    make_world=factory,
                    operation=operation(),
                    project_state=lambda fight: fight,
                    inputs={"path": path},
                )
                self.walking_reports[scenario] = report
                after = decode_state(report["current"]["state"])
                if scenario == "invalid-route":
                    self.assertFalse(report["action_succeeded"])
                    self.assertEqual(
                        report["current"]["error"]["type"], "builtins.ValueError"
                    )
                    self.assertEqual(
                        report["current"]["error"]["message"],
                        "Invalid combat movement path",
                    )
                    self.assertEqual(report["before"], report["current"]["state"])
                    self.assertEqual(report["current"]["packets"], [])
                else:
                    self.assertTrue(
                        report["action_succeeded"], report["current"]["error"]
                    )
                    event = decode_state(report["current"]["result"])
                    self.assertEqual(
                        event["cost"], 1 if scenario == "callback-interruption" else 2
                    )
                    self.assertEqual(
                        after.actors[100].mp,
                        2 if scenario == "callback-interruption" else 1,
                    )
                    self.assertEqual(
                        after.actors[100].position,
                        (0, 1, 0) if scenario == "callback-interruption" else (2, 0, 0),
                    )
                    self.assertEqual(
                        event["path"],
                        path[:1] if scenario == "callback-interruption" else path,
                    )
                    self.assertEqual(
                        [packet["opcode"] for packet in report["current"]["packets"]],
                        [13624],
                    )

    def test_registered_position_boundary_with_full_qi_and_resources(self):
        from test_combat_qi_fight import NativeQIFightLifecycleTests
        from wakfu_server.combat_qi_fight import move_registered_actor

        def factory(context):
            fixture = NativeQIFightLifecycleTests()
            fight, _, _ = fixture.fixture()
            fixture.initialize(fight)
            return fight

        def operation():
            def move(fight, inputs, context):
                move_registered_actor(fight, fight.actors[7], inputs["destination"])

            return move

        report = observe_movement(
            case_id="actual-registered-qi-position",
            make_world=factory,
            operation=operation(),
            project_state=lambda fight: fight,
            inputs={"destination": (1, 0, 0)},
        )
        self.assertTrue(report["action_succeeded"], report["current"]["error"])
        from wakfu_server.combat_reproduction_state import decode_state
        from wakfu_server.combat_qi_fight import current_registry

        before, after = decode_state(report["before"]), decode_state(
            report["current"]["state"]
        )
        self.assertEqual(after.actors[7].position, (1, 0, 0))
        self.assertEqual(after.actors[-7].position, before.actors[-7].position)
        self.assertEqual(
            {
                key: (actor.hp, actor.ap, actor.mp)
                for key, actor in after.actors.items()
            },
            {
                key: (actor.hp, actor.ap, actor.mp)
                for key, actor in before.actors.items()
            },
        )
        self.assertIn(
            after.actors[7].native_obstacle_id,
            current_registry(after).snapshot().U(1, 0),
        )

    def test_actual_reciprocal_carry_move_and_release(self):
        from test_combat_carrying import CarryingLifecycleTests
        from wakfu_server.combat_carrying import carry_registered, release_registered
        from wakfu_server.combat_qi_fight import move_registered_actor

        def factory(context):
            return CarryingLifecycleTests().fixture()[0]

        def operation():
            def move(fight, inputs, context):
                carrier, carried = (fight.actors[7], fight.actors[-7])
                context.event(
                    ("carry", carry_registered(fight, carrier, carried, source_uid=1))
                )
                move_registered_actor(fight, carrier, (1, 1, 0))
                context.event(("move", carrier.position, carried.position))
                context.event(
                    (
                        "release",
                        release_registered(fight, carrier, (2, 1, 0), direction=2),
                    )
                )

            return move

        report = observe_movement(
            case_id="actual-carry-move-release",
            make_world=factory,
            operation=operation(),
            project_state=lambda fight: fight,
        )
        self.assertTrue(report["action_succeeded"], report["current"]["error"])
        from wakfu_server.combat_reproduction_state import decode_state
        from wakfu_server.combat_qi_fight import current_registry

        before, after = decode_state(report["before"]), decode_state(
            report["current"]["state"]
        )
        carrier, carried = after.actors[7], after.actors[-7]
        self.assertEqual((carrier.position, carried.position), ((1, 1, 0), (2, 1, 0)))
        self.assertIsNone(carrier.native_carried_actor_id)
        self.assertIsNone(carried.native_carrier_id)
        self.assertEqual(carried.direction, 2)
        self.assertEqual(
            carried.native_obstacle_id, before.actors[-7].native_obstacle_id
        )
        self.assertTrue(
            current_registry(after).slots[carried.native_obstacle_id]["indexed"]
        )
        self.assertEqual(
            current_registry(after).snapshot().U(2, 1),
            frozenset({carried.native_obstacle_id}),
        )
        self.assertEqual(
            [decode_state(event)[0] for event in report["current"]["events"]],
            ["carry", "move", "release"],
        )
        self.assertEqual(
            {
                key: (actor.hp, actor.ap, actor.mp)
                for key, actor in after.actors.items()
            },
            {
                key: (actor.hp, actor.ap, actor.mp)
                for key, actor in before.actors.items()
            },
        )

    def test_actual_glyph_enter_inside_exit_sequence(self):
        from test_combat_effect_area_events import AreaEventTests

        def factory(context):
            runtime, row, calls = AreaEventTests().fixture(
                entry=(10001, 10008), exit=(10002,)
            )
            return {"runtime": runtime, "row": row, "calls": calls}

        def projection(world):
            fight = world["runtime"].fight
            return {
                "actors": {key: vars(actor) for key, actor in fight.actors.items()},
                "areas": fight.native_effect_areas,
                "retained": fight.native_retained_records,
                "phase": fight.phase,
                "current": fight.current.id,
                "calls": [
                    vars(call) if hasattr(call, "__dict__") else call
                    for call in world["calls"]
                ],
            }

        def operation():
            def move(world, inputs, context):
                runtime = world["runtime"]
                target = runtime.fight.actors[8]
                for origin, destination in (
                    ((1, 0, 3), (0, 0, 3)),
                    ((0, 0, 3), (0, 0, 3)),
                    ((0, 0, 3), (1, 0, 3)),
                ):
                    target.position = destination
                    result = runtime.movement(8, from_cell=origin, to_cell=destination)
                    context.event(("movement", origin, destination, result))

            return move

        report = observe_movement(
            case_id="actual-glyph-enter-inside-exit",
            make_world=factory,
            operation=operation(),
            project_state=projection,
        )
        self.assertTrue(report["action_succeeded"], report["current"]["error"])
        from wakfu_server.combat_reproduction_state import decode_state

        events = [decode_state(event) for event in report["current"]["events"]]
        self.assertEqual([event[0] for event in events], ["movement"] * 3)
        self.assertEqual(
            [event[-1] for event in events],
            [((True,), (), ()), ((), (True,), ()), ((), (), (False,))],
        )
        after = decode_state(report["current"]["state"])
        self.assertEqual(after["actors"][8]["position"], (1, 0, 3))
        self.assertEqual(set(after["areas"]), {901})
        self.assertEqual(after["retained"], {})
        self.assertEqual(len(after["calls"]), 2)
