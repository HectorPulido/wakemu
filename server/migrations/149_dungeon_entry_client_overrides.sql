-- Reviewed one-time import of the five existing projected native entrances.
-- Source catalog is immutable provenance, not the currently active revision.
INSERT INTO settings(name,value) VALUES ('dungeon_entry_client_overrides',
$reviewed${
  "version": 1,
  "native_client_sha256": "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd",
  "source_catalog_revision": "a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38",
  "projection_sha256": "05dcc274bfc2910ef0ada9deecabab7e26041efc9b524987e74ac76bc1555631",
  "entrances": [
    {
      "destination_id": 720,
      "criterion": "(not IsNeoServer())"
    },
    {
      "destination_id": 4578,
      "criterion": "(not IsNeoServer())"
    },
    {
      "destination_id": 4689,
      "criterion": "(IsNeoServer() or not IsNeoServer())"
    },
    {
      "destination_id": 4714,
      "criterion": "(IsNeoServer() or not IsNeoServer())"
    },
    {
      "destination_id": 4751,
      "criterion": "(not ((not IsNeoServer()) or (not (GetGlobalVariable(\"NEO_BOSS_UNLOCKED\") >= 8))))"
    }
  ]
}$reviewed$::jsonb) ON CONFLICT(name) DO NOTHING;
