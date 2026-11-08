"""Re-enter a Rift with an existing local QA party, surrender without kills."""
import argparse
import json
import os
from pathlib import Path
import struct
import time
from types import SimpleNamespace

from tools import rift_tls_party_e2e as native
from tools import rift_tls_reconnect_existing as reconnect
from wakfu_server.store import Store


def snapshot(store, owners, fight_id=None):
    accounts = [owner["account_id"] for owner in owners]
    characters = [owner["character"]["id"] for owner in owners]
    with store.connection() as db:
        result = {
            "characters": db.execute(
                "SELECT id,account_id,map_id,instance_id,x,y,z,hp,max_hp "
                "FROM characters WHERE id=ANY(%s) ORDER BY id",
                (characters,),
            ).fetchall(),
            "sessions": db.execute(
                "SELECT account_id,character_id,generation FROM sessions "
                "WHERE account_id=ANY(%s) ORDER BY account_id",
                (accounts,),
            ).fetchall(),
            "companies": db.execute(
                "SELECT account_id,leader_id FROM account_hero_rosters "
                "WHERE account_id=ANY(%s) ORDER BY account_id",
                (accounts,),
            ).fetchall(),
            "party": db.execute(
                "SELECT m.character_id,m.party_id,p.leader_id "
                "FROM player_party_members m JOIN player_parties p ON p.id=m.party_id "
                "WHERE m.character_id=ANY(%s) ORDER BY m.character_id",
                (characters,),
            ).fetchall(),
            "progression": db.execute(
                "SELECT character_id,xp FROM character_progression "
                "WHERE character_id=ANY(%s) ORDER BY character_id",
                (characters,),
            ).fetchall(),
            "wallets": db.execute(
                "SELECT account_id,kamas FROM account_wallets "
                "WHERE account_id=ANY(%s) ORDER BY account_id",
                (accounts,),
            ).fetchall(),
            "active_memberships": db.execute(
                "SELECT p.fight_id,p.character_id,f.status FROM combat_fight_participants p "
                "JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=ANY(%s) "
                "AND f.status IN ('placement','active') AND NOT EXISTS ("
                "SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id "
                "AND w.character_id=p.character_id) ORDER BY p.fight_id,p.character_id",
                (characters,),
            ).fetchall(),
        }
        run = db.execute(
            "SELECT instance_id,fight_id,wave_definition_id,status,wave,completed_waves,"
            "defeated_monsters,members FROM rift_instances WHERE owner_character_id=%s "
            "ORDER BY instance_id DESC LIMIT 1",
            (characters[0],),
        ).fetchone()
        result["run"] = run
        if run and run["fight_id"] is not None:
            current_fight = run["fight_id"]
            result["fight"] = db.execute(
                "SELECT id,status FROM combat_fights WHERE id=%s", (current_fight,)
            ).fetchone()
            checkpoint = db.execute(
                "SELECT revision,status,snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (current_fight,),
            ).fetchone()
            result["checkpoint"] = (
                None
                if checkpoint is None
                else {
                    "revision": checkpoint["revision"],
                    "status": checkpoint["status"],
                    "phase": checkpoint["snapshot"].get("phase"),
                    "turn_id": checkpoint["snapshot"].get("turn_id"),
                    "winner": checkpoint["snapshot"].get("winner"),
                }
            )
        if fight_id is not None:
            result["receipts"] = {}
            for table in (
                "fight_rewards",
                "fight_reward_policy_receipts",
                "fight_drop_awards",
                "rift_item_reward_receipts",
                "combat_pve_withdrawals",
            ):
                if table == "fight_reward_policy_receipts":
                    rows = db.execute(
                        "SELECT character_id,xp,kamas,snapshot FROM "
                        + table
                        + " WHERE fight_id=%s ORDER BY character_id",
                        (fight_id,),
                    ).fetchall()
                    result["receipts"][table] = [
                        {
                            "character_id": row["character_id"],
                            "xp": row["xp"],
                            "kamas": row["kamas"],
                            "defeated_actor_ids": sorted(
                                int(monster["actor_id"])
                                for monster in row["snapshot"].get(
                                    "defeated_native_monsters", ()
                                )
                            ),
                        }
                        for row in rows
                    ]
                else:
                    result["receipts"][table] = db.execute(
                        "SELECT character_id FROM "
                        + table
                        + " WHERE fight_id=%s ORDER BY character_id",
                        (fight_id,),
                    ).fetchall()
            result["receipts"]["rift_settlement_receipts"] = db.execute(
                "SELECT outcome FROM rift_settlement_receipts "
                "WHERE fight_id=%s ORDER BY instance_id",
                (fight_id,),
            ).fetchall()
            result["selected"] = db.execute(
                "SELECT account_id,character_id FROM sessions WHERE account_id=ANY(%s) "
                "ORDER BY account_id",
                (accounts,),
            ).fetchall()
    return result


