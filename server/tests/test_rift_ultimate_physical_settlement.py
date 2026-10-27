"""Three Ultimate Rift settlements against the recovered 29-species loot cohort."""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import combat_drops, rift_rewards, rift_runtime
from wakfu_server.combat_encounter_roles import bind_roles
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.rift_encounter_roles import roles_for_catalog
from wakfu_server.rift_policy import select_wave


class UltimatePhysicalSettlementTests(PostgresCase):
    def test_three_native_pools_physical_delivery_rollback_and_reopen(self):
        path = Path(
            os.environ.get(
                "WAKFU_ULTIMATE_LOOT_COHORT",
                ".runtime/rift-phase2-dataset/ultimate29-native-loot.json",
            )
        )
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "c2a1fe1f108c1195f6c762f2aa1e6aa92c772bba211318dd9dfb596769f54166",
        )
        source = json.loads(raw)
        catalog = dict(
            source_sha256=source["source_documents"]["monster-encyclopedia.json"][
                "sha256"
            ],
            monsters={
                int(ref): row["combat_drops"] for ref, row in source["monsters"].items()
            },
        )
        self.assertEqual(len(catalog["monsters"]), 29)
        saved = []
        # Only the source reader is projected: eligibility, bindings, pool
        # resolution, RNG receipts and physical delivery remain production code.
        with patch.object(combat_drops, "native_drop_catalog", return_value=catalog):
            for cohort in source["pools"]:
                wave_id = cohort["wave_id"]
                account = self.store.register(f"ultimate-{wave_id}", "local-password")[
                    "id"
                ]
                character = self.store.create_character(
                    account,
                    {5: "Ultfrigost", 8: "Ultzinit", 37: "Ultshukrute"}[wave_id],
                )
                cid = character["id"]
                generation = self.store.begin_session(account)
                self.store.select_character(account, generation, cid)
                with self.store.connection() as db:
                    run = rift_runtime.enter(
                        db,
                        wave_id,
                        cid,
                        [cid],
                        seed=f"physical-{wave_id}",
                        authorize=lambda c, m: True,
                    )
                    from wakfu_server.rift_key_admission import contract
                    from wakfu_server import quest_inventory

                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=%s",
                        (run["catalog"]["map_id"], run["instance_id"], cid),
                    )
                    price = contract(run["catalog"])
                    key_reference, key_quantity = price["reference"], price["quantity"]
                    if (
                        key_reference
                        in quest_inventory._SOURCE["account_quest_property_references"]
                    ):
                        db.execute(
                            "INSERT INTO account_quest_items(account_id,reference,quantity) VALUES(%s,%s,%s)",
                            (account, key_reference, key_quantity),
                        )
                    elif key_reference in quest_inventory.REFERENCES:
                        db.execute(
                            "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,%s,%s)",
                            (cid, key_reference, key_quantity),
                        )
                    else:
                        bag = db.execute(
                            "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                            (cid,),
                        ).fetchone()["uid"]
                        db.execute(
                            "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,0)",
                            (cid, key_reference, key_quantity, bag),
                        )
                    roles = roles_for_catalog(run["catalog"], run["policy"])
                    self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
                    fight_id = db.execute(
                        "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                    ).fetchone()["id"]
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,%s,%s)",
                        (fight_id, cid, account, roles.player_team, generation),
                    )
                    rift_runtime.start(db, run["instance_id"], cid, fight_id)
                    refs, identities = [], []
                    for wave in (1, 2):
                        selected = select_wave(
                            run["catalog"], run["policy"], run["seed"], wave
                        )
                        ids = [-(len(identities) + i + 1) for i in range(len(selected))]
                        rift_runtime.bind_wave(
                            db, run["instance_id"], wave, list(zip(ids, selected))
                        )
                        rift_runtime.record_wave(
                            db, run["instance_id"], wave, ids, turn=wave + 1
                        )
                        refs.extend(selected)
                        identities.extend(ids)
                    db.execute(
                        "UPDATE combat_fights SET status='finished' WHERE id=%s",
                        (fight_id,),
                    )
                    run = rift_runtime._run(db, run["instance_id"])
                player = Actor(
                    cid,
                    roles.player_team,
                    (0, 0, 0),
                    character["hp"],
                    6,
                    3,
                    100,
                    character["level"],
                    account,
                    True,
                )
                npcs = [
                    Actor(identity, roles.npc_team, (i + 1, 0, 0), 20, 4, 2, 1, 1)
                    for i, identity in enumerate(identities)
                ]
                cells = [(i, 0, 0) for i in range(len(npcs) + 1)]
                fight = Fight(
                    fight_id,
                    [player] + npcs,
                    cells,
                    {roles.player_team: {cells[0]}, roles.npc_team: set(cells[1:])},
                )
                bind_roles(
                    fight,
                    roles_for_catalog(
                        run["catalog"], run["policy"], monster_references=refs
                    ),
                    player_ids=[cid],
                    npc_ids=identities,
                )
                for npc in npcs:
                    npc.hp = 0
                fight.phase, fight.winner = "finished", roles.player_team
                fight.rift_wave_state = {"instance_id": run["instance_id"]}
                fight.rift_monsters = {
                    identity: dict(
                        id=identity, ref=ref, level=1, instance_id=run["instance_id"]
                    )
                    for identity, ref in zip(identities, refs)
                }

                def settle(db, store):
                    return rift_runtime.settle(
                        db,
                        run["instance_id"],
                        fight_id,
                        outcome="won",
                        turn=run["policy"]["turn_budget"],
                        apply_rewards=lambda conn, frozen, result: rift_rewards.apply(
                            conn,
                            frozen,
                            result,
                            store=store,
                            eligible_character_ids=[cid],
                            rng=lambda n: 0,
                            fight=fight,
                        ),
                    )

                with self.assertRaisesRegex(RuntimeError, "rollback physical"):
                    with self.store.connection() as db:
                        settle(db, self.store)
                        raise RuntimeError("rollback physical")
                with self.store.connection() as db:
                    for table in (
                        "rift_settlement_receipts",
                        "rift_item_reward_receipts",
                        "fight_drop_awards",
                        "fight_drop_delivery_receipts",
                    ):
                        self.assertEqual(
                            db.execute(
                                f"SELECT count(*) AS n FROM {table} WHERE fight_id=%s",
                                (fight_id,),
                            ).fetchone()["n"],
                            0,
                        )
                    settle(db, self.store)
                    receipt = db.execute(
                        "SELECT policy_snapshot FROM rift_item_reward_receipts WHERE instance_id=%s AND character_id=%s",
                        (run["instance_id"], cid),
                    ).fetchone()
                    equipment = next(
                        pool
                        for pool in receipt["policy_snapshot"]["pools"]
                        if pool["name"] == "equipment"
                    )
                    self.assertEqual(equipment["source"], "native_rift_monsters")
                    self.assertEqual(
                        equipment["references"], cohort["eligible_references"]
                    )
                    self.assertTrue(
                        set(equipment["references"]).isdisjoint({2021, 2022, 2023})
                    )
                    draws = db.execute(
                        "SELECT snapshot FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s",
                        (fight_id, cid),
                    ).fetchone()["snapshot"]["draws"]
                    index = next(
                        i
                        for i, pool in enumerate(receipt["policy_snapshot"]["pools"])
                        if pool["name"] == "equipment"
                    )
                    equipment_draw = next(
                        draw for draw in draws if draw["pool_index"] == index
                    )
                    self.assertTrue(equipment_draw["success"])
                    item = db.execute(
                        "SELECT sum(quantity) AS q FROM inventory_items WHERE character_id=%s AND reference=%s",
                        (cid, equipment_draw["reference"]),
                    ).fetchone()
                    self.assertEqual(item["q"], equipment_draw["quantity"])
                    count = db.execute(
                        "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s",
                        (fight_id,),
                    ).fetchone()["n"]
                reopened = self.reopen()
                with reopened.connection() as db, patch.object(
                    rift_rewards, "plan", side_effect=AssertionError("replay rerolled")
                ):
                    settle(db, reopened)
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM fight_drop_delivery_receipts WHERE fight_id=%s",
                            (fight_id,),
                        ).fetchone()["n"],
                        count,
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT sum(quantity) AS q FROM inventory_items WHERE character_id=%s AND reference=%s",
                            (cid, equipment_draw["reference"]),
                        ).fetchone()["q"],
                        equipment_draw["quantity"],
                    )
                saved.append(wave_id)
        self.assertEqual(saved, [5, 8, 37])
