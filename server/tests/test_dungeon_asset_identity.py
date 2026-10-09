"""Native map bootstrap must not expose server-private dungeon run IDs."""

import struct
import unittest

from wakfu_server.native_transports import bootstrap


class DungeonAssetIdentityTests(unittest.TestCase):
    def test_private_run_id_does_not_replace_client_asset_map(self):
        character = dict(
            id=7,
            account_id=9,
            map_id=1086,
            instance_id=144115188075855873,
            x=1,
            y=2,
            z=0,
        )
        body = bootstrap(character)[1][1]
        entity_size = struct.unpack_from(">H", body)[0]
        self.assertEqual(entity_size, 56)
        entity = body[2 : 2 + entity_size]
        self.assertEqual(struct.unpack_from(">q", entity, 28)[0], 1086)
        other_run = dict(character, instance_id=144115188075855874)
        self.assertEqual(bootstrap(other_run), bootstrap(character))

    def test_asset_map_changes_independently_of_private_run(self):
        character = dict(
            id=7,
            account_id=9,
            map_id=1086,
            instance_id=144115188075855873,
            x=1,
            y=2,
            z=0,
        )
        body = bootstrap(dict(character, map_id=1459))[1][1]
        self.assertEqual(struct.unpack_from(">q", body, 30)[0], 1459)
