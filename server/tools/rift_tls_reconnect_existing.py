"""Reconnect an existing local QA cohort, then surrender through native packets."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import rift_tls_party_e2e as native


def observe(args, identities):
    script = r"""
import json,os,sys
from wakfu_server.store import Store
r=json.load(sys.stdin)
s=Store(os.environ['WAKFU_DATABASE_URL'],password_file=os.environ.get('WAKFU_DATABASE_PASSWORD_FILE'))
try:
 with s.connection() as db:
  owners=db.execute('SELECT id,username FROM accounts WHERE id=ANY(%s)',(r['accounts'],)).fetchall()
  if len(owners)!=len(r['accounts']) or any(not x['username'].startswith('rfnetqa_') for x in owners):raise ValueError('QA accounts only')
  run=db.execute('SELECT instance_id,fight_id,wave_definition_id,status,wave,completed_waves,defeated_monsters,members FROM rift_instances WHERE fight_id=%s',(r['fight'],)).fetchone()
  if run is None or sorted(run['members'])!=sorted(r['characters']):raise ValueError('Existing fight differs from exact QA roster')
  cp=db.execute('SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s',(r['fight'],)).fetchone()['snapshot']
  result=dict(run=run,phase=cp['phase'],turn=cp['turn_id'],actor_ids=sorted(cp['actors']),runtime=cp.get('runtime'),characters=db.execute('SELECT id,map_id,instance_id,hp,level FROM characters WHERE id=ANY(%s) ORDER BY id',(r['characters'],)).fetchall(),progression=db.execute('SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s) ORDER BY character_id',(r['characters'],)).fetchall(),wallets=db.execute('SELECT account_id,kamas FROM account_wallets WHERE account_id=ANY(%s) ORDER BY account_id',(r['accounts'],)).fetchall())
  for table in ('fight_rewards','fight_reward_policy_receipts','fight_drop_awards','combat_pve_withdrawals'):
   result[table]=db.execute('SELECT character_id,count(*) AS count FROM '+table+' WHERE fight_id=%s GROUP BY character_id ORDER BY character_id',(r['fight'],)).fetchall()
  result['companies']=db.execute('SELECT account_id,leader_id FROM account_hero_rosters WHERE account_id=ANY(%s) ORDER BY account_id',(r['accounts'],)).fetchall()
  result['selected']=db.execute('SELECT account_id,character_id FROM sessions WHERE account_id=ANY(%s) ORDER BY account_id',(r['accounts'],)).fetchall()
  result['active_memberships']=db.execute("SELECT p.character_id,p.fight_id FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=ANY(%s) AND f.status IN ('placement','active') AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id)",(r['characters'],)).fetchall()
  print(json.dumps(result,default=str))
