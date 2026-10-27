"""Actual admitted MHS uses the World serializer source with its owned Fight."""
import ast
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile

from test_rift_earned_rewards import RiftEarnedRewardTests
from wakfu_server.combat_actor import actor_effects, monster_actor_stats
from wakfu_server.combat_bootstrap import player_payload
from wakfu_server.combat_companions import fighter_stats, registered_source
from wakfu_server.breed_resources import live_wp
from wakfu_server.combat_multiplayer_wire import added, decode_added


class WorldCompanionStatsContextTests(RiftEarnedRewardTests):
    def test_actual_mhs_placement_current_and_public_marker_preserve_source_context(
        self,
    ):
        (
            run,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        # The reused payout fixture intentionally retains only (id,ref,level)
        # reward operands in rift_monsters. World snapshot serializers instead
        # consume actual owned native sources for the declared1134 arena.
        from wakfu_server.monsters import owned_instance

        fight.rift_monsters = {
            identity: owned_instance(
                row["ref"],
                row["level"],
                identity,
                map_id=1134,
                instance_id=run["instance_id"],
                team=fight.actors[identity].team,
                x=fight.actors[identity].position[0],
                y=fight.actors[identity].position[1],
                z=fight.actors[identity].position[2],
            )
            for identity, row in fight.rift_monsters.items()
        }
        self.assertEqual(len(characters), 2)
        companion = fight.actors[companion_id]
        self.assertTrue(companion.controlled)
        source = fight.native_companion_sources[str(companion_id)]
        self.assertIsNotNone(registered_source(fight, companion, source))
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        current = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "current_combat_stats"
        )
        public = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "public_member_packet"
        )
        placement = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.For)
            and isinstance(n.target, ast.Name)
            and n.target.id == "placement_actor"
            and ast.unparse(n.iter) == "candidate.actors.values()"
        )
        namespace = dict(
            fight=fight,
            candidate=fight,
            STORE=self.store,
            COMBAT_TEST=True,
            character=characters[self.ids[0]],
            TEST_MONSTERS_BY_ID=fight.rift_monsters,
            sources=characters,
            actor_payloads={},
            live_wp=live_wp,
            companion_admission={"sources": {companion_id: source}},
            player_payload=player_payload,
            monster_actor_stats=monster_actor_stats,
            actor_effects=actor_effects,
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=[deepcopy(current), deepcopy(public), deepcopy(placement)],
                        type_ignores=[],
                    )
                ),
                "actual World MHS serializer boundaries",
                "exec",
            ),
            namespace,
        )
        expected = fighter_stats(fight, companion)
        self.assertEqual(namespace["actor_payloads"][companion_id][0], expected)
        self.assertEqual(namespace["current_combat_stats"](companion, fight), expected)
        public_packet = namespace["public_member_packet"](companion, fight)
        self.assertEqual(
            public_packet,
            added(
                fight.id,
                companion.id,
                actor_type=5,
                team=companion.team,
                stats=expected,
                effects=actor_effects(),
            ),
        )
        decoded = decode_added(public_packet[1])
        self.assertEqual(
            (decoded["actor_id"], decoded["actor_type"], decoded["team"]),
            (companion.id, 5, companion.team),
        )
        self.assertEqual(decoded["stats"], expected)
        # Execute only the original cvg decoder, without any catalog/game
        # bootstrap. Its type5 byte and nested payloads must remain unchanged.
        java_source = r"""
import java.nio.file.*;
import java.util.*;
public class NativeCompanionAddedOracle {
 public static void main(String[] args) throws Exception {
  byte[] body=HexFormat.of().parseHex(args[0]);
  Class<?> type=Class.forName("cvg");
  Object packet=type.getDeclaredConstructor().newInstance();
  if (!Boolean.TRUE.equals(type.getMethod("dp",byte[].class).invoke(packet,(Object)body)))
   throw new AssertionError("Original cvg refused packet");
  if (((Byte)type.getMethod("eHC").invoke(packet)).intValue()!=5)
   throw new AssertionError("Companion discriminator changed");
  if (((Long)type.getMethod("OO").invoke(packet)).longValue()!=Long.parseLong(args[1]))
   throw new AssertionError("Actor identity changed");
  if (!Arrays.equals((byte[])type.getMethod("eHA").invoke(packet),HexFormat.of().parseHex(args[2])))
   throw new AssertionError("Fighter stats changed");
  if (!Arrays.equals((byte[])type.getMethod("eHB").invoke(packet),HexFormat.of().parseHex(args[3])))
   throw new AssertionError("Effects changed");
  System.out.println("ORIGINAL_CVG_TYPE5_PASS");
 }
}
"""
        with tempfile.TemporaryDirectory(prefix="native-companion-added-") as directory:
            oracle_source = Path(directory) / "NativeCompanionAddedOracle.java"
            oracle_source.write_text(java_source)
            client_libraries = Path(__file__).resolve().parents[2] / "client" / "lib"
            native_result = subprocess.run(
                [
                    "java",
                    "-Xmx64m",
                    "--class-path",
                    str(client_libraries / "*"),
                    str(oracle_source),
                    public_packet[1].hex(),
                    str(companion.id),
                    expected.hex(),
                    actor_effects().hex(),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(native_result.returncode, 0, native_result.stderr[-2000:])
        self.assertIn("ORIGINAL_CVG_TYPE5_PASS", native_result.stdout)

        for unknown_kind in (-1, 2, 4, 6, 127):
            with self.assertRaises(ValueError):
                added(
                    fight.id,
                    companion.id,
                    actor_type=unknown_kind,
                    team=companion.team,
                    stats=expected,
                    effects=actor_effects(),
                )
        # The same extracted placement/current helpers still serve both human
        # sources and the actual negative NPC; sidekick admission changes no IDs.
        for identity in (*characters, *fight.rift_monsters):
            self.assertTrue(namespace["actor_payloads"][identity][0])
            self.assertTrue(
                namespace["current_combat_stats"](fight.actors[identity], fight)
            )
        self.assertEqual(set(fight.actors), set(namespace["actor_payloads"]))
        forged = deepcopy(fight)
        forged.native_companion_sources[str(companion_id)]["account_id"] += 1
        with self.assertRaises(ValueError):
            namespace["current_combat_stats"](forged.actors[companion_id], forged)
        with self.assertRaises(ValueError):
            namespace["public_member_packet"](forged.actors[companion_id], forged)
        from wakfu_server.combat_remote_effects import initial_npc_actor_effects

        with self.assertRaises(ValueError):
            initial_npc_actor_effects(forged, companion_id)
        # Moving an authentic NPC constructor receipt onto a human does not
        # grant the registered type5 exception to an ordinary controlled actor.
        human_impostor = deepcopy(fight)
        human_impostor.native_npc_initialization_receipts[self.ids[0]] = deepcopy(
            fight.native_npc_initialization_receipts[companion_id]
        )
        with self.assertRaises(ValueError):
            initial_npc_actor_effects(human_impostor, self.ids[0])

    def test_actual_admitted_mhs_join_notifications_keep_registered_type5(self):
        (
            run,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        from wakfu_server.combat_shared import Session
        import wakfu_server.combat_shared as shared_module

        tree = ast.parse(Path(shared_module.__file__).read_text())
        join = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "join"
        )
        notification_loop = next(
            n
            for n in ast.walk(join)
            if isinstance(n, ast.For)
            and isinstance(n.target, ast.Name)
            and n.target.id == "member"
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "actor_payload"
                for call in ast.walk(n)
            )
        )
        code = compile(
            ast.fix_missing_locations(
                ast.Module(body=[deepcopy(notification_loop)], type_ignores=[])
            ),
            "actual Registry.join MHS notification producer",
            "exec",
        )
        payload_calls = []

        def payload(candidate, actor, session):
            payload_calls.append(actor.id)
            if actor.id == companion_id:
                return fighter_stats(candidate, actor), actor_effects()
            return player_payload(
                characters[actor.id],
                actor,
                candidate.id,
                wp=live_wp(candidate, actor.id)[0],
            )

        namespace = dict(
            __package__="wakfu_server",
            candidate=fight,
            newcomers=[
                fight.actors[identity] for identity in (*characters, companion_id)
            ],
            actor_payload=payload,
            added=added,
            notifications=[],
            session=Session(
                self.account, self.ids[0], self.generation, 1134, run["instance_id"]
            ),
        )
        exec(code, namespace)
        decoded = {
            decode_added(body)["actor_id"]: decode_added(body)
            for opcode, body in namespace["notifications"]
            if opcode == 13091
        }
        self.assertEqual(set(decoded), {*characters, companion_id})
        self.assertEqual(decoded[companion_id]["actor_type"], 5)
        self.assertEqual(
            decoded[companion_id]["stats"],
            fighter_stats(fight, fight.actors[companion_id]),
        )
        self.assertTrue(
            all(decoded[identity]["actor_type"] == 0 for identity in characters)
        )
        self.assertEqual(payload_calls, [*characters, companion_id])
        forged = deepcopy(fight)
        forged.native_companion_sources[str(companion_id)]["account_id"] += 1
        namespace.update(
            candidate=forged, newcomers=[forged.actors[companion_id]], notifications=[]
        )
        payload_calls.clear()
        with self.assertRaises(ValueError):
            exec(code, namespace)
        self.assertEqual(payload_calls, [])
        self.assertEqual(namespace["notifications"], [])
