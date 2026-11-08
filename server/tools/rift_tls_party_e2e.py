"""Opt-in live Rift protocol scenarios on newly created QA accounts only.

The peer uses the real HTTP/dispatcher/World path. It does not replace the
official-client acceptance lane: packets are recorded, not rendered here.
No server restart, direct ticket minting, forged victory or player-state replay.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request

from protocol_codec import DIRECTIONS


def text(value):
    raw = value.encode()
    return struct.pack(">I", len(raw)) + raw


class Peer:
    def __init__(self, host, port):
        self.socket = ssl._create_unverified_context().wrap_socket(
            socket.create_connection((host, port), timeout=15),
            server_hostname="localhost",
        )
        self.socket.settimeout(0.1)
        self.io_lock = threading.Lock()
        self.tls = self.socket.version()
        self.events, self.pending = queue.Queue(), []
        self.closed = False
        self.failure = None
        self.seen, self.sent = [], []
        self.wait_metrics = []
        self.last_received_at = None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def exact(self, count):
        result = bytearray()
        while len(result) < count:
            try:
                with self.io_lock:
                    value = self.socket.recv(count - len(result))
            except TimeoutError:
                if self.closed:
                    raise EOFError("QA peer closed")
                time.sleep(0)
                continue
            if not value:
                raise EOFError("World closed the QA TLS connection")
            result.extend(value)
        return bytes(result)

    def _read(self):
        try:
            while not self.closed:
                size = struct.unpack(">I", self.exact(4))[0]
                if not 6 <= size <= 327670:
                    raise ValueError("Invalid native server frame length")
                packet = self.exact(size - 4)
                opcode = struct.unpack_from(">H", packet)[0]
                self.seen.append(opcode)
                self.events.put((opcode, packet[2:], time.monotonic()))
        except BaseException as error:
            if not self.closed:
                self.failure = error
                self.events.put((None, error, time.monotonic()))

    def send(self, opcode, body=b""):
        self.sent.append(opcode)
        with self.io_lock:
            self.socket.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)
        return time.monotonic()

    def wait(self, opcodes, timeout=45, *, since=None, predicate=None):
        started = time.monotonic()
        wanted = {opcodes} if isinstance(opcodes, int) else set(opcodes)
        for index, (opcode, body, received_at) in enumerate(self.pending):
            if (
                opcode in wanted
                and (since is None or received_at >= since)
                and (predicate is None or predicate(body))
            ):
                del self.pending[index]
                self._record_wait(wanted, opcode, started, received_at, since)
                return opcode, body
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                opcode, body, received_at = self.events.get(
                    timeout=max(0.01, until - time.monotonic())
                )
            except queue.Empty:
                break
            if opcode is None:
                raise body
            if (
                opcode in wanted
                and (since is None or received_at >= since)
                and (predicate is None or predicate(body))
            ):
                self._record_wait(wanted, opcode, started, received_at, since)
                return opcode, body
            self.pending.append((opcode, body, received_at))
        self.wait_metrics.append(
            {
                "wanted": sorted(wanted),
                "actual": None,
                "wait_ms": round((time.monotonic() - started) * 1000, 3),
                "timeout": True,
            }
        )
        raise TimeoutError(
            f"Missing native opcode {sorted(wanted)}; last={self.seen[-20:]}"
        )

    def _record_wait(self, wanted, opcode, started, received_at, since):
        self.last_received_at = received_at
        sample = {
            "wanted": sorted(wanted),
            "actual": opcode,
            "wait_ms": round((time.monotonic() - started) * 1000, 3),
            "queued_ms": round(max(0, (started - received_at) * 1000), 3),
        }
        if since is not None:
            sample["since_send_ms"] = round(max(0, (received_at - since) * 1000), 3)
        self.wait_metrics.append(sample)

    def close(self):
        self.closed = True
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        self.reader.join(timeout=1)


def post(args, path, value, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        args.http_url + path,
        data=json.dumps(value).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def ticket(args, token):
    peer = Peer(args.host, args.dispatcher_port)
    try:
        peer.send(574)
        public = peer.wait(400)[1]
        raw = token.encode()
        clear = struct.pack(">qB", struct.unpack_from(">q", public)[0], len(raw)) + raw
        with tempfile.TemporaryDirectory(prefix="rift-qa-auth-") as directory:
            key = Path(directory) / "public.der"
            key.write_bytes(public[8:])
            encrypted = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-encrypt",
                    "-pubin",
                    "-keyform",
                    "DER",
                    "-inkey",
                    str(key),
                    "-pkeyopt",
                    "rsa_padding_mode:pkcs1",
                ],
                input=clear,
                capture_output=True,
                check=True,
            ).stdout
        peer.send(584, struct.pack(">I", len(encrypted)) + encrypted)
        peer.wait(472)
        peer.send(402)
        peer.wait(453)
        peer.send(575, struct.pack(">iB", 10, 0))
        payload = peer.wait(466)[1]
        if payload[0] != 0:
            raise ValueError("Dispatcher rejected QA realm selection")
        size = struct.unpack_from(">I", payload, 1)[0]
        return payload[5 : 5 + size].decode()
    finally:
        peer.close()


def connect(args, owner, *, reconnect=False):
    login = post(args, "/login", {key: owner[key] for key in ("username", "password")})
    peer = Peer(args.host, args.world_port)
    peer.send(426, text(ticket(args, login["game_token"])) + text("rift-e2e-qa"))
    peer.wait(13873)
    character = owner["character"]
    peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
    if not reconnect:
        peer.wait(630)
        peer.wait(711)
        peer.send(12449)
        peer.wait(12436)
        peer.wait(711)
        peer.send(12449)
        peer.wait(711)
    return peer


def observe(args, request):
    """Use the existing World image for bounded source/DB observations/setup."""
    started = time.monotonic()
    script = r"""
import json,os,sys
from types import SimpleNamespace
from wakfu_server.store import Store
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.command_permissions import set_admin
def saved_movement_blocked(saved, actor_id):
 from wakfu_server.combat_qi_registry import NativeQIRegistry
 from wakfu_server.combat_qi_movement import movement_blocked_cells_from_registry
 if "native_pointer_checkpoint" in saved:
  raise ValueError("QA routes cannot reconstruct a canonical pointer QI owner")
 required=("native_qi_snapshot","native_qi_slots","native_qi_touched_cells","native_qi_byte_topology")
 if any(saved.get(name) is None for name in required):
  raise ValueError("QA routes require complete saved native QI topology")
 row=saved["actors"].get(str(actor_id))
 if row is None or type(row.get("physical_radius")) is not int:
  raise ValueError("QA route mover lacks saved native physical radius")
 actor=SimpleNamespace(id=actor_id,native_obstacle_id=row.get("native_obstacle_id"),physical_radius=row["physical_radius"])
 registry=NativeQIRegistry(saved["native_qi_snapshot"],saved["native_qi_slots"],touched_cells=saved["native_qi_touched_cells"],byte_topology=saved["native_qi_byte_topology"])
 return sorted(movement_blocked_cells_from_registry(registry,actor,set(map(tuple,saved["walkable"])),override=saved.get("native_qi_movement_override"),ignored=saved.get("native_qi_ignored_slots")))

