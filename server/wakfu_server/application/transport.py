"""Socket publication ordering and native write acknowledgements."""

import threading


class AbortedNativeReturn:
    def __init__(self, owner, shared):
        self.owner, self.shared = owner, shared
        self.acknowledged = self.world_returned = False
        self.command = self.callback_flag = None

    def require(self, account_id, generation, character_id):
        owner = self.owner
        if (
            (owner.account_id, owner.generation, owner.character_id)
            != (account_id, generation, character_id)
            or self.shared.participants.get(account_id) != owner
            or character_id
            not in (getattr(self.shared, "publication_recovery_aborted", None) or {})
        ):
            raise ValueError("Aborted native return lost its selected owner")

    def packets(self):
        from copy import copy
        from wakfu_server.combat_abandon import _terminal_packets, placement_runtime

        actor = self.shared.fight.actors.get(self.owner.character_id)
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != self.owner.account_id
        ):
            raise ValueError("Aborted native return has no owned participant")
        runtime = copy(placement_runtime(self.shared.fight, self.shared.runtime))
        # This codec only reads the original roster/counters. Durable abort,
        # health, grants and the authoritative winner are never changed here.
        if getattr(self.shared, "settlement_ready", False):
            from wakfu_server.combat_results import terminal_event

            packets = [terminal_event(runtime), runtime._flush()]
        else:
            packets = _terminal_packets(runtime, actor.team)
        # Original cvF.eIl -> buH.W -> kv selects the second UID list;
        # aUH emits its negated membership flag for the actual local actor.
        # Company members on the same native team have the same membership.
        import struct

        body = packets[0][1]
        second = 14 + 8 * body[13]
        count = body[second]
        ids = struct.unpack_from(">" + "q" * count, body, second + 1)
        self.callback_flag = self.owner.character_id not in ids
        return packets

    def acknowledge(self, body):
        from wakfu_server.combat_results import continuation

        if (
            self.callback_flag is None
            or continuation(self.shared.fight.id, body) != self.callback_flag
        ):
            raise ValueError("Aborted native return has a foreign native callback flag")
        self.acknowledged = True


def written_fight_id(data, previous):
    """Observe actual successful12847 writes; never infer native construction."""
    import struct

    offset = 0
    while offset < len(data):
        length, opcode = struct.unpack_from(">IH", data, offset)
        if length < 6 or offset + length > len(data):
            raise ValueError("Invalid actually written combat frame")
        if opcode == 12847:
            previous = struct.unpack_from(">i", data, offset + 6)[0]
        offset += length
    return previous


class Connection:
    """Serialize frames sent by the receiver and other players' workers."""

    def __init__(self, socket, *, runtime):
        self.runtime = runtime
        self.socket = socket
        self.write_lock = threading.RLock()
        self.item_spell_uids = set()
        from wakfu_server.combat_instance_publication import InstancePublicationTracker
        from wakfu_server.combat_external_markers import MarkerPublications

        self.instance_publications = InstancePublicationTracker()
        self.native_fight_id = None
        self.marker_publications = MarkerPublications()
        self.native_instance_scope = lambda: None
        self.interactive_publication = None
        self.interactive_scope = lambda: None
        self.interactive_trace = []
        self.ranch_scene_refresh = None

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def sendall(self, data):
        with self.runtime.PROFILER.span("network.send_lock"):
            self.write_lock.acquire()
        try:
            publication_scope = self.native_instance_scope()
            if self.interactive_publication is not None:
                self.interactive_trace.clear()
                data = self.interactive_publication.transform(
                    data, self.interactive_scope()
                )
            with self.runtime.PROFILER.span("network.send"):
                if data:
                    self.socket.sendall(data)
            self.instance_publications.after_write(data, publication_scope)
            self.marker_publications.after_write(data, publication_scope)
            self.native_fight_id = written_fight_id(data, self.native_fight_id)
            for event in self.interactive_trace:
                self.runtime.record(event="interactive_wire_publication", **event)
        except BaseException:
            self.instance_publications.invalidate()
            self.marker_publications.reset(None)
            if self.interactive_publication is not None:
                self.interactive_publication.clear()
            raise
        finally:
            self.interactive_trace.clear()
            self.write_lock.release()
