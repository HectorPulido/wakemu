-- Append source-guide cadences; never rewrite old policy rows or earned births.
-- Public guide recovery is explicit; this does not claim original client timers.
DO $$ BEGIN
 IF (SELECT count(*) FROM archmonster_spawn_cadences
     WHERE policy_version='wakemu.native-count-archmonster-world-birth-v1')<>61
    OR (SELECT count(*) FROM archmonster_spawn_cadences
        WHERE policy_version='wakemu.native-count-archmonster-world-birth-v1'
          AND authority_kind='SOURCE_DERIVED_PUBLIC')<>59
    OR (SELECT count(*) FROM archmonster_spawn_cadences c
        JOIN archmonster_spawn_sources s USING(source_key,scenario_id)
        WHERE c.policy_version='wakemu.native-count-archmonster-world-birth-v1'
          AND c.authority_kind='DECLARED_WAKEMU' AND c.cooldown_ms=14400000
          AND NOT s.blocked_by_membership
          AND ((c.scenario_id=-1043 AND s.monster_reference=4280)
            OR (c.scenario_id=-1022 AND s.monster_reference=4097)))<>2 THEN
  RAISE EXCEPTION 'Archmonster v1 cadence inventory differs from its qualified source';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM archmonster_spawn_active WHERE singleton
               AND policy_version='wakemu.native-count-archmonster-world-birth-v1') THEN
  RAISE EXCEPTION 'Archmonster cadence upgrade requires the existing v1 pointer';
 END IF;
END $$;

INSERT INTO archmonster_spawn_policy_versions
 (policy_version,policy_contract,cooldown_ms,member_count,authority,source_sha256)
SELECT 'wakemu.native-count-archmonster-world-birth-v2',policy_contract,cooldown_ms,member_count,
 'Append-only v2: all 61 named archmonster cadences from the public guide; original v1 and existing last-spawn deadlines remain immutable',
 '1ba39c6c627412771332813f427a8c03531000ee193c3d70318255c3ce19220b' FROM archmonster_spawn_policy_versions WHERE policy_version='wakemu.native-count-archmonster-world-birth-v1';

INSERT INTO archmonster_spawn_cadences
 (source_key,scenario_id,policy_version,cooldown_ms,authority_kind,provenance)
SELECT source_key,scenario_id,'wakemu.native-count-archmonster-world-birth-v2',cooldown_ms,authority_kind,provenance
FROM archmonster_spawn_cadences WHERE policy_version='wakemu.native-count-archmonster-world-birth-v1' AND scenario_id NOT IN(-1043,-1022);

INSERT INTO archmonster_spawn_cadences
 (source_key,scenario_id,policy_version,cooldown_ms,authority_kind,provenance) VALUES
 ('installed-environmental-source-v1',-1043,'wakemu.native-count-archmonster-world-birth-v2',9000000,'SOURCE_DERIVED_PUBLIC','{"authority_kind":"PUBLIC_GUIDE_EXACT_NAMED_ARCHMONSTER_CADENCE","cooldown_ms":9000000,"guide_name_fr":"Slek Sy","native_breed":4280,"native_min_level":98,"native_name_fr":"Le Slek Sy","provenance":{"clock_anchor":"last successful spawn","guide_published":"2026-06-20","guide_row":{"guide_max":103,"guide_min":98,"location":"Mont Zinit – Grotte Slek","name_fr":"Slek Sy","timer":"2H30"},"match":"Exact normalized tokens; optional French articles le/la/les/l-apostrophe removed explicitly, case/accents/apostrophe/whitespace normalized; unique candidate; roots unchanged","native_name_key":"content.7.4280","original_client_frequency_proven":false,"retrieved_at":"2026-10-22","url":"https://methodwakfu.com/pvm/les-archimonstres/"},"scenario_id":-1043,"source_artifact":".runtime/parallel-readiness-20261021/archmonster304-exact-public-cadence-overrides.json","source_artifact_sha256":"1ba39c6c627412771332813f427a8c03531000ee193c3d70318255c3ce19220b","source_key":"installed-environmental-source-v1"}'::jsonb);

INSERT INTO archmonster_spawn_cadences
 (source_key,scenario_id,policy_version,cooldown_ms,authority_kind,provenance) VALUES
 ('installed-environmental-source-v1',-1022,'wakemu.native-count-archmonster-world-birth-v2',3600000,'SOURCE_DERIVED_PUBLIC','{"authority_kind":"PUBLIC_GUIDE_EXACT_NAMED_ARCHMONSTER_CADENCE","cooldown_ms":3600000,"guide_name_fr":"Lartifice Explosive","native_breed":4097,"native_min_level":23,"native_name_fr":"Lartifice l''Explosive","provenance":{"clock_anchor":"last successful spawn","guide_published":"2026-06-20","guide_row":{"guide_max":28,"guide_min":23,"location":"Astrub – Égouts d’Astrub","name_fr":"Lartifice Explosive","timer":"1H"},"match":"Exact normalized tokens; optional French articles le/la/les/l-apostrophe removed explicitly, case/accents/apostrophe/whitespace normalized; unique candidate; roots unchanged","native_name_key":"content.7.4097","original_client_frequency_proven":false,"retrieved_at":"2026-10-22","url":"https://methodwakfu.com/pvm/les-archimonstres/"},"scenario_id":-1022,"source_artifact":".runtime/parallel-readiness-20261021/archmonster304-exact-public-cadence-overrides.json","source_artifact_sha256":"1ba39c6c627412771332813f427a8c03531000ee193c3d70318255c3ce19220b","source_key":"installed-environmental-source-v1"}'::jsonb);

DO $$ BEGIN
 IF (SELECT count(*) FROM archmonster_spawn_cadences
     WHERE policy_version='wakemu.native-count-archmonster-world-birth-v2'
       AND authority_kind='SOURCE_DERIVED_PUBLIC')<>61
    OR EXISTS(SELECT 1 FROM archmonster_spawn_cadences old
       LEFT JOIN archmonster_spawn_cadences fresh ON fresh.source_key=old.source_key
        AND fresh.scenario_id=old.scenario_id
        AND fresh.policy_version='wakemu.native-count-archmonster-world-birth-v2'
       WHERE old.policy_version='wakemu.native-count-archmonster-world-birth-v1'
        AND old.scenario_id NOT IN(-1043,-1022)
        AND (fresh.scenario_id IS NULL OR
          ROW(old.cooldown_ms,old.authority_kind,old.provenance)
            IS DISTINCT FROM ROW(fresh.cooldown_ms,fresh.authority_kind,fresh.provenance))) THEN
  RAISE EXCEPTION 'Archmonster v2 must preserve the 59 original public cadences';
 END IF;
END $$;

-- Keep enabled exactly as it was. Existing births retain their own policy,
-- cooldown_ms and cooldown_until_ms; runtime reads that immutable deadline first.
UPDATE archmonster_spawn_active
 SET policy_version='wakemu.native-count-archmonster-world-birth-v2'
 WHERE singleton;