request=json.load(sys.stdin)
store=Store(os.environ['WAKFU_DATABASE_URL'],password_file=os.environ.get('WAKFU_DATABASE_PASSWORD_FILE'))
try:
 with store.connection() as db:
  catalog=db.execute("SELECT value FROM settings WHERE name='rift_catalog'").fetchone()['value'][str(request['wave'])]
  if request['operation']=='catalog':
   print(json.dumps(catalog))
  elif request['operation']=='geometry':
   geometry=published_geometry(request['map_id'])
   print(json.dumps({'cells':sorted(geometry.cells),'edges':[[a,b] for a,rows in geometry.outgoing.items() for b in rows]}))
  elif request['operation']=='setup':
   account=db.execute('SELECT username FROM accounts WHERE id=%s',(request['account_id'],)).fetchone()
   if account is None or not account['username'].startswith('rfnetqa_'):
    raise ValueError('Only newly named transport QA accounts may be prepared')
   set_admin(store,request['account_id'],True,operator='rift-transport-e2e',reason='isolated QA account only')
   generation=store.begin_session(request['account_id'])
   store.select_character(request['account_id'],generation,request['character_id'])
   current=store.character(request['account_id'],request['character_id'],db)
   portal=catalog['entrances'][0]
   geometry=published_geometry(portal['map_id'])
   points=sorted((p for p in geometry.cells if max(abs(p[0]-portal['x']),abs(p[1]-portal['y']))<=2),key=lambda p:(abs(p[0]-portal['x'])+abs(p[1]-portal['y']),abs(p[2]-portal['z']),p))
   point=points[request['index']%len(points)]
   store.transition_map_in_transaction(db,request['account_id'],generation,request['character_id'],current,dict(map_id=portal['map_id'],instance_id=0,x=point[0],y=point[1],z=point[2]))
   print(json.dumps({'character_id':request['character_id'],'approach':point}))
  elif request['operation']=='weapon_guard':
   from wakfu_server.equipment import validate_sheet
   character=store.character(request['account_id'],request['character_id'],db)
   saved=character.get('builds',{}).get(character.get('active_build_index',0),{})
   equipped=validate_sheet(character,bytes.fromhex(saved.get('equipment','')),strict=False)
   selected=next((row for row in equipped if row['slot']==15),None)
   item=None if selected is None else db.execute('SELECT reference FROM inventory_items WHERE uid=%s AND character_id=%s',(selected['uid'],request['character_id'])).fetchone()
   if selected is not None and item is None: raise ValueError('Equipped weapon lacks its owned inventory unit')
   print(json.dumps({'reference':None if item is None else item['reference']}))
  elif request['operation'] in ('weapon','equipment'):
   from wakfu_server.combat_weapon import catalog
   from wakfu_server.equipment import validate_sheet
   rows=db.execute('SELECT uid FROM inventory_items WHERE character_id=%s AND reference=%s ORDER BY uid DESC LIMIT 1',(request['character_id'],request['reference'])).fetchall()
   if not rows: raise ValueError('QA weapon item was not durably created')
   character=store.character(request['account_id'],request['character_id'],db)
   saved=character.get('builds',{}).get(character.get('active_build_index',0),{})
   equipped=validate_sheet(character,bytes.fromhex(saved.get('equipment','')),strict=False)
   uid=rows[0]['uid']
   slot=request.get('slot',15)
   is_equipped=any(row['uid']==uid and row['slot']==slot for row in equipped)
   if request.get('require_equipped') and not is_equipped:
    raise ValueError('QA item UID did not equip in requested slot')
   result={'uid':uid,'equipped':is_equipped,'slot':slot,'hp':character['hp'],'max_hp':character['max_hp']}
   if request['operation']=='weapon':
    rule=catalog()[request['reference']]
    result.update(ap_cost=rule['ap_cost'],minimum_range=rule['native_cpF'],maximum_range=rule['native_cpG'])
   print(json.dumps(result))
  elif request['operation']=='state':
   ids=request['character_ids']
   characters=db.execute('SELECT id,account_id,level,map_id,instance_id,x,y,z,hp,max_hp FROM characters WHERE id=ANY(%s) ORDER BY id',(ids,)).fetchall()
   runs=db.execute('SELECT instance_id,fight_id,status,wave,completed_waves,defeated_monsters,members FROM rift_instances WHERE owner_character_id=%s ORDER BY instance_id DESC LIMIT 1',(ids[0],)).fetchall()
   result={'characters':characters,'runs':runs}
   if runs and runs[0]['fight_id']:
    result['fight']=db.execute('SELECT status FROM combat_fights WHERE id=%s',(runs[0]['fight_id'],)).fetchone()
    result['members']=db.execute('SELECT account_id,character_id,team FROM combat_fight_participants WHERE fight_id=%s ORDER BY character_id',(runs[0]['fight_id'],)).fetchall()
   print(json.dumps(result,default=str))
  elif request['operation']=='combat':
   row=db.execute('SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s',(request['fight_id'],)).fetchone()
   if row is None: raise ValueError('Missing actual fight checkpoint')
   run=db.execute('SELECT instance_id,status,wave,completed_waves,defeated_monsters FROM rift_instances WHERE fight_id=%s ORDER BY instance_id DESC LIMIT 1',(request['fight_id'],)).fetchone()
   saved=row['snapshot']
   schema=saved.get('checkpoint_schema')
   compact=schema=='wakemu.fight-checkpoint.v2'
   if schema is not None and not compact:
    raise ValueError('Unsupported native QA checkpoint schema')
   if compact:
    required=('id','phase','turn_id','turn_index','order','actors','walkable','edges','native_qi_snapshot','native_qi_slots','native_qi_touched_cells','native_qi_byte_topology','native_effect_areas','native_timeline_removed_count','native_global_pv_collections','native_qi_ignored_slots','native_qi_movement_override','native_los_ignored_affiliations','native_ordinary_qi_retirements','native_rift_birth_fence')
    missing=[name for name in required if name not in saved]
    if missing: raise ValueError('Incomplete native QA observation projection: '+','.join(missing))
    if not isinstance(saved['native_ordinary_qi_retirements'],dict): raise ValueError('Missing native ordinary retirement proof map')
    if saved['native_rift_birth_fence'] is not None and not isinstance(saved['native_rift_birth_fence'],dict): raise ValueError('Missing native birth-fence proof')
    if not isinstance(saved['native_effect_areas'],dict): raise ValueError('Missing explicit native healing-orb projection')
    if type(saved['native_timeline_removed_count']) is not int: raise ValueError('Missing native timeline retirement count')
    if not isinstance(saved['native_global_pv_collections'],dict) or not isinstance(saved['native_global_pv_collections'].get('fighter_status'),dict): raise ValueError('Missing native fighter life projection')
    if saved.get('rift_wave_state') is not None and 'native_wave_entries' not in saved['rift_wave_state']: raise ValueError('Missing current native wave-entry projection')
    for actor in saved['actors'].values():
     if actor.get('hp',0)>0 and any(name not in actor for name in ('physical_radius','native_obstacle_id','native_los_height')): raise ValueError('Missing live actor native spatial facts')
   fields=('id','phase','winner','turn_id','turn_index','order','native_timeline_round','rift_wave_state','runtime','native_rift_birth_fence')
   result={name:saved.get(name) for name in fields}
   result['checkpoint_schema']=schema
   result['artifact_lineage_observation']='UNKNOWN_FULL_SNAPSHOT_REQUIRED' if compact else 'FULL_SNAPSHOT_AVAILABLE'
   result['walkable']=saved.get('walkable')
   result['edges']=saved.get('edges')
   order=saved.get('order') or []
   index=saved.get('turn_index')
   result['current_actor_id']=order[index % len(order)] if order and isinstance(index,int) else None
   result['actors']={identity:{name:actor.get(name) for name in ('id','team','controlled','owner_id','position','hp','max_hp','ap','mp','turn_count','native_obstacle_id','native_los_height','physical_radius','native_ordinary_qi_retirement','native_death_status')} for identity,actor in saved['actors'].items()}
   result['native_ordinary_qi_retirements']=saved['native_ordinary_qi_retirements'] if compact else saved.get('native_ordinary_qi_retirements',{})
   result['native_fighter_status']=(saved.get('native_global_pv_collections') or {}).get('fighter_status',{})
   mover_id=request.get('visibility_actor_id',result['current_actor_id'])
   mover=result['actors'].get(str(mover_id))
   result['movement_actor_id']=None
   if mover is not None and mover['controlled'] and mover['hp']>0:
    result['movement_actor_id']=mover_id
    result['movement_blocked_cells']=saved_movement_blocked(saved,mover_id)
   result['healing_orbs']=[{name:area.get(name) for name in ('uid','reference','cell','native_area_contract','native_qq_bhi','native_qq_guard_source','executing','remaining_activations')} for area in saved.get('native_effect_areas',{}).values() if area.get('reference')==1574 and area.get('native_area_contract')=='faY' and area.get('native_qq_bhi') is False and not area.get('executing') and area.get('remaining_activations',-1)!=0]
   if request.get('visibility_actor_id') is not None:
    from wakfu_server.combat_los import authoritative_visible
    attacker=result['actors'].get(str(request['visibility_actor_id']))
    if attacker is None: raise ValueError('LOS source is missing from checkpoint')
    live={identity:row for identity,row in result['actors'].items() if row['hp']>0}
    actors={int(identity):SimpleNamespace(id=int(identity),hp=row['hp'],position=tuple(row['position']),native_obstacle_id=row['native_obstacle_id'],native_los_height=row['native_los_height']) for identity,row in live.items()}
    fight=SimpleNamespace(actors=actors,walkable=set(map(tuple,saved['walkable'])),native_los_ignored_affiliations=frozenset(saved.get('native_los_ignored_affiliations',())))
    attacker_id=int(request['visibility_actor_id'])
    source_rows=request.get('visibility_sources') or [attacker['position']]
    targets=[(int(identity),tuple(row['position'])) for identity,row in live.items() if row['team']!=attacker['team']]
    result['native_visibility']={}
    for source in source_rows:
     previous=actors[attacker_id].position
     actors[attacker_id].position=tuple(source)
     key=','.join(map(str,source))
     footprints={actor.id:{actor.position[:2]} for actor in actors.values() if actor.hp>0}
     result['native_visibility'][key]={str(identity):authoritative_visible(int(catalog['map_id']),source,target,fight,blocking_footprints=footprints) for identity,target in targets if request.get('visibility_minimum_range',0)<=abs(source[0]-target[0])+abs(source[1]-target[1])<=request.get('visibility_maximum_range',1000)}
     actors[attacker_id].position=previous
   if request.get('visibility_actor_id') is not None:
    from wakfu_server.combat_los import static_visible
    attacker=result['actors'].get(str(request['visibility_actor_id']))
    if attacker is None: raise ValueError('LOS source is missing from checkpoint')
    map_id=int(catalog['map_id'])
    source=attacker['position']
    result['native_static_visibility']={}
    for identity,target in result['actors'].items():
     if target['team'] == attacker['team'] or target['hp'] <= 0: continue
     result['native_static_visibility'][identity]=static_visible(map_id,source,target['position'])
   result['durable_rift']=None if run is None else dict(run)
   result['native_timeline_removed_count']=saved['native_timeline_removed_count'] if compact else len(saved.get('native_timeline_removed',()))
   slots=saved.get('native_qi_slots')
   result['native_qi_occupied_count']=None if slots is None else sum(slot is not None for slot in slots)
   print(json.dumps(result,default=str))
