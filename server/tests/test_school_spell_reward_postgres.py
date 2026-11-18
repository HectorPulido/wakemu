"""Exact native2780 outbox order grants the real spell and retained scroll once."""

import struct
from postgres_case import PostgresCase
from school_spell_domain_fixture import school_spell_domain
from wakfu_server.achievements import storage, service

REWARDS = [
    dict(native_class="aJP", d=4382, aeV=16, ckk=False, ckl=[5622]),
    dict(native_class="aJP", d=7294, aeV=11, ckk=False, ckl=[1000]),
    dict(native_class="aJP", d=7394, aeV=6, ckk=False, ckl=[34425]),
    dict(native_class="aJP", d=9697, aeV=5, ckk=False, ckl=[26345, 1]),
]


class SchoolSpellRewardPostgresTests(PostgresCase):
    def test_exact_original_reward_batch_survives_reconnect_and_supports_native_deck(
        self,
    ):
        from wakfu_server import spells, character_levels

        account = self.store.register("school-spell", "isolated-password")["id"]
        character = self.store.create_character(account, "School Graduate")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with school_spell_domain(runtime=False):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=30 WHERE id=%s", (character["id"],)
                )
                db.execute(
                    "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                    (character_levels.XP_BY_LEVEL[30], character["id"]),
                )
                current = self.store.character(account, character["id"], db)
                self.assertNotIn(
                    5622, {r[1] for r in spells.owned_spell_records(current)}
                )
                # An earned native outbox fixture, not a synthetic school victory.
                # Keep GIVE_PLAYER_SPELL first, exactly as original2780 defines.
                for reward in REWARDS:
                    storage.enqueue_reward(
                        db, character["id"], 2780, "once", str(reward["d"]), reward
                    )
                packets = service.drain_rewards(db, self.store, current)
                learned = [body for opcode, body in packets if opcode == 12503]
                self.assertEqual(len(learned), 1)
                self.assertEqual(
                    struct.unpack(">qiqh", learned[0]),
                    (character["id"], 5622, (character["id"] << 32) | 5622, 30),
                )
                current = self.store.character(account, character["id"], db)
                self.assertIn(5622, {r[1] for r in spells.owned_spell_records(current)})
                self.assertEqual(
                    db.execute(
                        "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=26345",
                        (account,),
                    ).fetchone()["quantity"],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s AND reference=26345",
                        (character["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=2780 AND delivered_at IS NOT NULL",
                        (character["id"],),
                    ).fetchone()["n"],
                    4,
                )
                snapshot = (current["xp"], current["kamas"])
                self.assertEqual(service.drain_rewards(db, self.store, current), [])
                replay = self.store.character(account, character["id"], db)
                self.assertEqual((replay["xp"], replay["kamas"]), snapshot)
            deck = spells.encode_deck((5622,))
            from wakfu_server.wire import proto_field

            self.store.save_build(
                account,
                generation,
                character["id"],
                0,
                dict(
                    sheet=(
                        proto_field(8, 0)
                        + proto_field(18, b"School")
                        + proto_field(24, 0xFFFFFFFF)
                        + proto_field(56, 0)
                    ),
                    equipment=b"",
                    deck=deck,
                    aptitudes=b"",
                ),
            )
            reopened = self.reopen().character(account, character["id"])
            self.assertEqual(
                spells.validate_deck(
                    bytes.fromhex(reopened["builds"][0]["deck"]),
                    reopened["breed"],
                    reopened["level"],
                    character=reopened,
                )["active"],
                [5622],
            )
            self.assertEqual(12503, spells.common_spell_packet(reopened)[0])
            self.assertEqual(
                next(
                    r["quantity"]
                    for r in reopened["account_quest_items"]
                    if r["reference"] == 26345
                ),
                1,
            )