def artifact_retirement_trace(store, fight_id, caster_id=191):
    """Keep only the natural artifact lineage relevant to the retained-source fix."""
    with store.connection() as db:
        row = db.execute(
            "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight_id,)
        ).fetchone()
    if row is None:
        raise ValueError("New QA fight has no checkpoint for artifact observation")
    state = row["snapshot"]
    if isinstance(state, dict) and state.get("checkpoint_schema"):
        raise RuntimeError(
            "Full fight snapshot required for artifact retirement trace; "
            "versioned recovery checkpoint omits native effect graph evidence"
        )
    groups = []
    for key, group in (state.get("native_owned_group_effects") or {}).items():
        invocation = group.get("invocation") or {}
        children = group.get("children") or ()
        if invocation.get("caster_id") == caster_id and (
            invocation.get("reference") == 317553 or 317554 in children
        ):
            groups.append(
                {
                    "uid": int(key),
                    "effect_class": group.get("effect_class"),
                    "children": list(children),
                    "state_uid": group.get("state_uid"),
                    "invocation": {
                        name: invocation.get(name)
                        for name in (
                            "reference",
                            "caster_id",
                            "target_id",
                            "state_uid",
                            "base_uid",
                            "native_retained_container",
                            "wakemu_fresh_child_selection",
                        )
                    },
                }
            )
    activations = []
    for key, receipt in (
        state.get("native_artifact_activation_receipts") or {}
    ).items():
        if receipt.get("actor_id") == caster_id or receipt.get("reference") == 1628:
            activations.append(
                {
                    "area_uid": int(key),
                    "actor_id": receipt.get("actor_id"),
                    "reference": receipt.get("reference"),
                    "source_kind": receipt.get("source_kind"),
                    "recipient_team": receipt.get("recipient_team"),
                }
            )
    source_map = state.get("rift_monsters") or {}
    actors = state.get("actors") or {}
    defeated_originals = sorted(
        int(identity)
        for identity in source_map
        if int(identity) < 0
        and str(identity) in actors
        and actors[str(identity)].get("hp", 1) <= 0
    )
    return {
        "natural_activation_receipts": activations,
        "retained_parent_child_groups": groups,
        "checkpoint_dead_original_actor_ids": defeated_originals,
    }


