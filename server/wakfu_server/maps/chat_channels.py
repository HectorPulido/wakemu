"""Native public/party chat with authoritative identities and recipients."""
import struct
from wakfu_server.characters.nation_state import load as load_nation


def payload(account_id, character, text, *, language_mask, community):
    name, content = character["name"].encode("utf-8"), text.encode("utf-8")
    if (
        type(account_id) is not int
        or not 0 < account_id < 2**63
        or not 1 <= len(name) <= 127
        or not 1 <= len(content) <= 2048
        or type(language_mask) is not int
        or not 1 <= language_mask <= 15
        or type(community) is not int
        or not 1 <= community <= 4
    ):
        raise ValueError("Invalid channel chat payload")
    return (
        bytes((len(name),))
        + name
        + struct.pack(">BBqB", language_mask, community, account_id, 0)
        + struct.pack(">h", len(content))
        + content
    )


class Channels:
    def __init__(self, store, world):
        self.store = store
        self.world = world

    def minimum_interval(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE name='chat_channel_policy'"
            ).fetchone()
        value = (
            row["value"].get("minimum_interval_ms")
            if row is not None and type(row["value"]) is dict
            else None
        )
        if type(value) is not int or not 1 <= value <= 60000:
            raise ValueError("Invalid channel chat rate policy")
        return value / 1000

    def handle(self, opcode, request, account_id, generation, character_id):
        if opcode not in (13074, 13224, 13188, 13831, 12116, 13702, 12387):
            raise ValueError("Unsupported chat channel")
        live = self.world.live_identity(character_id=character_id)
        if live is None or live[0] != generation or live[1]["account_id"] != account_id:
            raise ValueError("Chat sender session is stale")
        if type(request.get("text")) is not str:
            raise ValueError("Invalid channel chat text")
        text = request["text"].strip()
        if not text or "\x00" in text:
            raise ValueError("Invalid channel chat text")
        # Console commands only execute through the existing authenticated
        # local-chat command dispatcher, never through another chat channel.
        if text.startswith("!"):
            raise ValueError("Usa el canal local para los comandos de pruebas.")
        with self.store.connection() as db:
            self.store.lock_character(db, account_id, generation, character_id)
            row = db.execute(
                "SELECT value FROM settings WHERE name='chat_channel_policy'"
            ).fetchone()
            policy = None if row is None else row["value"]
            if (
                type(policy) is not dict
                or type(policy.get("version")) is not int
                or policy["version"] != 1
                or type(policy.get("maximum_bytes")) is not int
                or not 1 <= policy["maximum_bytes"] <= 2048
            ):
                raise ValueError("Invalid chat channel policy")
            if len(text.encode("utf-8")) > policy["maximum_bytes"]:
                raise ValueError("Chat message is too long")
            preferences = db.execute(
                "SELECT language_mask,community FROM account_chat_preferences WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            preferences = policy if preferences is None else preferences
            mask, community = preferences["language_mask"], preferences["community"]
            language = request.get("language_id") if opcode in (13188, 13831) else None
            if opcode in (13188, 13831):
                if (
                    type(language) is not int
                    or not 0 <= language <= 3
                    or not mask & (1 << language)
                ):
                    raise ValueError("El idioma no está habilitado para esta cuenta.")
            if opcode == 12116:
                admin = db.execute(
                    "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
                ).fetchone()
                if admin is None or not admin["is_admin"]:
                    raise ValueError(
                        "El canal administrativo requiere una cuenta administradora."
                    )
                identities = {
                    row["id"]
                    for row in db.execute(
                        "SELECT c.id FROM characters c JOIN accounts a ON a.id=c.account_id "
                        "WHERE a.is_admin"
                    )
                }
            elif opcode in (13702, 12387):
                nation_id = load_nation(db, character_id)
                identities = {
                    row["character_id"]
                    for row in db.execute(
                        "SELECT c.id AS character_id FROM characters c "
                        "LEFT JOIN character_chat_nations n ON n.character_id=c.id "
                        "WHERE COALESCE(n.nation_id,0)=%s",
                        (nation_id,),
                    )
                }
            elif opcode == 13224:
                membership = db.execute(
                    "SELECT party_id FROM player_party_members WHERE character_id=%s",
                    (character_id,),
                ).fetchone()
                if membership is None or request["group_id"] != membership["party_id"]:
                    raise ValueError("No perteneces a ese grupo.")
                identities = {
                    row["character_id"]
                    for row in db.execute(
                        "SELECT character_id FROM player_party_members WHERE party_id=%s",
                        (membership["party_id"],),
                    )
                }
            else:
                identities = None
            # Capture recipient leases before leaving the transaction. A
            # reconnect cannot redirect a packet to the replacement session.
            recipients = []
            for other in self.world.snapshot():
                if identities is not None and other["id"] not in identities:
                    continue
                if language is not None:
                    preference = db.execute(
                        "SELECT language_mask FROM account_chat_preferences WHERE account_id=%s",
                        (other["account_id"],),
                    ).fetchone()
                    recipient_mask = (
                        policy["language_mask"]
                        if preference is None
                        else preference["language_mask"]
                    )
                    if not recipient_mask & (1 << language):
                        continue
                peer = self.world.live_identity(character_id=other["id"])
                if peer is None:
                    continue
                if (
                    db.execute(
                        "SELECT 1 FROM sessions WHERE character_id=%s AND generation=%s AND expires_at>%s",
                        (other["id"], peer[0], self.store.now()),
                    ).fetchone()
                    is not None
                ):
                    recipients.append((other["id"], peer[0]))
            packet = payload(
                account_id, live[1], text, language_mask=mask, community=community
            )
            if opcode in (13188, 13831):
                packet = bytes((language,)) + packet
            if opcode == 12116:
                # NP prepends eEY.ADMIN_CHANNEL (0) to the common NQ body.
                packet = struct.pack(">i", 0) + packet
        response = {
            13074: 626,
            13224: 606,
            13188: 769,
            13831: 655,
            12116: 762,
            13702: 632,
            12387: 758,
        }[opcode]
        return sum(
            self.world.send_to(identity, lease, response, packet)
            for identity, lease in recipients
        )
