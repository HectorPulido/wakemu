"""Persistent local TLS owner for the already-earned post-Goultard story.

Start with python -i; helpers run in the same ordinary client session. Public
position commands are recorded setup only. Private walking uses pinned player
exploration; no quest/stat writes or ordinary combat strategy is provided.
"""
import atexit, json, os, struct, time
from pathlib import Path
from tools.regional_quest_tls_probe import RegionalProbe
from tools.rii_departure_probe import ObservedPeer, login
from tools.line2_rank23_native_tls_probe import _progress
from wakfu_server.store import Store
from wakfu_server import dungeon_runtime
from wakfu_server.command_permissions import is_admin, set_admin


class StoryProbe(RegionalProbe):
    def note(self, boundary, **facts):
        self.receipt.setdefault("journey", []).append(dict(boundary=boundary, **facts))
        self.save()
        print(json.dumps(dict(boundary=boundary, **facts), default=str), flush=True)

    def ack_loads(self, mark=0, timeout=8):
        deadline = time.monotonic() + timeout
        cursor = getattr(self, "ack_cursor", mark)
        last = time.monotonic()
        while time.monotonic() < deadline:
            with self.peer.observation_lock:
                rows = self.peer.records[cursor:]
                cursor = len(self.peer.records)
            self.ack_cursor = cursor
            for opcode, _body in rows:
                if opcode == 711:
                    self.peer.send(12449)
                    last = time.monotonic()
            if time.monotonic() - last > 0.5:
                return
            time.sleep(0.05)

    def configuration(self):
        current = self.current()
        instance = current["instance_id"]
        if not instance:
            raise ValueError("No current owned configuration")
        if instance not in self.configurations:
            with self.store.connection() as db:
                _route, config = dungeon_runtime.configuration_for_instance(
                    db, instance
                )
            self.configurations[instance] = config
        return self.configurations[instance]

    def walk(self, goal):
        if self.current()["instance_id"]:
            from tools.quest_instance_combat_probe import walk_native

            configuration = self.configuration()
            if not configuration["topology"].get("exploration_geometry"):
                return super().walk(goal)
            if configuration["topology"].get("owned_story_controller"):
                from copy import deepcopy
                from wakfu_server import owned_story_controller

                with self.store.connection() as db:
                    selected, completed = owned_story_controller._scope(
                        db, self.store, self.current(), check_position=False, lock=False
                    )
                blocked = owned_story_controller.collision_projection(
                    selected, completed
                )["blocked"]
                if blocked:
                    configuration = deepcopy(configuration)
                    geometry = dict(configuration["topology"]["exploration_geometry"])
                    geometry["edges"] = [
                        edge
                        for edge in geometry["edges"]
                        if all(tuple(point) not in blocked for point in edge)
                    ]
                    configuration["topology"]["exploration_geometry"] = geometry
            try:
                return walk_native(self, configuration, goal)
            except AssertionError as error:
                if (
                    not error.args
                    or not isinstance(error.args[0], tuple)
                    or error.args[0][0] != "Quest walk did not settle"
                ):
                    raise
                # Native movement can finish before its ordinary asynchronous
                # position flush. Poll that same movement, never resend it.
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    current = self.current()
                    if tuple(current[k] for k in ("x", "y", "z")) == tuple(goal):
                        return
                    time.sleep(0.1)
                raise AssertionError(
                    (
                        "Native private movement did not persist",
                        tuple(goal),
                        tuple(current[k] for k in ("x", "y", "z")),
                    )
                ) from None
        try:
            return super().walk(goal)
        except AssertionError as error:
            if "No native world walking path" not in str(error):
                raise
            return self.position(self.current()["map_id"], goal)

    def move_to(self, map_id, position):
        current = self.current()
        if current["map_id"] == map_id:
            return self.walk(position)
        if current["instance_id"]:
            raise ValueError("No private administrative travel")
        return self.position(map_id, position)

    def position(self, map_id, position):
        if self.current()["instance_id"]:
            raise ValueError("No private administrative position")
        previous = is_admin(self.store, self.account["id"])
        before = self.progress()
        mark = self.peer.mark()
        text = "!tp " + str(map_id) + " " + " ".join(map(str, position))
        try:
            set_admin(
                self.store,
                self.account["id"],
                True,
                operator="Codex local QA",
                reason="Authorized public story source positioning only; no quest/stat/outcome command",
            )
            raw = text.encode()
            self.peer.send(12366, struct.pack(">H", len(raw)) + raw)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                self.ack_loads(mark, timeout=0.6)
                current = self.current()
                if (
                    current["map_id"],
                    current["instance_id"],
                    current["x"],
                    current["y"],
                    current["z"],
                ) == (map_id, 0, *position):
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Public source positioning did not settle")
        finally:
            set_admin(
                self.store,
                self.account["id"],
                previous,
                operator="Codex local QA",
                reason="Restore role after public story source positioning",
            )
        if before != self.progress():
            raise AssertionError(
                "Public QA positioning advanced quest state; not natural source evidence"
            )
        self.note(
            "public source position setup only",
            command=text,
            qualification="Not a fully walked public route; actual source action remains required",
            admin_restored=True,
        )


def connect():
    global store, probe
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    path = Path(".local-state/wakemu/qa/line4-story-293-369.json")
    probe = StoryProbe(store, 293, 369, path)
    probe.configurations = {}
    if path.exists():
        probe.receipt = json.loads(path.read_text())
    else:
        probe.receipt.update(
            scope="Line4 only; retained2165/2166/2170/2675 proof reused. Ordinary !winfight outcomes explicitly administrative; genuine noncombat mechanics retained.",
            journey=[],
            trace=[],
        )
    state = probe.progress()
    if not {2165, 2166, 2170, 2675} <= set(state["completed"]):
        raise ValueError("Natural story prerequisites missing")
    probe.peer = ObservedPeer()
    login(store, probe.peer, probe.account, probe.current())
    probe.ack_cursor = len(probe.peer.records)
    probe.note(
        "existing story character connected",
        character_id=369,
        account_id=293,
        level=probe.current()["level"],
        position={
            k: probe.current()[k] for k in ("map_id", "instance_id", "x", "y", "z")
        },
        retained_completed=[2165, 2166, 2170, 2675],
    )
    return probe


def close():
    if globals().get("probe") and probe.peer:
        probe.save()
        probe.peer.close()
    if globals().get("store"):
        store.close()


if __name__ == "__main__":
    atexit.register(close)
    connect()
    print(
        "READY: existing single TLS peer; invoke source helpers on probe.", flush=True
    )
