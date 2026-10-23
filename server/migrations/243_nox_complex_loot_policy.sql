-- Explicit reconstructed eligibility; original complex expressions are absent.
-- Rules and whitelist are normalized database data, not runtime JSON files.
CREATE TABLE combat_complex_loot_policy_versions (
 version TEXT PRIMARY KEY,
 monster_reference INTEGER NOT NULL CHECK(monster_reference>0),
 encounter_controller TEXT NOT NULL,
 minimum_score BIGINT NOT NULL CHECK(minimum_score>=0),
 catalog_revision TEXT NOT NULL CHECK(length(catalog_revision)=64),
 native_rows_sha256 TEXT NOT NULL CHECK(length(native_rows_sha256)=64),
 expected_item_count INTEGER NOT NULL CHECK(expected_item_count>0),
 source_guide_url TEXT NOT NULL,source_guide_version TEXT NOT NULL,
 installed_release_evidence TEXT NOT NULL,authority TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(version,monster_reference)
);
CREATE TABLE combat_complex_loot_policy_items (
 version TEXT NOT NULL REFERENCES combat_complex_loot_policy_versions(version),
 item_reference INTEGER NOT NULL CHECK(item_reference>0),
 PRIMARY KEY(version,item_reference)
);
CREATE TABLE combat_complex_loot_policy_active (
 monster_reference INTEGER PRIMARY KEY,
 version TEXT NOT NULL,
 FOREIGN KEY(version,monster_reference) REFERENCES combat_complex_loot_policy_versions(version,monster_reference)
);
CREATE FUNCTION reject_complex_loot_policy_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Complex loot policy versions are immutable; append a reviewed version';
END;
$$;
CREATE TRIGGER immutable_complex_loot_policy_version BEFORE UPDATE OR DELETE ON combat_complex_loot_policy_versions
 FOR EACH ROW EXECUTE FUNCTION reject_complex_loot_policy_mutation();
CREATE TRIGGER immutable_complex_loot_policy_item BEFORE UPDATE OR DELETE ON combat_complex_loot_policy_items
 FOR EACH ROW EXECUTE FUNCTION reject_complex_loot_policy_mutation();
INSERT INTO combat_complex_loot_policy_versions(
 version,monster_reference,encounter_controller,minimum_score,catalog_revision,native_rows_sha256,
 expected_item_count,source_guide_url,source_guide_version,installed_release_evidence,authority
) VALUES(
 'wakemu-nox-scored-complex-loot-v1',5664,'wakemu-nox-score-1.92-v1',3000000,
 'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',
 '52480339c7c4810f2dcda7c3f08beeb23fc1734c77003c62e6064a956b3e8441',51,
 'https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/','1.92',
 'client/sentry.properties:1.93.1+79;client_manifest_sha1_verified',
 'explicit-reconstruction;original-complex-criterion-unrecovered;guide-and-package-versions-differ'
);
INSERT INTO combat_complex_loot_policy_items(version,item_reference) VALUES
 ('wakemu-nox-scored-complex-loot-v1',32473),
 ('wakemu-nox-scored-complex-loot-v1',32474),
 ('wakemu-nox-scored-complex-loot-v1',32475),
 ('wakemu-nox-scored-complex-loot-v1',32476),
 ('wakemu-nox-scored-complex-loot-v1',32477),
 ('wakemu-nox-scored-complex-loot-v1',32478),
 ('wakemu-nox-scored-complex-loot-v1',32479),
 ('wakemu-nox-scored-complex-loot-v1',32480),
 ('wakemu-nox-scored-complex-loot-v1',32481),
 ('wakemu-nox-scored-complex-loot-v1',32482),
 ('wakemu-nox-scored-complex-loot-v1',32483),
 ('wakemu-nox-scored-complex-loot-v1',32484),
 ('wakemu-nox-scored-complex-loot-v1',32485),
 ('wakemu-nox-scored-complex-loot-v1',32486),
 ('wakemu-nox-scored-complex-loot-v1',32487),
 ('wakemu-nox-scored-complex-loot-v1',32488),
 ('wakemu-nox-scored-complex-loot-v1',32489),
 ('wakemu-nox-scored-complex-loot-v1',32490),
 ('wakemu-nox-scored-complex-loot-v1',32491),
 ('wakemu-nox-scored-complex-loot-v1',32492),
 ('wakemu-nox-scored-complex-loot-v1',32493),
 ('wakemu-nox-scored-complex-loot-v1',32494),
 ('wakemu-nox-scored-complex-loot-v1',32495),
 ('wakemu-nox-scored-complex-loot-v1',32496),
 ('wakemu-nox-scored-complex-loot-v1',32497),
 ('wakemu-nox-scored-complex-loot-v1',32498),
 ('wakemu-nox-scored-complex-loot-v1',32499),
 ('wakemu-nox-scored-complex-loot-v1',32500),
 ('wakemu-nox-scored-complex-loot-v1',32501),
 ('wakemu-nox-scored-complex-loot-v1',32503),
 ('wakemu-nox-scored-complex-loot-v1',32504),
 ('wakemu-nox-scored-complex-loot-v1',32505),
 ('wakemu-nox-scored-complex-loot-v1',32506),
 ('wakemu-nox-scored-complex-loot-v1',32507),
 ('wakemu-nox-scored-complex-loot-v1',32508),
 ('wakemu-nox-scored-complex-loot-v1',32509),
 ('wakemu-nox-scored-complex-loot-v1',32510),
 ('wakemu-nox-scored-complex-loot-v1',32511),
 ('wakemu-nox-scored-complex-loot-v1',32512),
 ('wakemu-nox-scored-complex-loot-v1',32513),
 ('wakemu-nox-scored-complex-loot-v1',32514),
 ('wakemu-nox-scored-complex-loot-v1',32515),
 ('wakemu-nox-scored-complex-loot-v1',32516),
 ('wakemu-nox-scored-complex-loot-v1',32517),
 ('wakemu-nox-scored-complex-loot-v1',32518),
 ('wakemu-nox-scored-complex-loot-v1',32613),
 ('wakemu-nox-scored-complex-loot-v1',32614),
 ('wakemu-nox-scored-complex-loot-v1',32615),
 ('wakemu-nox-scored-complex-loot-v1',32616),
 ('wakemu-nox-scored-complex-loot-v1',32617),
 ('wakemu-nox-scored-complex-loot-v1',32618);
INSERT INTO combat_complex_loot_policy_active(monster_reference,version) VALUES(5664,'wakemu-nox-scored-complex-loot-v1');