def persist(args, result):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, default=str) + "\n")
    os.replace(temporary, args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--prior-fight-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument(
        "--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1"
    )
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--container", default="wakfu-local-world-1")
    parser.add_argument("--execute-existing-qa", action="store_true")
    parser.add_argument(
        "--battle-stop-after-defeats",
        type=int,
        help="Run a real native battle with the existing equipped gear; stop at a durable boundary after this many completed original kills.",
    )
    parser.add_argument(
        "--weapon-reference",
        type=int,
        help="Require this already-equipped weapon for the optional native endurance.",
    )
    parser.add_argument("--target-wave", type=int, default=999)
    parser.add_argument("--max-battle-seconds", type=int, default=10800)
    parser.add_argument("--max-turns", type=int, default=1500)
    parser.add_argument("--action-timeout", type=float, default=120)
    parser.add_argument("--seek-healing-orbs", action="store_true")
    parser.add_argument(
        "--loadout-manifest",
        type=Path,
        default=Path(".runtime/rift-followup-20261106/qa-next-six-owner-loadout.json"),
    )
    args = parser.parse_args()
    if not args.execute_existing_qa or not args.http_url.startswith(
        ("http://127.0.0.1:", "http://localhost:")
    ):
        parser.error("Explicit local existing-QA execution required")
    owners = json.loads(args.credentials.read_text())
    if len(owners) != 6 or any(
        not owner["username"].startswith("rfnetqa_") for owner in owners
    ):
        raise ValueError("Requires the exact six-owner local QA cohort")
    args.wave = 3
    args.observer_metrics = []
    endurance = args.battle_stop_after_defeats is not None
    if endurance and (
        args.battle_stop_after_defeats <= 0 or args.weapon_reference is None
    ):
        raise ValueError(
            "The optional endurance requires a positive defeat threshold and the equipped weapon reference"
        )
    loadout = None
    if endurance:
        loadout = json.loads(args.loadout_manifest.read_text())
        if (
            loadout.get("weapon_reference") != args.weapon_reference
            or len(loadout.get("equipment", ())) != 8
        ):
            raise ValueError(
                "Requested weapon or eight-item set differs from the prepared existing-cohort loadout"
            )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    peers = []
    result = {
        "status": "RUNNING",
        "prior_fight_id": args.prior_fight_id,
        "stages": [],
        "official_client": False,
    }
    try:
        before = snapshot(store, owners, args.prior_fight_id)
        with store.connection() as db:
            prior_run = db.execute(
                "SELECT instance_id,fight_id,wave_definition_id,status,wave,completed_waves,"
                "defeated_monsters,members FROM rift_instances WHERE fight_id=%s",
                (args.prior_fight_id,),
            ).fetchone()
        before["prior_run"] = prior_run
        result["before"] = before
        expected_ids = [owner["character"]["id"] for owner in owners]
        if (
            prior_run is None
            or prior_run["status"] != "closed"
            or prior_run["defeated_monsters"] <= 0
            or [row["character_id"] for row in before["party"]] != expected_ids
        ):
            raise ValueError(
                "Existing cohort is not grouped and outside the prior Rift"
            )

        catalog = native.observe(args, {"operation": "catalog", "wave": args.wave})
        entrance = catalog["entrances"][0]
        if entrance["map_id"] != 527 or catalog["map_id"] != 1314:
            raise ValueError(
                "Published Rift entrance no longer matches the existing exterior"
            )
        already_entered = (
            before["run"] is not None
            and before["run"]["status"] == "entered"
            and before["run"]["fight_id"] is None
            and before["run"]["defeated_monsters"] == 0
            and all(row["map_id"] == catalog["map_id"] for row in before["characters"])
            and len({row["instance_id"] for row in before["characters"]}) == 1
            and before["characters"][0]["instance_id"] != 0
        )
        already_exterior = (
            before["run"] is not None
            and before["run"]["fight_id"] == args.prior_fight_id
            and before["run"]["status"] == "closed"
            and all(
                row["map_id"] == 527
                and row["instance_id"] == 0
                and max(abs(row["x"] - entrance["x"]), abs(row["y"] - entrance["y"]))
                <= 3
                for row in before["characters"]
            )
        )
        if not already_entered and not already_exterior:
            raise ValueError(
                "Cohort is neither at the native exterior entrance nor in its pending new Rift entry"
            )

        native.connect_existing_scene(args, owners, peers)
        result["stages"].append("six_existing_accounts_native_login_and_selection")
        logged_in = snapshot(store, owners, args.prior_fight_id)
        if [row["character_id"] for row in logged_in["sessions"]] != expected_ids:
            raise ValueError("Native login did not select all six original characters")
        result["logged_in"] = logged_in
        if already_exterior:
            # The published entrance object is on map 527 and the cohort is
            # standing beside it. Use the ordinary native portal request.
            sent = peers[0].send(
                12870, struct.pack(">qHH", entrance["object_id"], 11, 0)
            )
            arrivals = native.wait_all(peers, 13974, timeout=90, since=sent)
            for peer in peers:
                peer.send(14689)
            result["portal_arrivals"] = [body[:64].hex() for _, body in arrivals]
            time.sleep(0.5)
        else:
            result["portal_arrivals"] = ["resumed-existing-native-entry"]
        result["after_portal"] = snapshot(store, owners, args.prior_fight_id)
        if any(
            row["map_id"] != catalog["map_id"] or row["instance_id"] == 0
            for row in result["after_portal"]["characters"]
        ):
            raise ValueError(
                "Native entrance did not place the full party in one Rift instance"
            )
        instances = {row["instance_id"] for row in result["after_portal"]["characters"]}
        if (
            len(instances) != 1
            or next(iter(instances)) == before["prior_run"]["instance_id"]
        ):
            raise ValueError(
                "Native entrance did not allocate a distinct Rift instance"
            )
        geometry = native.observe(
            args,
            {"operation": "geometry", "map_id": catalog["map_id"], "wave": args.wave},
        )
        activator = [
            row
            for row in catalog["objects"]
            if row.get("type") == "GenericActivableInteractiveElement"
        ]
        if len(activator) != 1:
            raise ValueError("Rift start activator is ambiguous")
        start = result["after_portal"]["characters"][0]
        native.walk(
            peers[0], geometry, (start["x"], start["y"], start["z"]), activator[0]
        )
        time.sleep(0.5)
        peers[0].send(12870, struct.pack(">qHH", activator[0]["id"], 0, 0))
        placement_packets = native.wait_all(peers, 12847, timeout=90)
        native.wait_all(peers, 13652, timeout=90)
        result["stages"].append("native_rift_entry_and_party_placement")
        if endurance:
            # Do all catalogue/gear observation before Ready can advance the
            # first native turn or enqueue its marker packets.
            args.phase = "battle"
            args.stop_after_defeats = args.battle_stop_after_defeats
            args.stop_after_wave = None
            for owner in owners:
                weapon = native.observe(
                    args,
                    dict(
                        operation="weapon",
                        wave=args.wave,
                        account_id=owner["account_id"],
                        character_id=owner["character"]["id"],
                        reference=args.weapon_reference,
                        require_equipped=True,
                    ),
                )
                owner.update(
                    weapon_uid=weapon["uid"],
                    weapon_ap_cost=weapon["ap_cost"],
                    weapon_minimum_range=weapon["minimum_range"],
                    weapon_maximum_range=weapon["maximum_range"],
                )
                verified_equipment = []
                for item in loadout["equipment"]:
                    verified_equipment.append(
                        native.observe(
                            args,
                            dict(
                                operation="equipment",
                                wave=args.wave,
                                account_id=owner["account_id"],
                                character_id=owner["character"]["id"],
                                reference=item["reference"],
                                slot=item["slot"],
                                require_equipped=True,
                            ),
                        )
                    )
                result.setdefault("existing_loadouts", []).append(
                    {
                        "character_id": owner["character"]["id"],
                        "weapon": weapon,
                        "equipment": verified_equipment,
                    }
                )
            result["stages"].append("same_six_owner_equipment_verified_before_ready")
        for peer in peers:
            peer.send(12523, b"\x01")
        ready_packets = native.wait_all(peers, 13482, timeout=90)
        result["ready_packets"] = [body[:24].hex() for _, body in ready_packets]
        state = snapshot(store, owners)
        run = state["run"]
        if (
            run is None
            or run["fight_id"] in (None, args.prior_fight_id)
            or run["status"] != "running"
            or run["defeated_monsters"] != 0
            or run["completed_waves"] != 0
        ):
            raise ValueError("Ready did not create a fresh zero-defeat Rift run")
        fight_id = run["fight_id"]
        result["fight_id"] = fight_id
        result["entered"] = snapshot(store, owners, fight_id)
        persist(args, result)
        result["stages"].append("new_fight_native_ready_zero_defeats")

        if endurance:
            geometry = native.observe(
                args,
                dict(operation="geometry", wave=args.wave, map_id=catalog["map_id"]),
            )
            result["native_endurance"] = {"status": "RUNNING", "fight_id": fight_id}
            persist(args, result)
            native.battle(
                args, peers, owners, geometry, fight_id, ready_packets[0][1], result
            )
            result["before_surrender"] = snapshot(store, owners, fight_id)
            result["before_surrender"]["artifact_trace"] = artifact_retirement_trace(
                store, fight_id, owners[0]["character"]["id"]
            )
            durable_kills = result["before_surrender"]["run"]["defeated_monsters"]
            checkpoint_dead = result["before_surrender"]["artifact_trace"][
                "checkpoint_dead_original_actor_ids"
            ]
            if (
                not result.get("stop_after_defeats_reached")
                or durable_kills < args.battle_stop_after_defeats
            ):
                raise ValueError(
                    "Native endurance did not reach its durable defeated-monster threshold"
                )
            result["stages"].append(
                "same_six_owner_native_endurance_stopped_at_durable_boundary"
            )
            result["native_endurance"] = {
                "status": "PASS_THRESHOLD",
                "fight_id": fight_id,
                "durable_completed_original_kills": durable_kills,
                "checkpoint_dead_original_actor_ids": checkpoint_dead,
                "stop_receipt": result.get("stop_receipt"),
                "artifact_trace": result["before_surrender"]["artifact_trace"],
            }
            persist(args, result)

        returns = []
        for owner, peer in zip(owners, peers):
            request_at = peer.send(13952)
            _, terminal = peer.wait(12238, since=request_at, timeout=90)
            flag = reconnect.callback_flag(terminal, owner["character"]["id"])
            body = struct.pack(">iB", fight_id, flag)
            peer.send(12925, body)
            peer.send(33, b"reentry-return-proof")
            peer.wait(
                23,
                predicate=lambda value: value == b"\x01reentry-return-proof",
                timeout=30,
            )
            returns.append(body.hex())
        result["return_callbacks"] = returns
        if endurance and len(returns) != len(owners):
            raise ValueError(
                "Native endurance did not receive every owner return callback"
            )
        result["surrendered"] = snapshot(store, owners, fight_id)
        if result["surrendered"]["run"]["status"] != "closed":
            raise ValueError("Last native surrender did not close the new fight")
        if endurance:
            if result["surrendered"]["fight"]["status"] != "aborted":
                raise ValueError(
                    "Native owner withdrawal did not abort the active PvE fight"
                )
            if (
                result["surrendered"]["run"]["defeated_monsters"]
                != result["before_surrender"]["run"]["defeated_monsters"]
            ):
                raise ValueError(
                    "Native surrender changed the durable defeated-monster counter"
                )
            expected_ids = sorted(owner["character"]["id"] for owner in owners)
            for table in ("fight_rewards", "fight_reward_policy_receipts"):
                if (
                    sorted(
                        row["character_id"]
                        for row in result["surrendered"]["receipts"][table]
                    )
                    != expected_ids
                ):
                    raise ValueError(
                        "Native endurance settlement lacks exactly one owner receipt in "
                        + table
                    )
            settlement = result["surrendered"]["receipts"]["rift_settlement_receipts"]
            # Sequential native withdrawals close the Rift through the PvE
            # abort path. Earned rewards are evidenced by per-owner policy
            # receipts; this path intentionally does not create a global
            # rift_settlement_receipts row.
            if settlement:
                raise ValueError(
                    "Native owner-withdrawal path unexpectedly wrote a global Rift settlement receipt"
                )
            withdrawals = result["surrendered"]["receipts"]["combat_pve_withdrawals"]
            if len(withdrawals) != len(owners) - 1:
                raise ValueError(
                    "Sequential native close should record one withdrawal per owner before the terminal owner"
                )
            expected_dead_ids = result["before_surrender"]["artifact_trace"][
                "checkpoint_dead_original_actor_ids"
            ]
            if any(
                row["defeated_actor_ids"] != expected_dead_ids
                for row in result["surrendered"]["receipts"][
                    "fight_reward_policy_receipts"
                ]
            ):
                raise ValueError(
                    "Settlement defeated actor IDs differ from the pre-surrender native checkpoint"
                )
            if not any(
                row["xp"] > 0 or row["kamas"] > 0
                for row in result["surrendered"]["receipts"][
                    "fight_reward_policy_receipts"
                ]
            ):
                raise ValueError("Native endurance settlement awarded no earned reward")
            result["stages"].append(
                "earned_reward_receipts_for_same_six_after_native_surrender"
            )
        else:
            if result["surrendered"]["run"]["defeated_monsters"] != 0:
                raise ValueError("New Rift unexpectedly recorded a defeated monster")
            if result["surrendered"]["progression"] != before["progression"]:
                raise ValueError("Zero-defeat re-entry changed XP")
            if result["surrendered"]["wallets"] != before["wallets"]:
                raise ValueError("Zero-defeat re-entry changed wallets")
        receipts = result["surrendered"]["receipts"]
        if not endurance:
            for table in (
                "fight_rewards",
                "fight_drop_awards",
                "rift_item_reward_receipts",
            ):
                if receipts[table]:
                    raise ValueError("Zero-defeat re-entry granted rewards: " + table)
            if any(
                row["xp"] or row["kamas"]
                for row in receipts["fight_reward_policy_receipts"]
            ):
                raise ValueError("Zero-defeat policy receipt granted XP or kamas")
            result["stages"].append("six_native_surrenders_without_rewards_or_defeats")

        reconnect.leave_finished_rift_through_portals(args, owners, peers)
        result["exterior"] = snapshot(store, owners, fight_id)
        if any(
            row["map_id"] != 527 or row["instance_id"] != 0
            for row in result["exterior"]["characters"]
        ):
            raise ValueError("Native exit did not return every owner to map 527")
        if result["exterior"]["active_memberships"]:
            raise ValueError("Native exit left an active combat membership")
        expected_progression = (
            result["surrendered"]["progression"] if endurance else before["progression"]
        )
        expected_wallets = (
            result["surrendered"]["wallets"] if endurance else before["wallets"]
        )
        if (
            result["exterior"]["progression"] != expected_progression
            or result["exterior"]["wallets"] != expected_wallets
        ):
            raise ValueError("Native exit changed XP or wallet after Rift settlement")
        if result["exterior"].get("receipts") != result["surrendered"].get("receipts"):
            raise ValueError("Native portal exit changed reward or withdrawal receipts")
        if (
            result["exterior"]["companies"] != before["companies"]
            or result["exterior"]["party"] != before["party"]
        ):
            raise ValueError("Native exit changed party/company ownership")
        expected_selection = sorted(
            (owner["account_id"], owner["character"]["id"]) for owner in owners
        )
        if (
            sorted(
                (row["account_id"], row["character_id"])
                for row in result["exterior"]["selected"]
            )
            != expected_selection
        ):
            raise ValueError("Native exit changed the selected six characters")
        result["stages"].append("native_portal_exit_company_and_party_preserved")
        # Prove a fresh native login/character selection after the portal
        # transition, not only that the prior selected-session rows remain.
        for peer in peers:
            peer.close()
        peers.clear()
        native.connect_existing_scene(args, owners, peers)
        result["post_portal_selection"] = snapshot(store, owners, fight_id)
        if (
            sorted(
                (row["account_id"], row["character_id"])
                for row in result["post_portal_selection"]["sessions"]
            )
            != expected_selection
        ):
            raise ValueError(
                "Fresh post-portal login did not select the same six characters"
            )
        expected_exterior_positions = [
            {key: row[key] for key in ("id", "map_id", "instance_id", "x", "y", "z")}
            for row in result["exterior"]["characters"]
        ]
        actual_post_portal_positions = [
            {key: row[key] for key in ("id", "map_id", "instance_id", "x", "y", "z")}
            for row in result["post_portal_selection"]["characters"]
        ]
        if actual_post_portal_positions != expected_exterior_positions:
            raise ValueError("Fresh post-portal selection changed exterior positions")
        if result["post_portal_selection"]["active_memberships"]:
            raise ValueError(
                "Fresh post-portal selection restored an active combat membership"
            )
        for field in (
            "run",
            "fight",
            "companies",
            "party",
            "progression",
            "wallets",
            "receipts",
        ):
            if result["post_portal_selection"].get(field) != result["exterior"].get(
                field
            ):
                raise ValueError(
                    "Fresh post-portal selection changed durable state: " + field
                )
        result["stages"].append(
            "fresh_native_selection_after_portal_preserved_rewards_and_membership"
        )
        if endurance:
            result["stages"].append(
                "natural_artifact_and_317553_to_317554_presence_recorded_without_seed_control"
            )
        result["status"] = "PASS"
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["status"] = "FAIL"
    finally:
        result["observer_metrics"] = args.observer_metrics
        persist(args, result)
        for peer in peers:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
