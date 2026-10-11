import struct
import unittest

from wakfu_server.maps.admin_chat_rights import project_account_information


class AdminChatRightsTests(unittest.TestCase):
    def test_admin_grants_only_native_chat_permission_and_preserves_tail(self):
        words = [1, 2, 3, 0x80000001, 9]
        body = struct.pack(">H5I", 5, *words) + b"\x00native-tail\xff"
        result = project_account_information(body, is_admin=True)
        expected = words.copy()
        expected[3] |= 0x4000
        self.assertEqual(result, struct.pack(">H5I", 5, *expected) + body[22:])
        self.assertEqual(project_account_information(result, is_admin=True), result)

    def test_ordinary_account_clears_fixture_chat_permission_only(self):
        body = struct.pack(">H4I", 4, 7, 8, 9, 0x80004001) + b"tail"
        self.assertEqual(
            project_account_information(body, is_admin=False),
            struct.pack(">H4I", 4, 7, 8, 9, 0x80000001) + b"tail",
        )

    def test_short_rights_expand_only_for_authorized_admin(self):
        body = b"\x00\x00tail"
        self.assertEqual(project_account_information(body, is_admin=False), body)
        self.assertEqual(
            project_account_information(body, is_admin=True),
            struct.pack(">H4I", 4, 0, 0, 0, 0x4000) + b"tail",
        )

    def test_malformed_section_or_untrusted_role_is_rejected(self):
        for body, role in [
            (b"", True),
            (b"\x00", False),
            (b"\x00\x02abcd", True),
            (b"\x00\x00", 1),
            (bytearray(b"\x00\x00"), True),
        ]:
            with self.subTest(body=body, role=role), self.assertRaises(ValueError):
                project_account_information(body, is_admin=role)