finally:store.close()
"""
    command = [
        "docker",
        "exec",
        "-i",
        "-e",
        "PYTHONPATH=/app",
        args.container,
        "python3",
        "-c",
        script,
    ]
    result = subprocess.run(
        command, input=json.dumps(request), capture_output=True, text=True, timeout=45
    )
    if result.returncode:
        raise RuntimeError("QA source observer failed: " + result.stderr[-1800:])
    observation = json.loads(result.stdout)
    args.observer_metrics.append(
        {
            "operation": request["operation"],
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }
    )
    return observation


def wait_all(peers, opcodes, *, timeout=90, since=None, predicate=None):
    """Wait for a native event on each real peer before advancing the cohort."""
    return [
        peer.wait(
            opcodes,
            timeout=timeout,
            since=since[index] if isinstance(since, (tuple, list)) else since,
            predicate=predicate,
        )
        for index, peer in enumerate(peers)
    ]


def summarize(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "total_ms": 0.0, "max_ms": 0.0}
    return {
        "count": len(values),
        "total_ms": round(sum(values), 3),
        "mean_ms": round(sum(values) / len(values), 3),
        "max_ms": round(values[-1], 3),
        "p95_ms": round(values[min(len(values) - 1, int(len(values) * 0.95))], 3),
    }


def write_progress(args, result):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, default=str) + "\n")
    os.replace(temporary, args.output)


def walk(peer, geometry, start, target):
    goals = {
        tuple(cell)
        for cell in geometry["cells"]
        if max(abs(cell[0] - target["x"]), abs(cell[1] - target["y"])) <= 2
        and abs(cell[2] - target["z"]) <= 2
    }
    outgoing = {}
    for a, b in geometry["edges"]:
        outgoing.setdefault(tuple(a), []).append(tuple(b))
    pending, previous = deque([tuple(start)]), {tuple(start): None}
    while pending:
        point = pending.popleft()
        if point in goals:
            route = []
            while previous[point] is not None:
                route.append(point)
                point = previous[point]
            route.reverse()
            break
        for point_b in outgoing.get(point, ()):
            if point_b not in previous:
                previous[point_b] = point
                pending.append(point_b)
    else:
        raise ValueError("No original native route to the Rift activator")
    directions = {(x, y): key for key, (_, x, y) in DIRECTIONS.items()}
    if route:
        steps, point = bytearray(), tuple(start)
        for end in route:
            dx, dy, dz = end[0] - point[0], end[1] - point[1], end[2] - point[2]
            if not -16 <= dz <= 15:
                raise ValueError("Native walk altitude exceeds packet bound")
            steps.append((directions[(dx, dy)] << 5) | (dz & 31))
            point = end
        peer.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + steps)
    return route[-1] if route else tuple(start)


class NativeActionRejected(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__("Native weapon request rejected: " + reason)


def native_console_rejection(body):
    if not body:
        return None
    size = body[0]
    offset = 1 + size + 11
    if len(body) < offset + 2 or body[1 : 1 + size] != b"Consola local":
        return None
    text_size = struct.unpack_from(">H", body, offset)[0]
    if len(body) != offset + 2 + text_size:
        return None
    return body[offset + 2 :].decode("utf-8", errors="replace")


def wait_weapon_action(
    peers, owner_peer, fight_id, actor_id, reference, since, result, *, timeout=120
):
    def accepted(body):
        return (
            len(body) >= 24
            and struct.unpack_from(">i", body)[0] == fight_id
            and struct.unpack_from(">q", body, 12)[0] == actor_id
            and struct.unpack_from(">i", body, 20)[0] == reference
        )

    opcode, body = owner_peer.wait(
        {13509, 674},
        timeout=timeout,
        since=since,
        predicate=lambda value: accepted(value)
        or native_console_rejection(value) is not None,
    )
    if opcode == 674:
        reason = native_console_rejection(body)
        result.setdefault("native_rejections", []).append(
            dict(opcode=12889, fight_id=fight_id, actor_id=actor_id, reason=reason)
        )
        raise NativeActionRejected(reason)
    wait_all(
        [peer for peer in peers if peer is not owner_peer],
        {13509},
        timeout=timeout,
        since=since,
        predicate=accepted,
    )


def visibility_for_target(checkpoint, target_id):
    def visible(source, _target=None):
        return (
            checkpoint["native_visibility"]
            .get(",".join(map(str, source)), {})
            .get(str(target_id), False)
        )

    return visible


def choose_combat_target(options):
    """Choose only among targets whose native route/range/LOS checks passed.

    Each option is ``(target_rank, route, target)`` where target_rank is
    ``(current_wave_priority, checkpoint_insertion_index)``. The ordering
    favors the current wave, then the shortest route, then native insertion
    order, and finally actor id for deterministic ties.
    """
    if not options:
        return None
    return min(
        options,
        key=lambda option: (
            option[0][0],
            len(option[1]),
            option[0][1],
            option[2]["id"],
        ),
    )


def combat_route(
    geometry,
    current,
    target,
    blocked,
    maximum,
    minimum_range=1,
    maximum_range=1,
    visible=None,
):
    outgoing = {}
    for a, b in geometry["edges"]:
        outgoing.setdefault(tuple(a), []).append(tuple(b))
    queue_, previous = deque([tuple(current)]), {tuple(current): None}
    goal = None
    while queue_:
        position = queue_.popleft()
        distance = abs(position[0] - target[0]) + abs(position[1] - target[1])
        if minimum_range <= distance <= maximum_range and (
            visible is None or visible(position, target)
        ):
            goal = position
            break
        for destination in outgoing.get(position, ()):
            if destination not in previous and destination not in blocked:
                previous[destination] = position
                queue_.append(destination)
    if goal is None:
        return []
    route = []
    while previous[goal] is not None:
        route.append(goal)
        goal = previous[goal]
    return list(reversed(route))[:maximum]


def route_blocked_cells(checkpoint, actor_id):
    if (
        checkpoint.get("movement_actor_id") != actor_id
        or "movement_blocked_cells" not in checkpoint
    ):
        raise ValueError("QA route lacks actor-specific native passability")
    return {tuple(cell) for cell in checkpoint["movement_blocked_cells"]}


def healing_orb_route(checkpoint, geometry, actor_id):
    actor = checkpoint["actors"][str(actor_id)]
    if (
        not actor_owns_current_turn(checkpoint, actor_id)
        or actor["mp"] <= 0
        or not actor.get("max_hp")
        or actor["hp"] >= actor["max_hp"] * 0.7
    ):
        return []
    goals = {
        tuple(row["cell"])
        for row in checkpoint.get("healing_orbs", ())
        if row.get("reference") == 1574
        and row.get("native_area_contract") == "faY"
        and row.get("native_qq_bhi") is False
        and not row.get("executing")
        and row.get("remaining_activations", -1) != 0
    }
    blocked = route_blocked_cells(checkpoint, actor_id)
    geometry = fight_geometry(checkpoint, geometry)
    edges = {}
    for source, target in geometry["edges"]:
        edges.setdefault(tuple(source), []).append(tuple(target))
    origin = tuple(actor["position"])
    search_limit = (
        len(geometry["cells"]) if actor["hp"] < actor["max_hp"] * 0.3 else actor["mp"]
    )
    pending, seen = deque([(origin, [])]), {origin}
    while pending:
        position, route = pending.popleft()
        if route and position in goals:
            return route[: actor["mp"]]
        if len(route) >= search_limit:
            continue
        for target in edges.get(position, ()):
            if target not in seen and target not in blocked:
                seen.add(target)
                pending.append((target, route + [target]))
    return []


def wait_movement_action(peer, fight_id, actor_id, sent_at, *, timeout=120):
    """Accept movement only from its native action, never from a batch flush."""
    opcode, body = peer.wait({13624, 13887}, since=sent_at, timeout=timeout)
    if opcode == 13887:
        if len(body) != struct.calcsize(">iqiih"):
            raise ValueError("Malformed native movement correction")
        actual_fight, actual_actor, x, y, z = struct.unpack(">iqiih", body)
        if (actual_fight, actual_actor) != (fight_id, actor_id):
            raise ValueError("Native movement correction identity mismatch")
        return {"accepted": False, "opcode": opcode, "position": [x, y, z]}
    if len(body) < 42 or (len(body) - 22) % 10:
        raise ValueError("Malformed native movement action")
    actual_fight, _, _, actual_actor, _, _ = struct.unpack_from(">iiiqBB", body)
    if (actual_fight, actual_actor) != (fight_id, actor_id):
        raise ValueError("Native movement action identity mismatch")
    return {"accepted": True, "opcode": opcode}


def seek_healing_orb(args, peer, checkpoint, geometry, fight_id, actor_id):
    route = healing_orb_route(checkpoint, geometry, actor_id)
    if not route:
        return checkpoint, None, None
    sent = peer.send(
        12161,
        struct.pack(">q", actor_id)
        + b"".join(struct.pack(">iih", *point) for point in route),
    )
    movement = wait_movement_action(
        peer, fight_id, actor_id, sent, timeout=getattr(args, "action_timeout", 120)
    )
    # Contact effects may heal, consume MP, kill or advance the current actor.
    # Only the newly committed state can authorize the following attack.
    return (
        observe(args, dict(operation="combat", wave=args.wave, fight_id=fight_id)),
        sent,
        movement,
    )


def ranged_visibility_sources(
    geometry, targets, occupied, minimum_range, maximum_range
):
    """Bound native LOS probes to unoccupied cells that could be a weapon cast."""
    return [
        tuple(cell)
        for cell in geometry["cells"]
        if tuple(cell) not in occupied
        and any(
            minimum_range
            <= abs(cell[0] - target[0]) + abs(cell[1] - target[1])
            <= maximum_range
            for target in targets
        )
    ]


def fight_geometry(checkpoint, fallback):
    cells = checkpoint.get("walkable")
    edges = checkpoint.get("edges")
    if not cells or not edges:
        return fallback
    permitted = {tuple(cell) for cell in cells}
    return {
        "cells": [list(cell) for cell in permitted],
        "edges": [
            [list(a), list(b)]
            for a, b in edges
            if tuple(a) in permitted and tuple(b) in permitted
        ],
    }


def combat_view(
    args, geometry, fight_id, actor_id, minimum_range, maximum_range, *, checkpoint=None
):
    if checkpoint is None:
        checkpoint = observe(
            args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
        )
    actor = checkpoint["actors"].get(str(actor_id))
    if actor is None or actor["hp"] <= 0:
        return checkpoint
    geometry = fight_geometry(checkpoint, geometry)
    targets = [
        row["position"]
        for row in checkpoint["actors"].values()
        if row["team"] != actor["team"] and row["hp"] > 0
    ]
    # Keep the existing LOS source uniqueness restriction. Native movement
    # override can permit an occupied cell; this observer does not certify LOS
    # from overlapping actors or change its existing blocker semantics.
    occupied = route_blocked_cells(checkpoint, actor_id) | {
        tuple(row["position"])
        for row in checkpoint["actors"].values()
        if row["id"] != actor_id and row["hp"] > 0
    }
    sources = ranged_visibility_sources(
        geometry, targets, occupied, minimum_range, maximum_range
    )
    if tuple(actor["position"]) not in sources:
        sources.append(tuple(actor["position"]))
    return observe(
        args,
        dict(
            operation="combat",
            wave=args.wave,
            fight_id=fight_id,
            visibility_actor_id=actor_id,
            visibility_sources=sources,
            visibility_minimum_range=minimum_range,
            visibility_maximum_range=maximum_range,
        ),
    )


def stop_at_durable_boundary(args, checkpoint, result):
    wave_state = checkpoint.get("rift_wave_state") or {}
    durable = checkpoint.get("durable_rift") or {}
    if (
        checkpoint.get("phase") != "active"
        or wave_state.get("pending_wave") is not None
        or (checkpoint.get("runtime") or {}).get("awaiting_ack") is not None
    ):
        return False
    defeated = durable.get("defeated_monsters") or 0
    stop_by_wave = (
        args.stop_after_wave is not None
        and wave_state.get("wave", 0) >= args.stop_after_wave
    )
    stop_by_defeats = (
        args.stop_after_defeats is not None and defeated >= args.stop_after_defeats
    )
    sample = {
        "turn_id": checkpoint.get("turn_id"),
        "wave": wave_state.get("wave"),
        "completed_waves": durable.get("completed_waves"),
        "defeated_monsters": defeated,
        "actor_history_count": len(checkpoint.get("actors", {})),
        "dead_npc_actor_history_count": sum(
            not actor["controlled"] and actor["hp"] <= 0
            for actor in checkpoint.get("actors", {}).values()
        ),
        "native_qi_occupied_count": checkpoint.get("native_qi_occupied_count"),
    }
    samples = result.setdefault("progress_samples", [])
    marker = (sample["wave"], sample["defeated_monsters"])
    if not samples or marker != (samples[-1]["wave"], samples[-1]["defeated_monsters"]):
        samples.append(sample)
        result["current_progress"] = sample
        result["status"] = "RUNNING"
        write_progress(args, result)
    if not (stop_by_wave or stop_by_defeats):
        return False
    result["stop_receipt"] = {
        "reason": (
            "durable_defeated_monsters_threshold"
            if stop_by_defeats
            else "durable_wave_boundary"
        ),
        "phase": checkpoint["phase"],
        "wave": wave_state["wave"],
        "completed_waves": durable.get("completed_waves"),
        "defeated_monsters": defeated,
        "actor_history_count": len(checkpoint["actors"]),
        "dead_npc_actor_history_count": sample["dead_npc_actor_history_count"],
        "living_actor_count": sum(
            actor["hp"] > 0 for actor in checkpoint["actors"].values()
        ),
        "native_timeline_removed_count": checkpoint.get(
            "native_timeline_removed_count"
        ),
        "native_qi_occupied_count": checkpoint.get("native_qi_occupied_count"),
        "pending_wave": wave_state.get("pending_wave"),
        "winner": checkpoint.get("winner"),
    }
    result["stop_after_defeats_reached"] = stop_by_defeats
    return True


def actor_owns_current_turn(checkpoint, actor_id):
    return (
        checkpoint.get("phase") == "active"
        and checkpoint.get("current_actor_id") == actor_id
        and (checkpoint.get("runtime") or {}).get("awaiting_ack") is None
    )


def durable_turn_boundary(args, fight_id, events, *, previous=None, after_counter=None):
    """Wait for the asynchronous checkpoint of the actual shared native marker."""
    if not events or any(opcode != 12502 for opcode, _ in events):
        raise ValueError("Native turn boundary requires actual end-turn markers")
    bodies = {body for _, body in events}
    if len(bodies) != 1 or len(events[0][1]) != struct.calcsize(">iiiqii"):
        raise ValueError("Owners received inconsistent or malformed turn markers")
    actual_fight, action, parent, actor, unknown, flags = struct.unpack(
        ">iiiqii", events[0][1]
    )
    if (
        actual_fight != fight_id
        or action <= 0
        or parent != -1
        or (unknown, flags) != (-1, 0)
    ):
        raise ValueError("Invalid native turn marker identity")
    deadline = time.monotonic() + getattr(args, "action_timeout", 120)
    while True:
        checkpoint = observe(
            args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
        )
        if checkpoint.get("id") != fight_id:
            raise ValueError("Durable turn boundary fight identity mismatch")
        runtime = checkpoint.get("runtime") or {}
        # cvB headers use the published native allocator, not logical request IDs.
        revision = runtime.get("native_action_id")
        counter = runtime.get("awaiting_ack")
        turn = checkpoint.get("turn_id")
        prior = previous or {}
        prior_runtime = prior.get("runtime") or {}
        prior_turn = prior.get("turn_id")
        prior_counter = prior_runtime.get("awaiting_ack")
        minimum = prior_counter if type(prior_counter) is int else prior_turn
        actor_matches = (
            prior.get("current_actor_id") is None
            or counter != prior_turn
            or prior["current_actor_id"] == actor
        )
        progression = (
            type(counter) is int
            and (type(minimum) is not int or counter >= minimum)
            and (after_counter is None or counter > after_counter)
            and actor_matches
        )
        if type(revision) is int and revision >= action:
            if checkpoint.get("phase") == "finished":
                if type(counter) is int and (
                    after_counter is None or counter > after_counter
                ):
                    return checkpoint
            if (
                checkpoint.get("phase") == "active"
                and type(counter) is int
                and type(turn) is int
                and 0 <= counter < turn
                and progression
            ):
                return checkpoint
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            details = dict(
                marker_actor=actor,
                marker_native_action=action,
                prior_turn=prior_turn,
                prior_counter=prior_counter,
                prior_actor=prior.get("current_actor_id"),
                after_counter=after_counter,
                turn=turn,
                counter=counter,
                native_action=revision,
                logical_action=runtime.get("action_id"),
                phase=checkpoint.get("phase"),
            )
            raise TimeoutError(
                "Native turn marker has no matching durable ACK barrier: "
                + json.dumps(details, sort_keys=True)
            )
        time.sleep(min(0.1, remaining))


def acknowledge_native_boundary(peers, checkpoint, actions=None):
    """Send the counter observed in a durable checkpoint for a real 12502."""
    counter = (checkpoint.get("runtime") or {}).get("awaiting_ack")
    if type(counter) is not int:
        raise ValueError("Native 12502 boundary lacks its durable ACK counter")
    sent_at = [peer.send(13510, struct.pack(">i", counter)) for peer in peers]
    if actions is not None:
        actions["acks_sent"] += len(peers)
    return counter, sent_at


def drain_turn_boundaries(
    args,
    peers,
    fight_id,
    *,
    since=None,
    actions=None,
    previous=None,
    after_counter=None,
):
    """ACK every native successor boundary until a turn or terminal event."""
    terminal_pending = False
    while True:
        expected = {12502, 12755} if terminal_pending else {13482, 12502, 12755}
        events = wait_all(
            peers, expected, timeout=getattr(args, "action_timeout", 120), since=since
        )
        opcodes = [opcode for opcode, _ in events]
        if 12755 in opcodes:
            if any(opcode != 12755 for opcode in opcodes):
                raise ValueError("Owners received inconsistent native terminal reports")
            return events
        if terminal_pending and any(opcode != 12502 for opcode in opcodes):
            raise ValueError("Finished native fight emitted a nonterminal boundary")
        if not terminal_pending and any(opcode != 12502 for opcode in opcodes):
            if any(opcode == 12502 for opcode in opcodes):
                raise ValueError(
                    "Owners received inconsistent native successor boundaries"
                )
            return events
        checkpoint = durable_turn_boundary(
            args, fight_id, events, previous=previous, after_counter=after_counter
        )
        counter, since = acknowledge_native_boundary(peers, checkpoint, actions)
        previous, after_counter = checkpoint, counter
        terminal_pending = checkpoint.get("phase") == "finished"


def recover_stale_weapon_turn(
    args, peers, fight_id, actor_id, previous, rejection, *, since, actions, result
):
    if rejection.reason not in (
        "Not current owned turn",
        "Acción rechazada: Not current owned turn",
    ):
        raise rejection
    checkpoint = observe(
        args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
    )
    pending = (checkpoint.get("runtime") or {}).get("awaiting_ack")
    previous_pending = (previous.get("runtime") or {}).get("awaiting_ack")
    changed = checkpoint.get("current_actor_id") != actor_id or (
        type(pending) is int and pending != previous_pending
    )
    if checkpoint.get("phase") != "active" or not changed:
        raise rejection
    events = drain_turn_boundaries(
        args, peers, fight_id, since=since, actions=actions, previous=checkpoint
    )
    if (
        any(opcode != 13482 for opcode, _ in events)
        or len({body for _, body in events}) != 1
    ):
        raise ValueError("Stale action recovery did not reach a shared native turn")
    result.setdefault("stale_turn_recoveries", []).append(
        dict(
            actor_id=actor_id,
            previous_turn=previous.get("turn_id"),
            observed_turn=checkpoint.get("turn_id"),
            awaiting_ack=pending,
            reason=rejection.reason,
        )
    )
    return events[0][1]


def battle(args, peers, owners, geometry, fight_id, first_turn, result):
    """Real movement, ordinary unarmed attacks and actual turn ACKs only."""
    peer_by_owner = {owner["account_id"]: peer for owner, peer in zip(owners, peers)}
    current = first_turn
    boundaries = 0
    battle_started = time.monotonic()
    observer_start = len(args.observer_metrics)
    peer_wait_starts = [len(peer.wait_metrics) for peer in peers]
    actions = {
        "movement": 0,
        "unarmed_attack": 0,
        "weapon_attack": 0,
        "end_turn": 0,
        "acks_sent": 0,
    }
    stopped_at_target = False
    stopped_by_defeats = False
    while boundaries < args.max_turns:
        if time.monotonic() - battle_started >= args.max_battle_seconds:
            raise TimeoutError("QA reached its explicit battle wall-time bound")
        actor_id = struct.unpack_from(">q", current, 12)[0]
        checkpoint = observe(
            args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
        )
        if checkpoint["phase"] == "finished":
            break
        if stop_at_durable_boundary(args, checkpoint, result):
            stopped_at_target = True
            stopped_by_defeats = result.get("stop_after_defeats_reached", False)
            break
        checkpoint_actor_id = checkpoint.get("current_actor_id")
        if (
            checkpoint["runtime"].get("awaiting_ack") is not None
            or checkpoint_actor_id != actor_id
        ):
            # Native start-turn effects can skip an owner after 13482. Drain
            # that new 12502 barrier and ACK it before trusting another turn.
            since = [peer.last_received_at or 0.0 for peer in peers]
            skipped = wait_all(
                peers,
                {12502, 12755},
                timeout=getattr(args, "action_timeout", 120),
                since=since,
            )
            skipped_opcodes = [opcode for opcode, _ in skipped]
            if 12755 in skipped_opcodes:
                result["terminal_report_received"] = True
                result["terminal_report_peers"] = skipped_opcodes.count(12755)
                break
            checkpoint = observe(
                args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
            )
            counter = checkpoint["runtime"].get("awaiting_ack")
            if type(counter) is not int:
                raise ValueError(
                    "Skipped owner turn marker lacks its durable ACK counter"
                )
            ack_sent_at = [
                peer.send(13510, struct.pack(">i", counter)) for peer in peers
            ]
            actions["acks_sent"] += len(peers)
            turn_events = drain_turn_boundaries(
                args,
                peers,
                fight_id,
                since=ack_sent_at,
                actions=actions,
                previous=checkpoint,
                after_counter=counter,
            )
            turn_opcodes = [opcode for opcode, _ in turn_events]
            if 12755 in turn_opcodes:
                result["terminal_report_received"] = True
                result["terminal_report_peers"] = turn_opcodes.count(12755)
                break
            actor_ids = {
                struct.unpack_from(">q", body, 12)[0]
                for _, body in turn_events
                if len(body) >= 20
            }
            if len(actor_ids) != 1:
                raise ValueError(
                    "Owners received inconsistent actor IDs after skipped-turn ACK"
                )
            current = turn_events[0][1]
            boundaries += 1
            continue
        actor = checkpoint["actors"].get(str(actor_id))
        if actor is None:
            raise ValueError("Turn actor missing from the durable checkpoint")
        end_turn_sent_at = None
        last_action_sent_at = None
        recovered_turn = None
        movement_rejected = False
        if (
            actor["controlled"]
            and actor["hp"] > 0
            and actor_owns_current_turn(checkpoint, actor_id)
        ):
            peer = peer_by_owner[actor["owner_id"]]
            should_attack = (
                args.phase == "battle"
                and checkpoint["rift_wave_state"]["wave"] < args.target_wave
            )
            if should_attack and getattr(args, "seek_healing_orbs", False):
                checkpoint, healing_sent, movement = seek_healing_orb(
                    args, peer, checkpoint, geometry, fight_id, actor_id
                )
                if healing_sent is not None:
                    last_action_sent_at = healing_sent
                    movement_rejected = not movement["accepted"]
                    if movement["accepted"]:
                        actions["movement"] += 1
                        actions["healing_orb_movement"] = (
                            actions.get("healing_orb_movement", 0) + 1
                        )
                    else:
                        result.setdefault("movement_rejections", []).append(
                            dict(
                                movement,
                                actor_id=actor_id,
                                turn_id=checkpoint["turn_id"],
                            )
                        )
                    actor = checkpoint["actors"][str(actor_id)]
                    should_attack = actor["hp"] > 0 and actor_owns_current_turn(
                        checkpoint, actor_id
                    )
            if should_attack:
                targets = [
                    row
                    for row in checkpoint["actors"].values()
                    if row["team"] != actor["team"] and row["hp"] > 0
                ]
                if targets:
                    owner = next(
                        row for row in owners if row["account_id"] == actor["owner_id"]
                    )
                    weapon_uid = owner.get("weapon_uid")
                    minimum_range = owner.get("weapon_minimum_range", 1)
                    maximum_range = owner.get("weapon_maximum_range", 1)
                    checkpoint = combat_view(
                        args,
                        geometry,
                        fight_id,
                        actor_id,
                        minimum_range,
                        maximum_range,
                        checkpoint=checkpoint,
                    )
                    geometry = fight_geometry(checkpoint, geometry)
                    actor = checkpoint["actors"][str(actor_id)]
                    blocked = route_blocked_cells(checkpoint, actor_id)
                    target_rank = {
                        row["id"]: (
                            0
                            if str(row["id"])
                            in checkpoint["rift_wave_state"].get(
                                "native_wave_entries", {}
                            )
                            and checkpoint["rift_wave_state"]["native_wave_entries"][
                                str(row["id"])
                            ].get("wave")
                            == checkpoint["rift_wave_state"].get("wave")
                            else 1,
                            index,
                        )
                        for index, row in enumerate(checkpoint["actors"].values())
                        if row["team"] != actor["team"] and row["hp"] > 0
                    }
                    options = []
                    route = []
                    for target in targets:
                        current_target = checkpoint["actors"].get(str(target["id"]))
                        if current_target is None or current_target["hp"] <= 0:
                            continue
                        visible = visibility_for_target(
                            checkpoint, current_target["id"]
                        )
                        route = combat_route(
                            geometry,
                            actor["position"],
                            current_target["position"],
                            blocked,
                            actor["mp"],
                            minimum_range,
                            maximum_range,
                            visible,
                        )
                        in_range_and_visible = minimum_range <= abs(
                            actor["position"][0] - current_target["position"][0]
                        ) + abs(
                            actor["position"][1] - current_target["position"][1]
                        ) <= maximum_range and visible(
                            tuple(actor["position"])
                        )
                        if route or in_range_and_visible:
                            options.append(
                                (
                                    target_rank.get(
                                        current_target["id"], (1 << 30, 1 << 30)
                                    ),
                                    route,
                                    current_target,
                                )
                            )
                    selected_target = choose_combat_target(options)
                    if selected_target is not None:
                        _, route, _ = selected_target
                    if route and not movement_rejected:
                        sent_at = peer.send(
                            12161,
                            struct.pack(">q", actor_id)
                            + b"".join(struct.pack(">iih", *point) for point in route),
                        )
                        last_action_sent_at = sent_at
                        movement = wait_movement_action(
                            peer,
                            fight_id,
                            actor_id,
                            sent_at,
                            timeout=getattr(args, "action_timeout", 120),
                        )
                        if movement["accepted"]:
                            actions["movement"] += 1
                        else:
                            result.setdefault("movement_rejections", []).append(
                                dict(
                                    movement,
                                    actor_id=actor_id,
                                    turn_id=checkpoint["turn_id"],
                                )
                            )
                        checkpoint = combat_view(
                            args,
                            geometry,
                            fight_id,
                            actor_id,
                            minimum_range,
                            maximum_range,
                        )
                        geometry = fight_geometry(checkpoint, geometry)
                        actor = checkpoint["actors"][str(actor_id)]
                    for _ in range(8):
                        if (
                            not actor_owns_current_turn(checkpoint, actor_id)
                            or actor["hp"] <= 0
                        ):
                            break
                        owner = next(
                            row
                            for row in owners
                            if row["account_id"] == actor["owner_id"]
                        )
                        weapon_uid = owner.get("weapon_uid")
                        weapon_cost = owner.get("weapon_ap_cost", 0)
                        minimum_range = owner.get("weapon_minimum_range", 1)
                        maximum_range = owner.get("weapon_maximum_range", 1)
                        visible_now = checkpoint.get("native_visibility", {}).get(
                            ",".join(map(str, actor["position"])), {}
                        )
                        living = [
                            row
                            for row in checkpoint["actors"].values()
                            if row["team"] != actor["team"]
                            and row["hp"] > 0
                            and minimum_range
                            <= abs(row["position"][0] - actor["position"][0])
                            + abs(row["position"][1] - actor["position"][1])
                            <= maximum_range
                            and visible_now.get(str(row["id"]), False)
                        ]
                        if weapon_uid is not None and actor["ap"] < weapon_cost:
                            break
                        use_weapon = weapon_uid is not None
                        action_cost = weapon_cost if use_weapon else 3
                        if not living or actor["ap"] < action_cost:
                            break
                        target = min(living, key=lambda row: row["id"])
                        before = (actor["ap"], target["hp"])
                        item_uid = weapon_uid if use_weapon else -1
                        item_reference = args.weapon_reference if use_weapon else 2145
                        action_boundary_since = [
                            owner_peer.last_received_at or 0.0 for owner_peer in peers
                        ]
                        sent_at = peer.send(
                            12889,
                            struct.pack(
                                ">qqbiih", actor_id, item_uid, 15, *target["position"]
                            ),
                        )
                        last_action_sent_at = sent_at
                        try:
                            wait_weapon_action(
                                peers,
                                peer,
                                fight_id,
                                actor_id,
                                item_reference,
                                sent_at,
                                result,
                                timeout=getattr(args, "action_timeout", 120),
                            )
                        except NativeActionRejected as rejection:
                            recovered_turn = recover_stale_weapon_turn(
                                args,
                                peers,
                                fight_id,
                                actor_id,
                                checkpoint,
                                rejection,
                                since=action_boundary_since,
                                actions=actions,
                                result=result,
                            )
                            break
                        actions[
                            "weapon_attack" if use_weapon else "unarmed_attack"
                        ] += 1
                        checkpoint = combat_view(
                            args,
                            geometry,
                            fight_id,
                            actor_id,
                            owner.get("weapon_minimum_range", 1),
                            owner.get("weapon_maximum_range", 1),
                        )
                        if checkpoint["phase"] == "finished":
                            break
                        actor = checkpoint["actors"][str(actor_id)]
                        if before == (
                            actor["ap"],
                            checkpoint["actors"][str(target["id"])]["hp"],
                        ):
                            raise ValueError(
                                "Native 12889 action did not change AP or target HP"
                            )
                        if (
                            not actor_owns_current_turn(checkpoint, actor_id)
                            or actor["hp"] <= 0
                        ):
                            break
            if recovered_turn is not None:
                current = recovered_turn
                boundaries += 1
                continue
            if checkpoint["phase"] != "finished":
                if actor_owns_current_turn(checkpoint, actor_id):
                    end_turn_sent_at = peer.send(
                        12403,
                        struct.pack(
                            ">qh", actor_id, checkpoint["native_timeline_round"]
                        ),
                    )
                    actions["end_turn"] += 1
        else:
            end_turn_sent_at = None
        boundary_since = (
            end_turn_sent_at
            if end_turn_sent_at is not None
            else last_action_sent_at
            if last_action_sent_at is not None
            else [peer.last_received_at or 0.0 for peer in peers]
        )
        end_events = wait_all(
            peers,
            {12502, 12755},
            timeout=getattr(args, "action_timeout", 120),
            since=boundary_since,
        )
        end_opcodes = [opcode for opcode, _ in end_events]
        if 12755 in end_opcodes:
            if any(opcode != 12755 for opcode in end_opcodes):
                raise ValueError("Owners received inconsistent native terminal reports")
            result["terminal_report_received"] = True
            result["terminal_report_peers"] = end_opcodes.count(12755)
            break
        checkpoint = durable_turn_boundary(
            args, fight_id, end_events, previous=checkpoint
        )
        counter, ack_sent_at = acknowledge_native_boundary(peers, checkpoint, actions)
        turn_events = drain_turn_boundaries(
            args,
            peers,
            fight_id,
            since=ack_sent_at,
            actions=actions,
            previous=checkpoint,
            after_counter=counter,
        )
        turn_opcodes = [opcode for opcode, _ in turn_events]
        if 12755 in turn_opcodes:
            if any(opcode != 12755 for opcode in turn_opcodes):
                raise ValueError("Owners received inconsistent native terminal reports")
            result["terminal_report_received"] = True
            result["terminal_report_peers"] = turn_opcodes.count(12755)
            break
        if checkpoint.get("phase") == "finished":
            raise ValueError(
                "Finished native checkpoint did not produce terminal reports after ACK"
            )
        actor_ids = {
            struct.unpack_from(">q", body, 12)[0]
            for _, body in turn_events
            if len(body) >= 20
        }
        if len(actor_ids) != 1:
            raise ValueError("Owners received inconsistent actor IDs after turn ACK")
        current = turn_events[0][1]
        boundaries += 1
    else:
        raise TimeoutError(
            "QA reached its explicit real-turn bound without a terminal report"
        )
    result["real_turn_boundaries"] = boundaries
    result["combat_final"] = observe(
        args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
    )
    observer_samples = args.observer_metrics[observer_start:]
    peer_samples = [
        peer.wait_metrics[start:] for peer, start in zip(peers, peer_wait_starts)
    ]
    result["battle_metrics"] = {
        "wall_ms": round((time.monotonic() - battle_started) * 1000, 3),
        "observer_calls": len(observer_samples),
        "observer_ms": summarize([sample["elapsed_ms"] for sample in observer_samples]),
        "actions": actions,
        "stop_after_wave_reached": stopped_at_target,
        "stop_after_defeats_reached": stopped_by_defeats,
        "peer_waits": [
            {
                "owner_index": index,
                "wait_count": len(samples),
                "wait_ms": summarize([sample["wait_ms"] for sample in samples]),
                "send_to_receive_ms": summarize(
                    [
                        sample["since_send_ms"]
                        for sample in samples
                        if "since_send_ms" in sample
                    ]
                ),
                "queued_before_wait_ms": summarize(
                    [sample["queued_ms"] for sample in samples if "queued_ms" in sample]
                ),
            }
            for index, samples in enumerate(peer_samples)
        ],
    }


def next_event(peer):
    if peer.pending:
        return peer.pending.pop(0)
    try:
        return peer.events.get_nowait()
    except queue.Empty:
        return None


def decode_owned_recovery(body):
    """Decode the native BETWEEN snapshot without treating it as a live turn."""
    from wakfu_server.combat_core_reconstruction import decode_core_packet, _Reader

    reader = _Reader(body)
    fight = reader.read("i")
    envelope = _Reader(reader.blob("h"))
    if envelope.read("BBiB") != (1, 0, 6, 0):
        raise ValueError("Unknown owned recovery envelope")
    payload = envelope.blob("h")
    envelope.done()
    reader.done()
    timeline = _Reader(payload)
    round_number, turn, phase, deadline = timeline.read("hibq")
    if phase != 2:
        return decode_core_packet(12053, body)
    available = [timeline.read("q") for _ in range(timeline.count("b"))]
    next_order = [timeline.read("q") for _ in range(timeline.count("b"))]
    progress = {}
    for _ in range(timeline.count("b")):
        identity, count = timeline.read("qh")
        if identity in progress:
            raise ValueError("Duplicate BETWEEN progress member")
        progress[identity] = count
    index = timeline.read("b")
    removed = {}
    for _ in range(timeline.count("b")):
        identity, count, position, modifications = timeline.read("qhih")
        if identity in removed or modifications:
            raise ValueError("Unknown BETWEEN removed-member layout")
        removed[identity] = dict(progress=count, position=position)
    bonuses = {}
    for _ in range(timeline.count("b")):
        identity, bonus = timeline.read("qi")
        if identity in bonuses:
            raise ValueError("Duplicate BETWEEN bonus member")
        bonuses[identity] = bonus
    timeline.done()
    members = set(available)
    if (
        not members
        or members != set(next_order)
        or members != set(progress)
        or members & set(removed)
        or not -1 <= index < len(available) - 1
    ):
        raise ValueError("Inconsistent native BETWEEN timeline")
    return dict(
        kind="recovery",
        fight=fight,
        opcode=12053,
        timeline=dict(
            round=round_number,
            turn=turn,
            phase=phase,
            deadline=deadline,
            available=available,
            next_order=next_order,
            progress=progress,
            index=index,
            removed=removed,
            bonuses=bonuses,
            current=None,
        ),
    )


def resumed_control_record(args, peers, fight_id, counters):
    """Accept real resumed SU state or new-turn events without inventing a turn."""

    timelines, turns, markers, witnessed = {}, {}, set(), set()
    inspected = None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        progressed = False
        for index, peer in enumerate(peers):
            event = next_event(peer)
            if event is None:
                continue
            progressed = True
            opcode, body, received = event
            if opcode is None:
                raise body
            if opcode == 12053:
                decoded = decode_owned_recovery(body)
                if decoded["fight"] != fight_id:
                    raise ValueError("Recovery timeline changed fight")
                timelines[index] = decoded["timeline"]
                peer.last_received_at = received
            elif opcode == 12502:
                markers.add(index)
                timelines.pop(index, None)
                turns.pop(index, None)
            elif opcode == 13482:
                turns[index] = body
                peer.last_received_at = received
            elif opcode == 12755:
                raise ValueError("Existing fight ended during native recovery")
        if len(markers) == len(peers):
            checkpoint = observe(
                args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
            )
            current_counter = (checkpoint.get("runtime") or {}).get("awaiting_ack")
            for index, peer in enumerate(peers):
                counter = (
                    current_counter
                    if type(current_counter) is int
                    else counters[index]
                    if index not in witnessed
                    else None
                )
                if type(counter) is not int:
                    raise ValueError("Native recovery marker lacks a current counter")
                peer.send(13510, struct.pack(">i", counter))
                witnessed.add(index)
            markers.clear()
            inspected = None
        if len(turns) == len(peers):
            if len(set(turns.values())) != 1:
                raise ValueError("Owners received inconsistent resumed turns")
            return turns[0]
        if len(timelines) == len(peers) and not markers:
            signature = tuple(
                (timelines[i]["phase"], timelines[i]["turn"], timelines[i]["current"])
                for i in range(len(peers))
            )
            if signature != inspected:
                inspected = signature
                checkpoint = observe(
                    args, dict(operation="combat", wave=args.wave, fight_id=fight_id)
                )
                expected = (1, checkpoint["turn_id"], checkpoint["current_actor_id"])
                if (
                    checkpoint["phase"] == "active"
                    and (checkpoint.get("runtime") or {}).get("awaiting_ack") is None
                    and all(row == expected for row in signature)
                ):
                    # Local battle-loop input only. This record is never sent.
                    return struct.pack(">iiiq", fight_id, 0, -1, expected[2])
        if not progressed:
            time.sleep(0.01)
    raise TimeoutError("Native recovery did not reach a consistent playable state")


def connect_existing_scene(args, owners, peers):
    """Establish the complete owner cohort before waiting for scene loading."""
    for owner in owners:
        peers.append(connect(args, owner, reconnect=True))
    for peer in peers:
        peer.wait(630)
        peer.wait(711)
        peer.send(12449)
        peer.wait(12436)
        peer.wait(711)
        peer.send(12449)
    return peers


def reconnect_owned_combat(args, owners, fight_id, *, peers=None):
    """Recover the existing native cohort, without issuing a gameplay action."""
    from wakfu_server.combat_wire import decode_bootstrap

    peers = [] if peers is None else peers
    connect_existing_scene(args, owners, peers)
    counters = []
    for peer in peers:
        bootstrap = decode_bootstrap(peer.wait(12847)[1])
        if bootstrap["fight_id"] != fight_id:
            raise ValueError("Native reconnect changed fight identity")
        counters.append(struct.unpack_from(">i", bootstrap["myG"], 2)[0])
    return peers, resumed_control_record(args, peers, fight_id, counters)


def resume_existing_battle(args, owners, peers, result, catalog):
    if len(owners) != args.owners or any(
        not row["username"].startswith("rfnetqa_") for row in owners
    ):
        raise ValueError("Resume requires the exact existing QA cohort")
    state = observe(
        args,
        dict(
            operation="state",
            wave=args.wave,
            character_ids=[row["character"]["id"] for row in owners],
        ),
    )
    if not state["runs"] or state["runs"][0]["fight_id"] != args.resume_fight_id:
        raise ValueError("Saved QA roster does not own the requested existing fight")
    if state["fight"]["status"] != "active" or set(state["runs"][0]["members"]) != {
        row["character"]["id"] for row in owners
    }:
        raise ValueError("Resume requires an active exact owner-only encounter")
    for owner in owners:
        if args.weapon_reference is None:
            equipped = observe(
                args,
                dict(
                    operation="weapon_guard",
                    wave=args.wave,
                    account_id=owner["account_id"],
                    character_id=owner["character"]["id"],
                ),
            )
            if equipped["reference"] is not None:
                raise ValueError(
                    f"Existing QA character {owner['character']['id']} has an equipped weapon; resume with --weapon-reference {equipped['reference']}"
                )
        if args.weapon_reference is not None:
            weapon = observe(
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
    _, first_turn = reconnect_owned_combat(
        args, owners, args.resume_fight_id, peers=peers
    )
    result["stages"].append("existing_qa_native_reconnect")
    result["resumed_fight_id"] = args.resume_fight_id
    result["fight_id"] = args.resume_fight_id
    geometry = observe(
        args, dict(operation="geometry", wave=args.wave, map_id=catalog["map_id"])
    )
    battle(args, peers, owners, geometry, args.resume_fight_id, first_turn, result)
    result["status"] = "PASS" if result.get("stop_after_defeats_reached") else "PARTIAL"


def equipment_reference(value):
    try:
        reference, slot = map(int, value.split(":"))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("Equipment must be REFERENCE:SLOT") from None
    if reference <= 0 or not 0 <= slot <= 31:
        raise argparse.ArgumentTypeError("Equipment reference/slot is out of range")
    return reference, slot


def equip_qa_loadout(args, peer, owner, loadout):
    """Use ordinary pre-fight commands and verify the owned active sheet."""
    receipts = []
    for reference, slot in loadout:
        query = dict(
            operation="equipment",
            wave=args.wave,
            account_id=owner["account_id"],
            character_id=owner["character"]["id"],
            reference=reference,
            slot=slot,
        )
        command = f"!item {reference} 1".encode()
        sent = peer.send(12366, struct.pack(">H", len(command)) + command)
        peer.wait(674, since=sent)
        granted = observe(args, query)
        command = f"!equip {granted['uid']} {slot}".encode()
        sent = peer.send(12366, struct.pack(">H", len(command)) + command)
        peer.wait(674, since=sent)
        verified = observe(args, dict(query, require_equipped=True))
        if (
            verified["uid"] != granted["uid"]
            or not verified["equipped"]
            or verified["slot"] != slot
            or not 0 < verified["hp"] <= verified["max_hp"]
        ):
            raise ValueError("Native QA equipment or health verification failed")
        receipts.append(dict(reference=reference, **verified))
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--container", default="wakfu-local-world-1")
    parser.add_argument("--owners", type=int, choices=(1, 4, 6), required=True)
    parser.add_argument("--heroes-per-owner", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--wave", type=int, default=3)
    parser.add_argument("--level", type=int, default=33)
    parser.add_argument(
        "--phase", choices=("entry", "ready", "loss", "battle"), default="ready"
    )
    parser.add_argument("--target-wave", type=int, default=4)
    parser.add_argument(
        "--stop-after-wave",
        type=int,
        help="Stop only after every peer receives a real turn boundary and the durable active wave reaches this number.",
    )
    parser.add_argument(
        "--stop-after-defeats",
        type=int,
        help="Stop at the first active durable wave boundary after at least this many deaths.",
    )
    parser.add_argument("--max-battle-seconds", type=int, default=3600)
    parser.add_argument(
        "--weapon-reference",
        type=int,
        help="Grant and equip this native QA weapon using ordinary admin chat commands.",
    )
    parser.add_argument("--max-turns", type=int, default=320)
    parser.add_argument(
        "--action-timeout",
        type=float,
        default=120,
        help="Native action response deadline in seconds; measured latency is still recorded.",
    )
    parser.add_argument(
        "--seek-healing-orbs",
        action="store_true",
        help="Below70 percent HP, use remaining native MP to contact an existing healing orb before attacking.",
    )
    parser.add_argument(
        "--equipment-reference",
        action="append",
        type=equipment_reference,
        default=[],
        metavar="REFERENCE:SLOT",
        help="Equip ordinary QA gear using native commands before party/fight entry; repeat for each slot.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-new-qa", action="store_true")
    parser.add_argument("--resume-credentials", type=Path)
    parser.add_argument("--resume-fight-id", type=int)
    parser.add_argument("--execute-existing-qa", action="store_true")
    args = parser.parse_args()
    if not 0 < args.action_timeout <= 600:
        parser.error("--action-timeout must be positive and at most600 seconds")
    resuming = args.resume_credentials is not None or args.resume_fight_id is not None
    if resuming and args.equipment_reference:
        parser.error("Equipment setup is only available before a new QA fight")
    if len({slot for _, slot in args.equipment_reference}) != len(
        args.equipment_reference
    ):
        parser.error("Equipment setup must not repeat an equipment slot")
    if args.weapon_reference is not None and any(
        slot == 15 for _, slot in args.equipment_reference
    ):
        parser.error("Use --weapon-reference for slot15 when requesting weapon combat")
    if resuming and (
        not args.execute_existing_qa
        or args.resume_credentials is None
        or args.resume_fight_id is None
        or args.phase != "battle"
        or args.heroes_per_owner
    ):
        parser.error(
            "Resume requires credentials, fight ID, --execute-existing-qa and owner-only battle"
        )
    if resuming and (
        args.host not in ("127.0.0.1", "localhost")
        or not args.http_url.startswith(("http://127.0.0.1:", "http://localhost:"))
    ):
        parser.error("Existing QA resume is local only")
    if not resuming and not args.execute_new_qa:
        parser.error("No actions performed; --execute-new-qa is required")
    if args.owners * (1 + args.heroes_per_owner) > 6:
        parser.error("This acceptance runner uses at most six combat units")
    if args.stop_after_wave is not None and args.phase != "battle":
        parser.error("--stop-after-wave requires --phase battle")
    if args.stop_after_wave is not None and args.stop_after_wave > args.target_wave:
        parser.error("--stop-after-wave must not exceed --target-wave")
    if args.stop_after_wave is not None and args.stop_after_defeats is not None:
        parser.error("Choose only one stop target")
    if args.stop_after_defeats is not None and (
        args.phase != "battle" or args.stop_after_defeats < 1
    ):
        parser.error(
            "--stop-after-defeats requires --phase battle and a positive count"
        )
    if args.max_battle_seconds < 1:
        parser.error("--max-battle-seconds must be positive")
    args.observer_metrics = []
    result = dict(
        status="RUNNING",
        channel="native_tls",
        official_client=False,
        owners=args.owners,
        heroes_per_owner=args.heroes_per_owner,
        action_timeout_seconds=args.action_timeout,
        stages=[],
    )
    owners, peers = [], []
    private = args.output.with_suffix(".credentials.private.json")
    try:
        catalog = observe(args, dict(operation="catalog", wave=args.wave))
        if catalog["type"] != "INFINITE_WAVE":
            raise ValueError("This first complete runner uses a classic native Rift")
        if resuming:
            owners = json.loads(args.resume_credentials.read_text())
            resume_existing_battle(args, owners, peers, result, catalog)
            return
        for index in range(args.owners):
            owner = dict(
                username="rfnetqa_" + secrets.token_hex(7),
                password=secrets.token_urlsafe(24),
            )
            account = post(args, "/register", owner)
            login = post(args, "/login", owner)
            owner["account_id"] = account["id"]
            owner["character"] = post(
                args,
                "/characters",
                {
                    "name": "Rfnet"
                    + "".join(
                        secrets.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(10)
                    ),
                    "breed": 19,
                },
                login["api_token"],
            )
            owner["heroes"] = [
                post(
                    args,
                    "/characters",
                    {
                        "name": "Rfhero"
                        + "".join(
                            secrets.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(9)
                        ),
                        "breed": 19,
                    },
                    login["api_token"],
                )
                for _ in range(args.heroes_per_owner)
            ]
            owners.append(owner)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            private.write_text(json.dumps(owners))
            os.chmod(private, 0o600)
            observe(
                args,
                dict(
                    operation="setup",
                    wave=args.wave,
                    account_id=owner["account_id"],
                    character_id=owner["character"]["id"],
                    index=index,
                ),
            )
            peer = connect(args, owner)
            peers.append(peer)
            if args.level != 1:
                command = f"!level {args.level}".encode()
                sent_at = peer.send(12366, struct.pack(">H", len(command)) + command)
                peer.wait(674, since=sent_at)
            if args.weapon_reference is not None:
                command = f"!item {args.weapon_reference} 1".encode()
                sent_at = peer.send(12366, struct.pack(">H", len(command)) + command)
                peer.wait(674, since=sent_at)
                weapon = observe(
                    args,
                    dict(
                        operation="weapon",
                        wave=args.wave,
                        account_id=owner["account_id"],
                        character_id=owner["character"]["id"],
                        reference=args.weapon_reference,
                    ),
                )
                command = f"!equip {weapon['uid']} 15".encode()
                sent_at = peer.send(12366, struct.pack(">H", len(command)) + command)
                peer.wait(674, since=sent_at)
                verified = observe(
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
                owner["weapon_uid"] = verified["uid"]
                owner["weapon_ap_cost"] = verified["ap_cost"]
                owner["weapon_minimum_range"] = verified["minimum_range"]
                owner["weapon_maximum_range"] = verified["maximum_range"]
            if args.equipment_reference:
                owner["equipment_receipts"] = equip_qa_loadout(
                    args, peer, owner, args.equipment_reference
                )
                result.setdefault("equipment_loadouts", []).append(
                    dict(
                        character_id=owner["character"]["id"],
                        items=owner["equipment_receipts"],
                    )
                )
            for hero in owner["heroes"]:
                peer.send(12219, struct.pack(">q", hero["id"]))
                if peer.wait(12587)[1] != b"\x01":
                    raise ValueError("Native owned-hero addition rejected")
        result["qa_identities"] = [
            {
                "account_id": o["account_id"],
                "character_id": o["character"]["id"],
                "hero_ids": [h["id"] for h in o["heroes"]],
            }
            for o in owners
        ]
        result["stages"].append("http_dispatcher_world_selection")
        for owner, peer in zip(owners[1:], peers[1:]):
            peers[0].send(
                1156, struct.pack(">BqqBq", 1, -1, -1, 1, owner["character"]["id"])
            )
            invite = peer.wait(1072)[1]
            size = invite[1]
            inviter = invite[2 : 2 + size]
            identity = struct.unpack_from(">q", invite, 2 + size)[0]
            peer.send(
                1031,
                b"\x01\x01"
                + bytes((len(inviter),))
                + inviter
                + b"\x00"
                + struct.pack(">q", identity),
            )
            peer.wait(1184)
        result["stages"].append("native_party_and_heroes")
        portal = catalog["entrances"][0]
        peers[0].send(12870, struct.pack(">qHH", portal["object_id"], 11, 0))
        arrivals = []
        for peer in peers:
            bootstrap = peer.wait(13974)
            size = struct.unpack_from(">H", bootstrap[1])[0]
            fields = struct.unpack(">BqBqiihqBBiihq", bootstrap[1][2 : 2 + size])
            arrivals.append(tuple(fields[4:7]))
            peer.send(14689)
        result["stages"].append("native_party_rift_portal")
        portal_state = observe(
            args,
            dict(
                operation="state",
                wave=args.wave,
                character_ids=[o["character"]["id"] for o in owners],
            ),
        )
        rows = {row["id"]: row for row in portal_state["characters"]}
        arrivals = [
            tuple(rows[o["character"]["id"]][key] for key in ("x", "y", "z"))
            for o in owners
        ]
        result["portal_positions"] = arrivals
        geometry = observe(
            args, dict(operation="geometry", wave=args.wave, map_id=catalog["map_id"])
        )
        activators = [
            row
            for row in catalog["objects"]
            if row["type"] == "GenericActivableInteractiveElement"
        ]
        if len(activators) != 1:
            raise ValueError("Ambiguous original Rift start activator")
        walk(peers[0], geometry, arrivals[0], activators[0])
        time.sleep(0.5)
        peers[0].send(12870, struct.pack(">qHH", activators[0]["id"], 0, 0))
        for peer in peers:
            opcode, body = peer.wait(12847)
            peer.wait(13652)
        result["stages"].append("native_all_owner_placement")
        time.sleep(1)
        for peer in peers:
            if peer.failure is not None:
                raise peer.failure
        if args.phase != "entry":
            for peer in peers:
                peer.send(12523, b"\x01")
            starts = [peer.wait(13482)[1] for peer in peers]
            result["stages"].append("native_all_owner_ready")
            if args.phase in ("loss", "battle"):
                state = observe(
                    args,
                    dict(
                        operation="state",
                        wave=args.wave,
                        character_ids=[o["character"]["id"] for o in owners],
                    ),
                )
                fight_id = state["runs"][0]["fight_id"]
                result["fight_id"] = fight_id
                write_progress(args, result)
                battle(args, peers, owners, geometry, fight_id, starts[0], result)
        result["state"] = observe(
            args,
            dict(
                operation="state",
                wave=args.wave,
                character_ids=[o["character"]["id"] for o in owners],
            ),
        )
        result["status"] = "PARTIAL"
        if result.get("stop_receipt"):
            result[
                "limit"
            ] = "Stopped at the observed durable wave boundary; this is a live, nonterminal partial combat and does not qualify complete waves or settlement."
        elif args.phase == "battle":
            result[
                "limit"
            ] = "Battle loop reached its terminal event or real-turn bound; this does not qualify the full Rift matrix or official-client presentation."
        else:
            result["limit"] = "Entry/Ready only; never counted as full matrix PASS."
    except BaseException as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        for peer in peers:
            peer.close()
        result["peer_opcodes"] = [
            {"received": p.seen, "sent": p.sent, "tls": p.tls} for p in peers
        ]
        result["observer_metrics"] = {
            "count": len(args.observer_metrics),
            "total_ms": round(
                sum(sample["elapsed_ms"] for sample in args.observer_metrics), 3
            ),
            "by_operation": {
                operation: summarize(
                    [
                        sample["elapsed_ms"]
                        for sample in args.observer_metrics
                        if sample["operation"] == operation
                    ]
                )
                for operation in sorted(
                    {sample["operation"] for sample in args.observer_metrics}
                )
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
