"""Authenticated native party requests and cross-map roster publication.

Only social mutations are serialized here; SQL and delivery never hold the
world membership lock. Combat state is read, never changed by this adapter.
"""
import threading
from contextlib import contextmanager

from . import party_snapshot, party_wire, player_parties


class PartySnapshotUnavailable(ValueError):
    """A live fight has not published this member's authoritative snapshot yet."""

    def __init__(self, party_id, character_id, fight_id):
        super().__init__("Current party fight snapshot is unavailable")
        self.party_id = party_id
        self.character_id = character_id
        self.fight_id = fight_id

    def diagnostic(self):
        return dict(
            party_id=self.party_id,
            character_id=self.character_id,
            fight_id=self.fight_id,
        )


class Parties:
    def __init__(self, store, world):
        self.store = store
        self.world = world
        # Bounded serialization by party, independent of world/combat locks.
        self.locks = [threading.RLock() for _ in range(1024)]

    def _key(self, character_id):
        with self.store.connection() as db:
            member = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s",
                (character_id,),
            ).fetchone()
        return (1, member["party_id"]) if member else (0, character_id)

    @contextmanager
    def _guard(self, character_id):
        while True:
            key = self._key(character_id)
            lock = self.locks[hash(key) % len(self.locks)]
            lock.acquire()
            try:
                if self._key(character_id) == key:
                    break
            except BaseException:
                lock.release()
                raise
            lock.release()
        try:
            yield
        finally:
            lock.release()

    def _authorize(self, account_id, generation, character_id):
        live = self.world.live_identity(character_id=character_id)
        if (
            live is None
            or live[0] != generation
            or live[1]["account_id"] != account_id
            or not self.store.current_character_session(
                account_id, generation, character_id
            )
        ):
            raise ValueError("La sesión del grupo ya no está activa.")
        return live[1]

    def _publish(self, party_id):
        """Read the latest roster, including effective levels and checkpoint HP."""
        with self.store.connection() as db:
            party = db.execute(
                "SELECT * FROM player_parties WHERE id=%s FOR UPDATE", (party_id,)
            ).fetchone()
            if party is None:
                return False
            rows = db.execute(
                "SELECT c.id,c.account_id,c.name,c.level,c.hp,c.max_hp,c.breed,c.sex,c.health_dead,c.hp_zero_valid "
                "FROM player_party_members m JOIN characters c ON c.id=m.character_id "
                "WHERE m.party_id=%s ORDER BY m.joined_order",
                (party_id,),
            ).fetchall()
            from wakfu_server.characters.heroes import augment_party

            rows = augment_party(db, self.store, rows)
            members, levels, fighting = [], {}, set()
            owner_snapshots = {}
            recipients = []
            for row in rows:
                member = dict(row)
                current = self.store.character(member["account_id"], member["id"], db)
                owner_snapshots[member["id"]] = current
                levels[member["id"]] = current["effective_level"]
                member.update(
                    hp=current["hp"],
                    max_hp=current["max_hp"],
                    health_dead=current["health_dead"],
                    hp_zero_valid=current.get("hp_zero_valid", False),
                    level=current["level"],
                )
                active = db.execute(
                    "SELECT f.id,k.snapshot FROM combat_fight_participants p "
                    "JOIN combat_fights f ON f.id=p.fight_id "
                    "LEFT JOIN fight_checkpoints k ON k.fight_id=f.id AND k.status='active' "
                    "WHERE p.character_id=%s AND f.status IN ('placement','active') "
                    "ORDER BY f.id DESC LIMIT 1",
                    (member["id"],),
                ).fetchone()
                if active is not None:
                    fighting.add(member["id"])
                    checkpoint = active["snapshot"]
                    actor = (
                        None
                        if checkpoint is None
                        else checkpoint.get("actors", {}).get(str(member["id"]))
                    )
                    if actor is None:
                        raise PartySnapshotUnavailable(
                            party_id, member["id"], active["id"]
                        )
                    if actor is not None:
                        member.update(
                            hp=actor["hp"],
                            max_hp=actor["max_hp"],
                            health_dead=actor["hp"] == 0,
                        )
                        levels[member["id"]] = actor["effective_level"]
                members.append(member)
                live = self.world.live_identity(character_id=member["id"])
                if live is not None:
                    lease = db.execute(
                        "SELECT 1 FROM sessions WHERE character_id=%s AND generation=%s AND expires_at>%s",
                        (member["id"], live[0], self.store.now()),
                    ).fetchone()
                    if lease is not None:
                        recipients.append((member["id"], live[0]))
            from wakfu_server import companions

            for owner in rows:
                if owner.get("hero_main_id") is not None:
                    continue
                raw = {
                    row["id"]: row
                    for row in companions.roster(db, owner["account_id"], owner["id"])
                }
                if not raw:
                    continue
                current = owner_snapshots[owner["id"]]
                for source in companions.combat_sources(
                    db,
                    owner["account_id"],
                    owner["id"],
                    owner_character=current,
                    store=self.store,
                ):
                    companion_id = source["id"]
                    party_identity = -companion_id
                    native_record = dict(
                        raw[companion_id], hp=source["hp"], max_hp=source["max_hp"]
                    )
                    effective_level = source["level"]
                    active = db.execute(
                        "SELECT f.id,k.snapshot FROM combat_fight_companions c "
                        "JOIN combat_fights f ON f.id=c.fight_id "
                        "LEFT JOIN fight_checkpoints k ON k.fight_id=f.id AND k.status='active' "
                        "WHERE c.companion_id=%s AND f.status IN ('placement','active') "
                        "ORDER BY f.id DESC LIMIT 1",
                        (companion_id,),
                    ).fetchone()
                    if active is not None:
                        checkpoint = active["snapshot"]
                        actor = (
                            None
                            if checkpoint is None
                            else checkpoint.get("actors", {}).get(str(companion_id))
                        )
                        if actor is None:
                            raise PartySnapshotUnavailable(
                                party_id, companion_id, active["id"]
                            )
                        native_record.update(hp=actor["hp"], max_hp=actor["max_hp"])
                        effective_level = actor["effective_level"]
                        fighting.add(party_identity)
                    levels[party_identity] = effective_level
                    members.append(
                        companions.party_member(
                            native_record,
                            account_id=owner["account_id"],
                            effective_level=effective_level,
                            in_fight=party_identity in fighting,
                        )
                    )
            packet = party_snapshot.packet(
                dict(party_id=party_id, leader_id=party["leader_id"], members=members),
                effective_levels=levels,
                fighting_ids=fighting,
            )
        for identity, generation in recipients:
            self.world.send_to(identity, generation, *packet)
        return True

    def refresh(self, account_id, generation, character_id):
        with self._guard(character_id):
            self._authorize(account_id, generation, character_id)
            snapshot = player_parties.snapshot(
                self.store, account_id, generation, character_id
            )
            if snapshot is None:
                from wakfu_server.characters.heroes import ensure_company_party

                ensure_company_party(self.store, account_id, generation, character_id)
                snapshot = player_parties.snapshot(
                    self.store, account_id, generation, character_id
                )
            return False if snapshot is None else self._publish(snapshot["party_id"])

    def handle(self, opcode, body, account_id, generation, character_id):
        request = party_wire.invitation_answer(body) if opcode == 1031 else None
        # Acceptance belongs to the inviter's current party, including its
        # initial creation. Other actions serialize on the actor's party.
        anchor = request["inviter_id"] if request is not None else character_id
        with self._guard(anchor):
            sender = self._authorize(account_id, generation, character_id)
            if opcode == 1156:
                request = party_wire.invitation_request(body)
                target = self.world.live_identity(
                    character_id=request.get("target_id"),
                    name=request.get("target_name"),
                )
                if target is None:
                    raise ValueError("El jugador no está conectado.")
                token = player_parties.invite(
                    self.store, account_id, generation, character_id, target[1]["id"]
                )
                with self.store.connection() as db:
                    pending = db.execute(
                        "SELECT invitee_generation FROM player_party_invitations WHERE token=%s",
                        (token,),
                    ).fetchone()
                try:
                    if pending is None or pending["invitee_generation"] != target[0]:
                        raise ValueError("La sesión del invitado cambió.")
                    if not self.world.send_to(
                        target[1]["id"],
                        target[0],
                        *party_wire.invitation(character_id, sender["name"])
                    ):
                        raise ValueError("No se pudo entregar la invitación.")
                except ValueError:
                    with self.store.connection() as db:
                        db.execute(
                            "DELETE FROM player_party_invitations WHERE token=%s AND inviter_generation=%s",
                            (token, generation),
                        )
                    raise
                return None
            if opcode == 1031:
                party_id = player_parties.answer_native(
                    self.store, account_id, generation, character_id, request
                )
                if party_id is not None:
                    self._publish(party_id)
                return party_id
            if opcode in (1074, 1066):
                request = party_wire.member_request(body)
                before = player_parties.snapshot(
                    self.store, account_id, generation, character_id
                )
                if before is None or before["party_id"] != request["group_id"]:
                    raise ValueError("No perteneces a ese grupo.")
                recipients = [
                    self.world.live_identity(character_id=row["id"])
                    for row in before["members"]
                ]
                result = player_parties.change_member(
                    self.store,
                    account_id,
                    generation,
                    character_id,
                    request["group_id"],
                    request["member_id"],
                    transfer=opcode == 1066,
                )
                if result["removed"]:
                    packet = party_wire.removed(result["party_id"], result["removed"])
                    for live in recipients:
                        if live is not None:
                            self.world.send_to(live[1]["id"], live[0], *packet)
                self._publish(result["party_id"])
                return result
            raise ValueError("Unknown player party request")

    def refresh_online(self):
        """Repair missed publications and refresh changing HP/build/fight state."""
        live = {row["id"] for row in self.world.snapshot()}
        if not live:
            return dict(refreshed=0, deferred=[])
        deferred = {}
        refreshed = set()
        with self.store.connection() as db:
            missing = db.execute(
                "SELECT r.leader_id FROM account_hero_rosters r "
                "WHERE r.leader_id=ANY(%s) "
                "AND EXISTS(SELECT 1 FROM account_hero_slots s WHERE s.account_id=r.account_id) "
                "AND NOT EXISTS(SELECT 1 FROM player_party_members m WHERE m.character_id=r.leader_id)",
                (list(live),),
            ).fetchall()
        for row in missing:
            current = self.world.live_identity(character_id=row["leader_id"])
            if current is not None:
                try:
                    self.refresh(current[1]["account_id"], current[0], row["leader_id"])
                except PartySnapshotUnavailable as error:
                    deferred[error.party_id] = error.diagnostic()
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT party_id,min(character_id) AS anchor FROM player_party_members "
                "WHERE character_id=ANY(%s) GROUP BY party_id",
                (list(live),),
            ).fetchall()
        for row in rows:
            try:
                with self._guard(row["anchor"]):
                    if self._publish(row["party_id"]):
                        refreshed.add(row["party_id"])
                        deferred.pop(row["party_id"], None)
            except PartySnapshotUnavailable as error:
                # Keep the current native checkpoint guard closed for this
                # party while allowing unrelated parties to refresh normally.
                deferred[error.party_id] = error.diagnostic()
        player_parties.expire(self.store)
        return dict(refreshed=len(refreshed), deferred=list(deferred.values()))

    def publish_character_deletion(self, change):
        """Publish a roster removal after an offline character is deleted."""
        if change is None:
            return
        packet = party_wire.removed(change["party_id"], change["removed"])
        for character_id in change["previous_members"]:
            if character_id == change["deleted_character_id"]:
                continue
            live = self.world.live_identity(character_id=character_id)
            if live is not None:
                self.world.send_to(live[1]["id"], live[0], *packet)
        if change["remaining"]:
            self._publish(change["party_id"])
