import struct
import unittest
from wakfu_server.combat_effects import direct_damage
from wakfu_server.combat_effect_removal import (
    running_effect_removal,
    EFFECT_UNAPPLICATION_OPCODE,
)


class EffectRemovalTests(unittest.TestCase):
    def payload(self):
        create = direct_damage(
            7,
            8,
            uid=1234,
            generic_effect=348703,
            element=1,
            caster_id=22,
            target_id=-33,
            damage=5,
        )
        return create[19:]

    def removal(self, **overrides):
        values = dict(
            effect_class=1,
            target_id=-33,
            uid=1234,
            running_effect_payload=self.payload(),
        )
        values.update(overrides)
        return running_effect_removal(7, 9, **values)

    def test_preserves_owned_proto_and_targets_uid(self):
        body = self.removal()
        self.assertEqual(EFFECT_UNAPPLICATION_OPCODE, 13560)
        self.assertEqual(
            struct.unpack(">iiiih", body[:18]), (7, 9, -1, 1, len(self.payload()))
        )
        self.assertEqual(body[18:-16], self.payload())
        self.assertEqual(struct.unpack(">qq", body[-16:]), (-33, 1234))

    def test_refuses_changed_identity_and_incomplete_proto(self):
        for args in [
            dict(uid=1235),
            dict(target_id=-34),
            dict(running_effect_payload=b""),
            dict(running_effect_payload=b"\x08\xd2\x09"),
            dict(running_effect_payload=self.payload() + b"\x08\x01"),
        ]:
            with self.assertRaises(ValueError):
                self.removal(**args)

    def test_child_removal_preserves_container_and_execution_metadata(self):
        from wakfu_server.combat_effects import _integer, _varint

        # Removing a child must keep its state-container identity. Rebuilding
        # a minimal proto would lose PL even when UID/owner remain correct.
        timing = _integer(2, 0) + _integer(5, 1)
        for container_type in (1, 3, 11, 12):
            with self.subTest(container_type=container_type):
                original = (
                    self.payload()
                    + _integer(9, container_type)
                    + _integer(10, (3442 << 16) | 20)
                    + b"\x5a"
                    + _varint(len(timing))
                    + timing
                )
                removed = self.removal(running_effect_payload=original)
                self.assertEqual(removed[18:-16], original)
                self.assertEqual(struct.unpack(">qq", removed[-16:]), (-33, 1234))

    def test_refuses_truncated_and_invalid_bounds(self):
        for args in [
            dict(running_effect_payload=self.payload()[:-1]),
            dict(uid=True),
            dict(effect_class=0),
            dict(sequence=-2),
            dict(target_id=0),
        ]:
            with self.assertRaises(ValueError):
                self.removal(**args)

    def test_state310_validates_actual_additional_uid(self):
        from wakfu_server.combat_effects import _integer, _varint

        # Parent apply304 and state carrier310 have separate owned UIDs.
        original = b"".join(
            _integer(k, v)
            for k, v in [(1, 2345), (2, 1234), (3, 348703), (4, 5), (6, 22), (7, -33)]
        )
        for nested_uid in [2345, 1234, None]:
            additional = _integer(10, 5)
            if nested_uid is not None:
                additional += _integer(13, nested_uid)
            proto = original + b"\x42" + _varint(len(additional)) + additional
            values = dict(effect_class=310, uid=2345, running_effect_payload=proto)
            if nested_uid == 2345:
                self.assertEqual(
                    struct.unpack(">q", self.removal(**values)[-8:])[0], 2345
                )
            else:
                with self.assertRaises(ValueError):
                    self.removal(**values)
        with self.assertRaises(ValueError):
            self.removal(effect_class=310, uid=2345, running_effect_payload=original)

    def test_state310_refuses_duplicate_additional_uid(self):
        from wakfu_server.combat_effects import _integer, _varint

        original = b"".join(
            _integer(k, v)
            for k, v in [(1, 2345), (2, 1234), (3, 348703), (4, 5), (6, 22), (7, -33)]
        )
        additional = _integer(10, 5) + _integer(13, 2345) + _integer(13, 1234)
        proto = original + b"\x42" + _varint(len(additional)) + additional
        with self.assertRaises(ValueError):
            self.removal(effect_class=310, uid=2345, running_effect_payload=proto)
