"""Recipient routing regression for the real World guild publication callback."""
import ast
from pathlib import Path
import struct
import unittest

from wakfu_server import guild_wire
from wakfu_server.guild_dispatch import Guilds
from wakfu_server.world import World


class GuildRemotePublicationTests(unittest.TestCase):
    def test_actual_world_callback_keeps_remote_guild_off_local_actor_after_renewal(
        self,
    ):
        deliveries = []
        world = World(
            lambda character: b"",
            lambda character: b"",
            lambda peer, opcode, body: deliveries.append((peer, opcode, body)),
            deliver_batch=lambda peer, packets: deliveries.extend(
                (peer, opcode, body) for opcode, body in packets
            ),
        )
        owner = dict(
            id=1,
            account_id=101,
            name="Owner",
            map_id=527,
            instance_id=0,
            x=0,
            y=0,
            z=0,
            direction=0,
        )
        remote = dict(owner, id=2, account_id=102, name="Remote")
        other_region_on_map = dict(owner, id=3, account_id=103, name="Other")
        elsewhere = dict(owner, id=4, account_id=104, map_id=327)
        private = dict(owner, id=5, account_id=105, instance_id=9)
        for generation, peer, character in [
            ("owner-old", "owner-old-peer", owner),
            ("remote", "remote-peer", remote),
            ("other", "other-peer", other_region_on_map),
            ("elsewhere", "elsewhere-peer", elsewhere),
            ("private", "private-peer", private),
        ]:
            world.join(generation, peer, character)
        deliveries.clear()

        # Evaluate the actual configured callback, without importing World and
        # starting listeners. Its domain publisher and membership capture are real.
        tree = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        call = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "GUILDS"
                for target in node.targets
            )
        )
        callback = next(
            keyword.value
            for keyword in call.keywords
            if keyword.arg == "remote_publish"
        )
        publish = eval(
            compile(ast.Expression(callback), "World.GUILDS.remote_publish", "eval"),
            {"WORLD": world},
        )
        local = b"\x16" + bytes(31) + guild_wire.local_section(None) + bytes(8)
        guilds = Guilds(
            object(), world, lambda: local, service=object(), remote_publish=publish
        )

        def projection(generation, peer):
            deliveries.clear()
            guilds._projection(owner["id"], generation, None)
            local_packet = guilds._packet(owner["id"], None)
            self.assertTrue(world.send_to(owner["id"], generation, *local_packet))
            own = [row for row in deliveries if row[0] == peer]
            self.assertEqual(len(own), 1)
            self.assertEqual((own[0][1], own[0][2][10]), (15548, 22))
            remote_packets = [row for row in deliveries if row[0] != peer]
            self.assertEqual(
                {row[0] for row in remote_packets}, {"remote-peer", "other-peer"}
            )
            self.assertEqual(len(remote_packets), 2)
            for _, opcode, body in remote_packets:
                self.assertEqual(opcode, 15548)
                self.assertEqual(struct.unpack_from(">qH", body)[0], owner["id"])
                self.assertEqual(body[10], 12)
            self.assertNotIn(
                "owner-old-peer",
                {row[0] for row in deliveries} if peer != "owner-old-peer" else set(),
            )

        projection("owner-old", "owner-old-peer")
        world.join("owner-new", "owner-new-peer", owner)
        projection("owner-new", "owner-new-peer")
        deliveries.clear()
        guilds._projection(owner["id"], "owner-old", None)
        self.assertEqual(deliveries, [])
        self.assertFalse(world.send_to(owner["id"], "owner-old", 15548, b"stale"))

        # Identity exclusion is recipient-local, not an account-wide filter.
        # This routing-only control does not authorize two concurrent SQL leases.
        same_account = dict(remote, id=6, account_id=owner["account_id"])
        world.join("routing-control", "same-account-other-actor", same_account)
        deliveries.clear()
        guilds._projection(owner["id"], "owner-new", None)
        self.assertIn("same-account-other-actor", {row[0] for row in deliveries})
        self.assertNotIn("owner-new-peer", {row[0] for row in deliveries})


if __name__ == "__main__":
    unittest.main()
