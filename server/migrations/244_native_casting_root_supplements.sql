-- Additive source-exported casting metadata; immutable catalog rows stay unchanged.
-- Revision matching is enforced by the reader. Isolated schemas need no release seed.
CREATE TABLE IF NOT EXISTS native_casting_root_supplements (
 catalog_revision text NOT NULL CHECK(catalog_revision ~ '^[0-9a-f]{64}$'),
 root_id integer NOT NULL CHECK(root_id > 0),
 source_spell_references integer[] NOT NULL CHECK(cardinality(source_spell_references)>0),
 source_jar_sha256 text NOT NULL CHECK(source_jar_sha256 ~ '^[0-9a-f]{64}$'),
 export_sha256 text NOT NULL CHECK(export_sha256 ~ '^[0-9a-f]{64}$'),
 exporter_sha256 text NOT NULL CHECK(exporter_sha256 ~ '^[0-9a-f]{64}$'),
 metadata jsonb NOT NULL CHECK(
   jsonb_typeof(metadata)='object'
   AND metadata ?& ARRAY['native_casting_collision_area','native_selector_present','native_target_selector']
   AND metadata - ARRAY['native_casting_collision_area','native_selector_present','native_target_selector']='{}'::jsonb
   AND jsonb_typeof(metadata->'native_selector_present')='boolean'
   AND jsonb_typeof(metadata->'native_casting_collision_area') IN ('null','object')
   AND jsonb_typeof(metadata->'native_target_selector') IN ('null','object')
   AND (metadata->>'native_selector_present')::boolean = (metadata->'native_target_selector'<>'null'::jsonb)),
 PRIMARY KEY(catalog_revision,root_id)
);

-- Original eVn.fKX/aZF export, separate from its aZP application geometry.
INSERT INTO native_casting_root_supplements
 (catalog_revision,root_id,source_spell_references,source_jar_sha256,export_sha256,exporter_sha256,metadata)
VALUES
 ('b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',401997,ARRAY[8460],
  'e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd',
  '7c715456f6eab830b2ee24456eb09ee115683da3cf1ac2503c40fe36d9a2aab6',
  '2fcb3e699b9ba8efb29de4aab519f83550f6b5fe842d4b4f16bb9a088f75f448',
  '{"native_casting_collision_area":null,"native_selector_present":true,"native_target_selector":{"class":"fcE","mask":1266637395197957}}'),
 ('b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',402030,ARRAY[8460],
  'e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd',
  '7c715456f6eab830b2ee24456eb09ee115683da3cf1ac2503c40fe36d9a2aab6',
  '2fcb3e699b9ba8efb29de4aab519f83550f6b5fe842d4b4f16bb9a088f75f448',
  '{"native_casting_collision_area":null,"native_selector_present":true,"native_target_selector":{"class":"fcE","mask":140737488363540}}')
ON CONFLICT(catalog_revision,root_id) DO NOTHING;