finally:s.close()
"""
    request = dict(
        fight=args.fight_id,
        accounts=[x["account_id"] for x in identities],
        characters=[x["character"]["id"] for x in identities],
    )
    result = subprocess.run(
        ["docker", "exec", "-i", args.container, "python", "-c", script],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def callback_flag(body, character_id):
    offset = 13
    cohorts = []
    for _ in range(3):
        count = struct.unpack_from(">b", body, offset)[0]
        offset += 1
        if count < 0:
            raise ValueError("Invalid terminal roster count")
        cohorts.append(struct.unpack_from(">" + "q" * count, body, offset))
        offset += count * 8
    return int(character_id not in cohorts[1])


def leave_finished_rift_through_portals(args, owners, peers):
    """Use each character's published native exit from a terminal Rift."""
    from tools import probe_rift_artifact_journey as journey
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.generic_transports import source as transport_source
    from wakfu_server.store import Store

    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
        if catalog["map_id"] != 1314:
            raise ValueError("Published Rift exit map differs from the QA fight")
        exit_object = next(
            row for row in catalog["objects"] if row.get("type") == "Teleporter"
        )
        exit_source = transport_source(catalog["map_id"], exit_object["id"])
        exits = [
            row
            for row in exit_source["destinations"]
            if row["map_id"] != catalog["map_id"]
        ]
        if len(exits) != 1:
            raise ValueError("Rift exit destination is not unique")
        destination = exits[0]
        geometry = published_geometry(catalog["map_id"])
        for owner, peer in zip(owners, peers):
            character_id = owner["character"]["id"]
            current = store.character(owner["account_id"], character_id)
            if (
                current["instance_id"] == 0
                and current["map_id"] == destination["map_id"]
            ):
                continue
            if current["map_id"] != catalog["map_id"] or current["instance_id"] == 0:
                raise ValueError("Won Rift owner is not in its original instance")
            target = journey.walk_to_native_exit(
                peer,
                geometry,
                tuple(current[key] for key in ("x", "y", "z")),
                exit_source,
            )
            if target != tuple(current[key] for key in ("x", "y", "z")):
                # The native movement handler intentionally does not echo the
                # path to its owner; the client renders its own request. Wait
                # for the durable position that the same handler commits.
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    moved = store.character(owner["account_id"], character_id)
                    if tuple(moved[key] for key in ("x", "y", "z")) == target:
                        break
                    time.sleep(0.1)
                else:
                    raise TimeoutError(
                        "Native movement to the Rift exit was not durable"
                    )
            sent = peer.send(
                12296,
                struct.pack(
                    ">qiBi", exit_source["id"], destination["destination_id"], 0, 2
                ),
            )
            peer.wait(13974, since=sent, timeout=60)
            peer.send(14689)
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--fight-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-existing-qa", action="store_true")
    parser.add_argument("--recover-closed", action="store_true")
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument(
        "--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1"
    )
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--container", default="wakfu-local-world-1")
    args = parser.parse_args()
    if not args.execute_existing_qa or not args.http_url.startswith(
        ("http://127.0.0.1:", "http://localhost:")
    ):
        parser.error("Explicit local existing-QA execution required")
    owners = json.loads(args.credentials.read_text())
    if len(owners) not in (4, 6) or any(
        not x["username"].startswith("rfnetqa_") for x in owners
    ):
        raise ValueError("Exactly four or six existing QA owners required")
    peers = []
    result = dict(
        status="FAIL", fight_id=args.fight_id, stages=[], official_client=False
    )
    try:
        before = observe(args, owners)
        result["before"] = before
        allowed_statuses = ("closed", "won") if args.recover_closed else ("running",)
        if before["run"]["status"] not in allowed_statuses:
            raise ValueError("Requested QA fight is no longer resumable")
        if (
            args.recover_closed
            and before["run"]["status"] == "won"
            and before["phase"] != "finished"
        ):
            raise ValueError("Won QA fight lacks a finished checkpoint")
        args.wave = before["run"]["wave_definition_id"]
        args.observer_metrics = []
        if args.recover_closed:
            native.connect_existing_scene(args, owners, peers)
        else:
            native.reconnect_owned_combat(args, owners, args.fight_id, peers=peers)
        if args.recover_closed:
            if before["run"]["status"] == "won":
                # The normal login no longer has a shared fight attached. Use
                # the original published teleporter to leave the won instance.
                leave_finished_rift_through_portals(args, owners, peers)
            else:
                for peer in peers:
                    peer.send(33, b"closed-recovery")
                    peer.wait(
                        23, predicate=lambda value: value == b"\x01closed-recovery"
                    )
                    if 12847 in peer.seen:
                        raise ValueError(
                            "Closed fight reattached during character selection"
                        )
                if any(row["instance_id"] != 0 for row in before["characters"]):
                    leave_finished_rift_through_portals(args, owners, peers)
            recovered = observe(args, owners)
            result["recovered"] = recovered
            if recovered["active_memberships"] or any(
                row["instance_id"] != 0 for row in recovered["characters"]
            ):
                raise ValueError(
                    "Closed Rift recovery left private membership or position"
                )
            for table in (
                "fight_rewards",
                "fight_reward_policy_receipts",
                "fight_drop_awards",
            ):
                if recovered[table] != before[table]:
                    raise ValueError(
                        "Closed Rift recovery changed earned reward receipts"
                    )
            for table in ("progression", "wallets"):
                if recovered[table] != before[table]:
                    raise ValueError("Closed Rift recovery changed " + table)
            if recovered["companies"] != before["companies"]:
                raise ValueError("Closed Rift recovery changed company ownership")
            expected = sorted(
                (owner["account_id"], owner["character"]["id"]) for owner in owners
            )
            if (
                sorted(
                    (row["account_id"], row["character_id"])
                    for row in recovered["selected"]
                )
                != expected
            ):
                raise ValueError("Closed Rift recovery changed selected characters")
            result["stages"].append(
                "terminal_rift_login_exterior_membership_company_rewards_once"
            )
            result["status"] = "PASS"
            return
        resumed_state = observe(args, owners)
        result["resumed"] = resumed_state
        if resumed_state["run"] != before["run"] or not set(before["actor_ids"]) <= set(
            resumed_state["actor_ids"]
        ):
            raise ValueError(
                "Reconnect changed earned wave progress or lost actor history"
            )
        result["stages"].append(
            f"same_{len(owners)}_owners_same_fight_native_resumption"
        )
        returns = []
        for owner, peer in zip(owners, peers):
            sent = peer.send(13952)
            _, terminal = peer.wait(12238, since=sent, timeout=60)
            flag = callback_flag(terminal, owner["character"]["id"])
            body = struct.pack(">iB", args.fight_id, flag)
            peer.send(12925, body)
            peer.send(33, b"return-proof")
            peer.wait(23, predicate=lambda value: value == b"\x01return-proof")
            returns.append(body)
        result["stages"].append(f"{len(owners)}_explicit_surrenders_and_native_returns")
        settled = observe(args, owners)
        result["settled"] = settled
        if settled["run"]["status"] in ("entered", "running"):
            raise ValueError("Last explicit surrender did not close the Rift")
        expected_ids = sorted(owner["character"]["id"] for owner in owners)
        for table in (
            "fight_rewards",
            "fight_reward_policy_receipts",
            "fight_drop_awards",
        ):
            if settled[table] != [
                dict(character_id=identity, count=1) for identity in expected_ids
            ]:
                raise ValueError("Missing or duplicate earned reward receipt: " + table)
        if settled["run"]["defeated_monsters"] != before["run"]["defeated_monsters"]:
            raise ValueError("Surrender changed defeated native history")
        for peer, body in zip(peers, returns):
            peer.send(12925, body)
            peer.send(33, b"replay-proof")
            peer.wait(23, predicate=lambda value: value == b"\x01replay-proof")
        replay = observe(args, owners)
        result["replayed_returns"] = replay
        for table in (
            "fight_rewards",
            "fight_reward_policy_receipts",
            "fight_drop_awards",
        ):
            if replay[table] != settled[table]:
                raise ValueError("Return replay duplicated rewards")
        for table in ("progression", "wallets"):
            if replay[table] != settled[table]:
                raise ValueError("Return replay duplicated " + table)
        result["stages"].append("reward_receipts_once_after_return_replay")
        result["status"] = "PASS"
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        for peer in peers:
            peer.close()
        result["peers"] = [dict(received=p.seen, sent=p.sent) for p in peers]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
