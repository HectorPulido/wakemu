"""Party snapshots read coherent rosters without waiting on membership writers."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid

from postgres_case import PostgresCase
from wakfu_server import player_parties


class PlayerPartySnapshotMVCCPostgresTests(PostgresCase):
    def player(self):
        account = self.store.register(
            f"party-mvcc-{uuid.uuid4().hex[:12]}", "test-password"
        )["id"]
        name_suffix = (
            uuid.uuid4().hex[:8].translate(str.maketrans("0123456789", "abcdefghij"))
        )
        name = "Party" + name_suffix
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        return {
            "account": account,
            "generation": generation,
            "character": character,
        }

    def party(self):
        leader, second, third, replacement = (self.player() for _ in range(4))
        invitation = player_parties.invite(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            second["character"]["id"],
        )
        party_id = player_parties.answer(
            self.store,
            second["account"],
            second["generation"],
            second["character"]["id"],
            invitation,
            True,
        )
        invitation = player_parties.invite(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            third["character"]["id"],
        )
        self.assertEqual(
            player_parties.answer(
                self.store,
                third["account"],
                third["generation"],
                third["character"]["id"],
                invitation,
                True,
            ),
            party_id,
        )
        return party_id, leader, second, third, replacement

    def snapshot(self, leader):
        return player_parties.snapshot(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
        )

    @staticmethod
    def roster_shape(snapshot):
        return (
            snapshot["leader_id"],
            snapshot["revision"],
            tuple(row["id"] for row in snapshot["members"]),
        )

    def test_party_row_writer_does_not_block_snapshot_and_old_for_update_probe_waits(
        self,
    ):
        party_id, leader, second, third, _replacement = self.party()
        before = self.snapshot(leader)
        locked = threading.Event()
        release = threading.Event()

        def hold_party_row():
            with self.store.connection() as db:
                db.execute(
                    "SELECT id FROM player_parties WHERE id=%s FOR UPDATE", (party_id,)
                ).fetchone()
                locked.set()
                if not release.wait(5):
                    raise TimeoutError("test did not release party row")

        def legacy_row_lock_probe():
            with self.store.connection() as db:
                self.store.lock_character(
                    db,
                    leader["account"],
                    leader["generation"],
                    leader["character"]["id"],
                )
                db.execute(
                    "SELECT p.id FROM player_parties p JOIN player_party_members m "
                    "ON m.party_id=p.id WHERE m.character_id=%s FOR UPDATE OF p",
                    (leader["character"]["id"],),
                ).fetchone()
                return True

        with ThreadPoolExecutor(max_workers=3) as pool:
            writer = pool.submit(hold_party_row)
            self.assertTrue(locked.wait(5))
            current_reader = pool.submit(self.snapshot, leader)
            current = current_reader.result(timeout=3)
            self.assertEqual(self.roster_shape(current), self.roster_shape(before))

            old_reader = pool.submit(legacy_row_lock_probe)
            time.sleep(0.15)
            self.assertFalse(
                old_reader.done(),
                "the old SELECT FOR UPDATE probe should wait behind the held party row",
            )
            release.set()
            self.assertTrue(writer.result(timeout=5) is None)
            self.assertTrue(old_reader.result(timeout=5))

    def test_membership_and_leader_commit_publish_wholly_old_then_new_roster(self):
        party_id, leader, second, third, replacement = self.party()
        before = self.snapshot(leader)
        locked = threading.Event()
        commit = threading.Event()

        def change_party_atomically():
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (replacement["character"]["id"], party_id),
                )
                db.execute(
                    "DELETE FROM player_party_members WHERE party_id=%s AND character_id=%s",
                    (party_id, third["character"]["id"]),
                )
                db.execute(
                    "UPDATE player_parties SET leader_id=%s,revision=revision+1 WHERE id=%s",
                    (second["character"]["id"], party_id),
                )
                locked.set()
                if not commit.wait(5):
                    raise TimeoutError("test did not commit party replacement")

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(change_party_atomically)
            self.assertTrue(locked.wait(5))
            observed_before_commit = self.snapshot(leader)
            self.assertEqual(
                self.roster_shape(observed_before_commit), self.roster_shape(before)
            )
            commit.set()
            writer.result(timeout=5)

        after = self.snapshot(leader)
        self.assertEqual(after["party_id"], party_id)
        self.assertEqual(after["leader_id"], second["character"]["id"])
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(
            {row["id"] for row in after["members"]},
            {
                leader["character"]["id"],
                second["character"]["id"],
                replacement["character"]["id"],
            },
        )

    def test_snapshot_preserves_selected_lease_and_foreign_membership_boundaries(self):
        party_id, leader, second, _third, _replacement = self.party()
        snapshot = self.snapshot(leader)
        self.assertEqual(snapshot["party_id"], party_id)
        self.assertEqual(
            {row["id"] for row in snapshot["members"]},
            {
                leader["character"]["id"],
                second["character"]["id"],
                _third["character"]["id"],
            },
        )
        outsider = self.player()
        self.assertIsNone(self.snapshot(outsider))
        with self.assertRaises(ValueError):
            player_parties.snapshot(
                self.store,
                leader["account"],
                "stale-generation",
                leader["character"]["id"],
            )
