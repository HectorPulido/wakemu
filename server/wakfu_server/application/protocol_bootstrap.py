"""Application domain helpers extracted from the World bootstrap."""

import base64
import ipaddress
import os
import struct


class ProtocolBootstrap:
    def __init__(self, runtime):
        self.runtime = runtime

    def pack_text(self, value, width="I"):
        data = value.encode()
        return struct.pack(">" + width, len(data)) + data

    def send_shop_authentication(
        self, connection, service, account_id, generation, *, language=None
    ):
        """Issue the native shop key for initial login or an explicit renewal."""
        if language is not None:
            parts = language.replace("_", "-").split("-")
            if (
                not language.isascii()
                or not 2 <= len(language) <= 16
                or not 2 <= len(parts[0]) <= 3
                or not parts[0].isalpha()
                or any(
                    not 2 <= len(part) <= 8 or not part.isalnum() for part in parts[1:]
                )
            ):
                raise ValueError("Invalid shop request language")
        if account_id is None or not self.runtime.STORE.current_session(
            account_id, generation
        ):
            raise ValueError("Shop authentication requires a current game session")
        shop_key = self.runtime.STORE.issue_token(
            account_id, "api", ttl=86400, generation=generation
        )
        if not self.runtime.STORE.current_session(account_id, generation):
            self.runtime.STORE.revoke_token(shop_key)
            raise ValueError("Shop authentication session changed before delivery")
        self.runtime.send(
            connection,
            service,
            22995,
            self.runtime.pack_text(shop_key)
            + struct.pack(">q", int((self.runtime.STORE.clock() + 86400) * 1000)),
        )
        self.runtime.record(
            event="shop_authentication_key_sent",
            account_id=account_id,
            renewal=language is not None,
            language=language,
        )

    def realms_local(self, body):
        """Keep realm metadata and advertise the configured emulator endpoint."""
        address = ipaddress.IPv4Address(
            os.environ.get("WAKFU_ADVERTISE_HOST", "127.0.0.1")
        )
        port = int(os.environ.get("WAKFU_ADVERTISE_WORLD_PORT", "15556"))
        if address.is_unspecified or address.is_multicast or not 1 <= port <= 65535:
            raise ValueError("Invalid advertised game endpoint")
        host = str(address)
        r = self.runtime.Reader(body)
        realms = []
        for _ in range(r.number("i")):
            start = r.pos
            realm_id = r.number("i")
            if r.number("B"):
                r.take(4)
            r.text("B")
            for _ in range(r.number("B")):
                r.take(1)
                r.text("B")
            r.take(4)
            if r.number("B"):
                r.take(4)
            host_start = r.pos
            r.text("I")
            for _ in range(r.number("i")):
                r.take(4)
            host_end = r.pos
            r.take(1 + 4 + 1 + 4 + 1)
            if realm_id == 10:
                realm = (
                    body[start:host_start]
                    + self.runtime.pack_text(host)
                    + struct.pack(">ii", 1, port)
                    + body[host_end : r.pos]
                )
                realms.append(realm)
        configs = []
        for _ in range(r.number("i")):
            start = r.pos
            realm_id = r.number("i")
            r.take(r.number("i"))
            r.take(r.number("i"))
            r.take(1)
            if realm_id == 10:
                configs.append(body[start : r.pos])
        flags = r.take(1)
        r.finish()
        assert len(realms) == len(configs) == 1
        result = (
            struct.pack(">i", 1) + realms[0] + struct.pack(">i", 1) + configs[0] + flags
        )
        assert b"ankama" not in result and host.encode() in result
        return result

    def fixture(self, opcode):
        return base64.b64decode(
            next(
                frame["body_base64"]
                for frame in self.runtime.FRAMES
                if frame["direction"] == "in" and frame["opcode"] == opcode
            )
        )

    def character_list_local(self, body):
        r = self.runtime.Reader(body)
        characters = [r.take(r.number("I")) for _ in range(r.number("B"))]
        pekebu = [
            blob
            for blob in characters
            if self.runtime.wire.TEMPLATE_NAME.encode("utf-8") in blob
        ]
        assert len(pekebu) == 1
        return b"\x01" + struct.pack(">I", len(pekebu[0])) + pekebu[0] + body[r.pos :]

    def player_template(self):
        r = self.runtime.Reader(self.runtime.fixture(12608))
        r.take(1)
        for _ in range(r.number("B")):
            actor_type, actor_id = r.number("B"), r.number("q")
            blob = r.take(r.number("H"))
            if actor_type == 0 and actor_id == self.runtime.wire.TEMPLATE_CHARACTER:
                return blob
        raise ValueError("Missing player appearance template")

    def owned_hero_template(self):
        """Use the owned entity format with spellbook, decks and shortcuts."""
        reader = self.runtime.Reader(self.runtime.fixture(12666))
        count = reader.number("H")
        reader.take(count * 8)
        entity = reader.take(reader.number("I"))
        if not entity or entity[0] != 10:
            raise ValueError("Missing native owned hero entity template")
        return entity
