-- Dedicated private finite encounters, never public ecology population.
CREATE SEQUENCE objectives_challenge_instance_ids AS bigint START WITH 576460752303423489 MAXVALUE 648518346341351423 NO CYCLE;
CREATE SEQUENCE objectives_challenge_group_ids AS bigint START WITH 288230376151711745 MAXVALUE 360287970189639679 NO CYCLE;
CREATE TABLE objectives_challenge_profiles (
    key text PRIMARY KEY,
    definition jsonb NOT NULL CHECK(jsonb_typeof(definition)='object'),
    revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_challenge_runs (
    attempt_id text PRIMARY KEY CHECK(length(attempt_id)=32),
    owner_account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL REFERENCES characters(id),
    profile_key text NOT NULL REFERENCES objectives_challenge_profiles(key),
    profile_revision bigint NOT NULL,
    week_key text NOT NULL CHECK(week_key ~ '^\d{4}-\d{2}-\d{2}$'),
    bracket text NOT NULL,
    level integer NOT NULL CHECK(level BETWEEN 1 AND 200),
    group_level integer NOT NULL CHECK(group_level BETWEEN level AND 200),
    instance_id bigint NOT NULL UNIQUE,
    map_id integer NOT NULL CHECK(map_id>0),
    group_id bigint NOT NULL UNIQUE,
    roster jsonb NOT NULL CHECK(jsonb_typeof(roster)='array'),
    return_position jsonb NOT NULL CHECK(jsonb_typeof(return_position)='object'),
    anchor jsonb NOT NULL CHECK(jsonb_typeof(anchor)='array'),
    status text NOT NULL DEFAULT 'available' CHECK(status IN ('available','fighting','won','lost','abandoned')),
    fight_id integer UNIQUE REFERENCES combat_fights(id),
    turns integer CHECK(turns>0),
    winner_team integer CHECK(winner_team IN(0,1)),
    test_mode boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_at timestamptz,
    returned_at timestamptz,
    FOREIGN KEY(owner_account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE UNIQUE INDEX objectives_challenge_one_unreturned ON objectives_challenge_runs(character_id) WHERE returned_at IS NULL;
CREATE INDEX objectives_challenge_week ON objectives_challenge_runs(week_key,profile_key,bracket);

-- Curated native geometry 1086; enabled ordinary dungeon roster references.
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-001-020','{"key":"weekly-native-001-020","title":"Weekly native challenge: levels 1-20","enabled":true,"min_level":1,"max_level":20,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":1,"level":10,"count":1},{"ref_id":4,"level":10,"count":1},{"ref_id":5,"level":10,"count":1},{"ref_id":41,"level":10,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-021-040','{"key":"weekly-native-021-040","title":"Weekly native challenge: levels 21-40","enabled":true,"min_level":21,"max_level":40,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":87,"level":30,"count":1},{"ref_id":88,"level":30,"count":1},{"ref_id":90,"level":30,"count":1},{"ref_id":271,"level":30,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-041-060','{"key":"weekly-native-041-060","title":"Weekly native challenge: levels 41-60","enabled":true,"min_level":41,"max_level":60,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":4749,"level":51,"count":1},{"ref_id":94,"level":48,"count":1},{"ref_id":1274,"level":48,"count":1},{"ref_id":4510,"level":48,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-061-080','{"key":"weekly-native-061-080","title":"Weekly native challenge: levels 61-80","enabled":true,"min_level":61,"max_level":80,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":4731,"level":70,"count":1},{"ref_id":5104,"level":70,"count":1},{"ref_id":5111,"level":70,"count":1},{"ref_id":5113,"level":70,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-081-100','{"key":"weekly-native-081-100","title":"Weekly native challenge: levels 81-100","enabled":true,"min_level":81,"max_level":100,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":1779,"level":90,"count":1},{"ref_id":1828,"level":90,"count":1},{"ref_id":4909,"level":90,"count":1},{"ref_id":1825,"level":89,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-101-120','{"key":"weekly-native-101-120","title":"Weekly native challenge: levels 101-120","enabled":true,"min_level":101,"max_level":120,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":2367,"level":108,"count":1},{"ref_id":2368,"level":113,"count":1},{"ref_id":3007,"level":113,"count":1},{"ref_id":3009,"level":113,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-121-140','{"key":"weekly-native-121-140","title":"Weekly native challenge: levels 121-140","enabled":true,"min_level":121,"max_level":140,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":2827,"level":130,"count":1},{"ref_id":4887,"level":130,"count":1},{"ref_id":4888,"level":130,"count":1},{"ref_id":5468,"level":130,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-141-160','{"key":"weekly-native-141-160","title":"Weekly native challenge: levels 141-160","enabled":true,"min_level":141,"max_level":160,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":4779,"level":150,"count":1},{"ref_id":5037,"level":150,"count":1},{"ref_id":4778,"level":149,"count":1},{"ref_id":5035,"level":149,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-161-180','{"key":"weekly-native-161-180","title":"Weekly native challenge: levels 161-180","enabled":true,"min_level":161,"max_level":180,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":3394,"level":168,"count":1},{"ref_id":3396,"level":168,"count":1},{"ref_id":4922,"level":168,"count":1},{"ref_id":3398,"level":173,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);
INSERT INTO objectives_challenge_profiles(key,definition) VALUES('weekly-native-181-200','{"key":"weekly-native-181-200","title":"Weekly native challenge: levels 181-200","enabled":true,"min_level":181,"max_level":200,"map_id":1086,"anchor":[-11,-17,0],"roster":[{"ref_id":4203,"level":190,"count":1},{"ref_id":4204,"level":190,"count":1},{"ref_id":4205,"level":190,"count":1},{"ref_id":4208,"level":190,"count":1}],"source_route_key":"donjons-paturages-des-bouftous"}'::jsonb);

CREATE TABLE objectives_challenge_members (
    attempt_id text NOT NULL REFERENCES objectives_challenge_runs(attempt_id),
    character_id bigint NOT NULL REFERENCES characters(id),
    return_position jsonb NOT NULL CHECK(jsonb_typeof(return_position)='object'),
    PRIMARY KEY(attempt_id,character_id)
);
