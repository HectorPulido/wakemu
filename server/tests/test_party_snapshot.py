import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import party_snapshot, player_parties
from wakfu_server.party_wire import roster


class PartySnapshotTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    def player(self, label, *, sex, breed):
        account = self.store.register(f"s{uuid.uuid4().hex[:10]}", "test-password")[
            "id"
        ]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = "Player" + uuid.uuid4().hex[:8].translate(letters)
        character = self.store.create_character(account, name, sex=sex, breed=breed)
        generation = self.store.begin_session(account, ttl=10_000)
        self.store.select_character(account, generation, character["id"])
        return {"account": account, "generation": generation, "character": character}

    def test_postgres_membership_snapshot_encodes_appearance_death_level_and_fight(
        self,
    ):
        leader = self.player("leader", sex=0, breed=8)
        member = self.player("member", sex=1, breed=15)
        token = player_parties.invite(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            member["character"]["id"],
        )
        party_id = player_parties.answer(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            token,
            True,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                (member["character"]["id"],),
            )

        snapshot = player_parties.snapshot(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
        )
        levels = {
            leader["character"]["id"]: 7,
            member["character"]["id"]: 12,
        }
        opcode, body = party_snapshot.packet(
            snapshot,
            effective_levels=levels,
            fighting_ids={leader["character"]["id"]},
        )
        rows = {row["id"]: row for row in snapshot["members"]}
        expected = roster(
            party_id,
            leader["character"]["id"],
            [
                dict(
                    id=rows[identity]["id"],
                    association_id=rows[identity]["account_id"],
                    name=rows[identity]["name"],
                    breed=rows[identity]["breed"],
                    portrait_variant=int(rows[identity]["sex"]),
                    native_identity_flag=False,
                    level=rows[identity]["level"],
                    effective_level=levels[identity],
                    in_fight=identity == leader["character"]["id"],
                    dead=identity == member["character"]["id"],
                    hp=rows[identity]["hp"],
                    max_hp=rows[identity]["max_hp"],
                )
                for identity in (leader["character"]["id"], member["character"]["id"])
            ],
        )
        self.assertEqual((opcode, body), expected)
        parsed = self._decode_roster(body)
        self.assertEqual(
            [
                (
                    row["breed"],
                    row["portrait_variant"],
                    row["dead"],
                    row["in_fight"],
                    row["level"],
                    row["effective_level"],
                )
                for row in parsed
            ],
            [
                (8, 0, False, True, rows[leader["character"]["id"]]["level"], 7),
                (15, 1, True, False, rows[member["character"]["id"]]["level"], 12),
            ],
        )
        before_revision = snapshot["revision"]
        refreshed = player_parties.snapshot(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
        )
        self.assertEqual(refreshed["revision"], before_revision)
        self.assertEqual(refreshed["members"], snapshot["members"])

    def test_owned_hero_party_rows_set_native_activation_identity_flag(self):
        from wakfu_server.characters import heroes

        account = self.store.register(f"h{uuid.uuid4().hex[:10]}", "test-password")[
            "id"
        ]
        main = self.store.create_character(account, "Party Hero Main", sex=0, breed=8)
        hero = self.store.create_character(account, "Party Hero Actor", sex=1, breed=15)
        generation = self.store.begin_session(account, ttl=10_000)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])

        with self.store.connection() as db:
            main_row = self.store.character(account, main["id"], db)
            members = heroes.augment_party(db, self.store, [main_row])
            snapshot = {
                "party_id": (1 << 56) | 123,
                "leader_id": main["id"],
                "members": members,
            }
            levels = {row["id"]: row["effective_level"] for row in members}
        opcode, body = party_snapshot.packet(snapshot, effective_levels=levels)
        self.assertEqual(1184, opcode)
        decoded = {row["id"]: row for row in self._decode_roster(body)}
        self.assertFalse(decoded[main["id"]]["native_identity_flag"])
        self.assertTrue(decoded[hero["id"]]["native_identity_flag"])

    def test_snapshot_packet_requires_explicit_effective_levels_and_consistent_death(
        self,
    ):
        leader = self.player("leader", sex=0, breed=8)
        member = self.player("member", sex=1, breed=15)
        token = player_parties.invite(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            member["character"]["id"],
        )
        player_parties.answer(
            self.store,
            member["account"],
            member["generation"],
            member["character"]["id"],
            token,
            True,
        )
        snapshot = player_parties.snapshot(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
        )
        ids = {row["id"] for row in snapshot["members"]}
        with self.assertRaisesRegex(ValueError, "effective level"):
            party_snapshot.packet(snapshot, effective_levels={next(iter(ids)): 1})

        inconsistent = dict(snapshot)
        inconsistent["members"] = [dict(row) for row in snapshot["members"]]
        inconsistent["members"][0]["health_dead"] = True
        with self.assertRaisesRegex(ValueError, "disagrees with health"):
            party_snapshot.packet(
                inconsistent, effective_levels={identity: 1 for identity in ids}
            )

        missing = dict(snapshot)
        missing["members"] = [dict(row) for row in snapshot["members"]]
        del missing["members"][0]["sex"]
        with self.assertRaisesRegex(ValueError, "appearance or death"):
            party_snapshot.packet(
                missing, effective_levels={identity: 1 for identity in ids}
            )

    @staticmethod
    def _decode_roster(body):
        group_id, party_type, reserved, leader_id, count = struct.unpack_from(
            ">qBhqh", body
        )
        assert group_id >> 56 == 1 and party_type == 0 and reserved == 8
        offset = struct.calcsize(">qBhqh")
        rows = []
        for _ in range(count):
            identity, size = struct.unpack_from(">qh", body, offset)
            record = body[offset + 10 : offset + 10 + size]
            offset += 10 + size
            section_count = record[0]
            directories = {
                record[1 + index * 5]: struct.unpack_from(">i", record, 2 + index * 5)[
                    0
                ]
                for index in range(section_count)
            }

            def section(tag):
                start = directories[tag]
                end = min(
                    (position for position in directories.values() if position > start),
                    default=len(record),
                )
                return record[start + 1 : end]

            appearance = section(0)
            account_id, character_id, name_length = struct.unpack_from(
                ">qqB", appearance
            )
            name_start = struct.calcsize(">qqB")
            name = appearance[name_start : name_start + name_length].decode("utf-8")
            breed, native_flag, portrait = struct.unpack_from(
                ">h?B", appearance, name_start + name_length
            )
            hp, maximum, _percent, _gain = struct.unpack(">iiii", section(5))
            rows.append(
                {
                    "id": identity,
                    "account_id": account_id,
                    "name": name,
                    "breed": breed,
                    "portrait_variant": portrait,
                    "native_identity_flag": native_flag,
                    "in_fight": struct.unpack(">?", section(1))[0],
                    "dead": struct.unpack(">?", section(2))[0],
                    "effective_level": struct.unpack(">h", section(3))[0],
                    "hp": hp,
                    "max_hp": maximum,
                    "level": struct.unpack(">h", section(7))[0],
                }
            )
            assert character_id == identity
        assert offset == len(body) and leader_id in {row["id"] for row in rows}
        return rows


if __name__ == "__main__":
    unittest.main()
