-- Source-backed weekly hunters. No automatic acceptance or NPC binding is seeded.
CREATE TABLE recurring_hunter_contracts (
 definition_id integer NOT NULL CHECK(definition_id>0), version integer NOT NULL CHECK(version>0),
 objective_id integer NOT NULL CHECK(objective_id>0), minimum_level integer NOT NULL CHECK(minimum_level>0),
 required_distinct integer NOT NULL CHECK(required_distinct>0), anchor_ms bigint NOT NULL CHECK(anchor_ms>=0),
 period_ms bigint NOT NULL CHECK(period_ms>0), cooldown_ms bigint NOT NULL CHECK(cooldown_ms>=0),
 interpretation_policy text NOT NULL, source_authority text NOT NULL,
 PRIMARY KEY(definition_id,version)
);
CREATE TABLE recurring_hunter_targets (
 definition_id integer NOT NULL, version integer NOT NULL, boss_reference integer NOT NULL CHECK(boss_reference>0),
 variable_name text NOT NULL, PRIMARY KEY(definition_id,version,boss_reference),
 UNIQUE(definition_id,version,variable_name),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_hunter_contracts
);
CREATE TABLE recurring_hunter_rewards (
 definition_id integer NOT NULL, version integer NOT NULL, reward_id integer NOT NULL CHECK(reward_id>0),
 native_type integer NOT NULL CHECK(native_type IN(5,6)), reference integer, amount integer NOT NULL CHECK(amount>0),
 native_flag boolean NOT NULL,
 PRIMARY KEY(definition_id,version,reward_id),
 CHECK((native_type=5 AND reference>0) OR (native_type=6 AND reference IS NULL)),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_hunter_contracts
);
-- Only separately recovered original acceptance actions may populate this table.
CREATE TABLE recurring_hunter_acceptance_sources (
 definition_id integer NOT NULL, version integer NOT NULL,
 source_kind text NOT NULL CHECK(source_kind IN('npc_dialogue','native_share')),
 source_reference bigint NOT NULL CHECK(source_reference>0), action_id integer NOT NULL CHECK(action_id>0),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(definition_id,version,source_kind,source_reference,action_id),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_hunter_contracts
);
CREATE TABLE recurring_hunter_acceptances (
 character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 definition_id integer NOT NULL, version integer NOT NULL, period_index bigint NOT NULL CHECK(period_index>=0),
 account_id bigint NOT NULL REFERENCES accounts(id), accepted_at_ms bigint NOT NULL CHECK(accepted_at_ms>=0),
 real_level integer NOT NULL CHECK(real_level>0), acceptance_event_key text NOT NULL,
 completed_at_ms bigint, expired_at_ms bigint,
 PRIMARY KEY(character_id,definition_id,period_index),
 UNIQUE(character_id,acceptance_event_key),
 UNIQUE(character_id,definition_id,period_index,version),
 FOREIGN KEY(definition_id,version) REFERENCES recurring_hunter_contracts,
 FOREIGN KEY(character_id,acceptance_event_key) REFERENCES character_achievement_events(character_id,event_key),
 CHECK(completed_at_ms IS NULL OR completed_at_ms>=accepted_at_ms)
);
CREATE TABLE recurring_hunter_victories (
 character_id bigint NOT NULL, definition_id integer NOT NULL, period_index bigint NOT NULL, version integer NOT NULL,
 fight_id bigint NOT NULL REFERENCES combat_fights(id), boss_reference integer NOT NULL,
 occurred_at_ms bigint NOT NULL, source_event_key text NOT NULL,
 PRIMARY KEY(character_id,definition_id,period_index,fight_id,boss_reference),
 FOREIGN KEY(character_id,definition_id,period_index,version) REFERENCES recurring_hunter_acceptances(character_id,definition_id,period_index,version),
 FOREIGN KEY(definition_id,version,boss_reference) REFERENCES recurring_hunter_targets,
 FOREIGN KEY(character_id,source_event_key) REFERENCES character_achievement_events(character_id,event_key)
);
CREATE INDEX recurring_hunter_current_owned ON recurring_hunter_acceptances(character_id) WHERE expired_at_ms IS NULL;
CREATE FUNCTION recurring_hunter_immutable_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Recurring hunter source versions are immutable'; END; $$;
CREATE TRIGGER recurring_hunter_contract_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_contracts FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TRIGGER recurring_hunter_target_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_targets FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TRIGGER recurring_hunter_reward_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_rewards FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();
CREATE TRIGGER recurring_hunter_acceptance_source_immutable BEFORE UPDATE OR DELETE ON recurring_hunter_acceptance_sources FOR EACH ROW EXECUTE FUNCTION recurring_hunter_immutable_source();

INSERT INTO recurring_hunter_contracts VALUES(3766,1,7774,1,3,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3766,1,1259,'hunterLevel006Boss1259');
INSERT INTO recurring_hunter_targets VALUES(3766,1,2157,'hunterLevel006Boss2157');
INSERT INTO recurring_hunter_targets VALUES(3766,1,4012,'hunterLevel006Boss4012');
INSERT INTO recurring_hunter_targets VALUES(3766,1,44,'hunterLevel006Boss44');
INSERT INTO recurring_hunter_rewards VALUES(3766,1,6697,5,12686,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3766,1,6696,6,NULL,103099,false);
INSERT INTO recurring_hunter_contracts VALUES(3765,1,7773,21,3,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3765,1,1187,'hunterLevel021Boss1187');
INSERT INTO recurring_hunter_targets VALUES(3765,1,3216,'hunterLevel021Boss3216');
INSERT INTO recurring_hunter_targets VALUES(3765,1,3780,'hunterLevel021Boss3780');
INSERT INTO recurring_hunter_targets VALUES(3765,1,3845,'hunterLevel021Boss3845');
INSERT INTO recurring_hunter_targets VALUES(3765,1,3893,'hunterLevel021Boss3893');
INSERT INTO recurring_hunter_targets VALUES(3765,1,4107,'hunterLevel021Boss4107');
INSERT INTO recurring_hunter_rewards VALUES(3765,1,6695,5,20672,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3765,1,6694,6,NULL,373337,false);
INSERT INTO recurring_hunter_contracts VALUES(3764,1,7772,36,3,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3764,1,1726,'hunterLevel036Boss1726');
INSERT INTO recurring_hunter_targets VALUES(3764,1,4519,'hunterLevel036Boss4519');
INSERT INTO recurring_hunter_targets VALUES(3764,1,4651,'hunterLevel036Boss4651');
INSERT INTO recurring_hunter_targets VALUES(3764,1,4758,'hunterLevel036Boss4758');
INSERT INTO recurring_hunter_targets VALUES(3764,1,5376,'hunterLevel036Boss5376');
INSERT INTO recurring_hunter_targets VALUES(3764,1,5382,'hunterLevel036Boss5382');
INSERT INTO recurring_hunter_rewards VALUES(3764,1,6693,5,20968,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3764,1,6692,6,NULL,1095187,false);
INSERT INTO recurring_hunter_contracts VALUES(3763,1,7771,51,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3763,1,4754,'hunterLevel051Boss4754');
INSERT INTO recurring_hunter_targets VALUES(3763,1,4731,'hunterLevel051Boss4731');
INSERT INTO recurring_hunter_targets VALUES(3763,1,2768,'hunterLevel051Boss2768');
INSERT INTO recurring_hunter_targets VALUES(3763,1,2774,'hunterLevel051Boss2774');
INSERT INTO recurring_hunter_targets VALUES(3763,1,4240,'hunterLevel051Boss4240');
INSERT INTO recurring_hunter_targets VALUES(3763,1,4244,'hunterLevel051Boss4244');
INSERT INTO recurring_hunter_targets VALUES(3763,1,5388,'hunterLevel051Boss5388');
INSERT INTO recurring_hunter_targets VALUES(3763,1,5445,'hunterLevel051Boss5445');
INSERT INTO recurring_hunter_rewards VALUES(3763,1,6691,5,21001,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3763,1,6690,6,NULL,2279403,false);
INSERT INTO recurring_hunter_contracts VALUES(3762,1,7770,66,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3762,1,5107,'hunterLevel066Boss5107');
INSERT INTO recurring_hunter_targets VALUES(3762,1,5114,'hunterLevel066Boss5114');
INSERT INTO recurring_hunter_targets VALUES(3762,1,4763,'hunterLevel066Boss4763');
INSERT INTO recurring_hunter_targets VALUES(3762,1,4871,'hunterLevel066Boss4871');
INSERT INTO recurring_hunter_targets VALUES(3762,1,2313,'hunterLevel066Boss2313');
INSERT INTO recurring_hunter_targets VALUES(3762,1,3587,'hunterLevel066Boss3587');
INSERT INTO recurring_hunter_targets VALUES(3762,1,3696,'hunterLevel066Boss3696');
INSERT INTO recurring_hunter_targets VALUES(3762,1,4918,'hunterLevel066Boss4918');
INSERT INTO recurring_hunter_rewards VALUES(3762,1,6689,5,21002,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3762,1,6688,6,NULL,3764294,false);
INSERT INTO recurring_hunter_contracts VALUES(3681,1,7613,81,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3681,1,2464,'hunterLevel081Boss2464');
INSERT INTO recurring_hunter_targets VALUES(3681,1,1786,'hunterLevel081Boss1786');
INSERT INTO recurring_hunter_targets VALUES(3681,1,1836,'hunterLevel081Boss1836');
INSERT INTO recurring_hunter_targets VALUES(3681,1,3735,'hunterLevel081Boss3735');
INSERT INTO recurring_hunter_targets VALUES(3681,1,4913,'hunterLevel081Boss4913');
INSERT INTO recurring_hunter_targets VALUES(3681,1,4739,'hunterLevel081Boss4739');
INSERT INTO recurring_hunter_targets VALUES(3681,1,2443,'hunterLevel081Boss2443');
INSERT INTO recurring_hunter_targets VALUES(3681,1,4251,'hunterLevel081Boss4251');
INSERT INTO recurring_hunter_targets VALUES(3681,1,3707,'hunterLevel081Boss3707');
INSERT INTO recurring_hunter_targets VALUES(3681,1,2710,'hunterLevel081Boss2710');
INSERT INTO recurring_hunter_rewards VALUES(3681,1,6501,5,21003,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3681,1,6500,6,NULL,6214766,false);
INSERT INTO recurring_hunter_contracts VALUES(3767,1,7775,96,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3767,1,1345,'hunterLevel096Boss1345');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2142,'hunterLevel096Boss2142');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2143,'hunterLevel096Boss2143');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2144,'hunterLevel096Boss2144');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2368,'hunterLevel096Boss2368');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2469,'hunterLevel096Boss2469');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2708,'hunterLevel096Boss2708');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2100,'hunterLevel096Boss2100');
INSERT INTO recurring_hunter_targets VALUES(3767,1,2363,'hunterLevel096Boss2363');
INSERT INTO recurring_hunter_targets VALUES(3767,1,4520,'hunterLevel096Boss4520');
INSERT INTO recurring_hunter_rewards VALUES(3767,1,6698,5,21004,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3767,1,6699,6,NULL,10690744,false);
INSERT INTO recurring_hunter_contracts VALUES(3768,1,7776,111,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3768,1,4720,'hunterLevel111Boss4720');
INSERT INTO recurring_hunter_targets VALUES(3768,1,2343,'hunterLevel111Boss2343');
INSERT INTO recurring_hunter_targets VALUES(3768,1,2348,'hunterLevel111Boss2348');
INSERT INTO recurring_hunter_targets VALUES(3768,1,2354,'hunterLevel111Boss2354');
INSERT INTO recurring_hunter_targets VALUES(3768,1,2827,'hunterLevel111Boss2827');
INSERT INTO recurring_hunter_targets VALUES(3768,1,2972,'hunterLevel111Boss2972');
INSERT INTO recurring_hunter_targets VALUES(3768,1,4231,'hunterLevel111Boss4231');
INSERT INTO recurring_hunter_targets VALUES(3768,1,4727,'hunterLevel111Boss4727');
INSERT INTO recurring_hunter_rewards VALUES(3768,1,6700,5,21005,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3768,1,6701,6,NULL,18746194,false);
INSERT INTO recurring_hunter_contracts VALUES(3769,1,7777,126,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3769,1,2556,'hunterLevel126Boss2556');
INSERT INTO recurring_hunter_targets VALUES(3769,1,5471,'hunterLevel126Boss5471');
INSERT INTO recurring_hunter_targets VALUES(3769,1,2570,'hunterLevel126Boss2570');
INSERT INTO recurring_hunter_targets VALUES(3769,1,2977,'hunterLevel126Boss2977');
INSERT INTO recurring_hunter_targets VALUES(3769,1,3048,'hunterLevel126Boss3048');
INSERT INTO recurring_hunter_targets VALUES(3769,1,3926,'hunterLevel126Boss3926');
INSERT INTO recurring_hunter_targets VALUES(3769,1,4254,'hunterLevel126Boss4254');
INSERT INTO recurring_hunter_targets VALUES(3769,1,4874,'hunterLevel126Boss4874');
INSERT INTO recurring_hunter_rewards VALUES(3769,1,6702,5,21006,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3769,1,6703,6,NULL,32957817,false);
INSERT INTO recurring_hunter_contracts VALUES(3770,1,7778,141,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3770,1,2582,'hunterLevel141Boss2582');
INSERT INTO recurring_hunter_targets VALUES(3770,1,2605,'hunterLevel141Boss2605');
INSERT INTO recurring_hunter_targets VALUES(3770,1,3080,'hunterLevel141Boss3080');
INSERT INTO recurring_hunter_targets VALUES(3770,1,3094,'hunterLevel141Boss3094');
INSERT INTO recurring_hunter_targets VALUES(3770,1,4060,'hunterLevel141Boss4060');
INSERT INTO recurring_hunter_targets VALUES(3770,1,4780,'hunterLevel141Boss4780');
INSERT INTO recurring_hunter_targets VALUES(3770,1,5040,'hunterLevel141Boss5040');
INSERT INTO recurring_hunter_targets VALUES(3770,1,5478,'hunterLevel141Boss5478');
INSERT INTO recurring_hunter_rewards VALUES(3770,1,6704,5,21007,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3770,1,6705,6,NULL,57979086,false);
INSERT INTO recurring_hunter_contracts VALUES(3771,1,7779,156,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3771,1,3398,'hunterLevel156Boss3398');
INSERT INTO recurring_hunter_targets VALUES(3771,1,3399,'hunterLevel156Boss3399');
INSERT INTO recurring_hunter_targets VALUES(3771,1,4217,'hunterLevel156Boss4217');
INSERT INTO recurring_hunter_targets VALUES(3771,1,2018,'hunterLevel156Boss2018');
INSERT INTO recurring_hunter_targets VALUES(3771,1,4924,'hunterLevel156Boss4924');
INSERT INTO recurring_hunter_targets VALUES(3771,1,4923,'hunterLevel156Boss4923');
INSERT INTO recurring_hunter_targets VALUES(3771,1,4538,'hunterLevel156Boss4538');
INSERT INTO recurring_hunter_rewards VALUES(3771,1,6706,5,21008,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3771,1,6707,6,NULL,101943413,false);
INSERT INTO recurring_hunter_contracts VALUES(3772,1,7780,171,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3772,1,3864,'hunterLevel171Boss3864');
INSERT INTO recurring_hunter_targets VALUES(3772,1,3865,'hunterLevel171Boss3865');
INSERT INTO recurring_hunter_targets VALUES(3772,1,3866,'hunterLevel171Boss3866');
INSERT INTO recurring_hunter_targets VALUES(3772,1,3971,'hunterLevel171Boss3971');
INSERT INTO recurring_hunter_targets VALUES(3772,1,5046,'hunterLevel171Boss5046');
INSERT INTO recurring_hunter_targets VALUES(3772,1,5131,'hunterLevel171Boss5131');
INSERT INTO recurring_hunter_rewards VALUES(3772,1,6708,5,19796,80,false);
INSERT INTO recurring_hunter_rewards VALUES(3772,1,6709,6,NULL,179032500,false);
INSERT INTO recurring_hunter_contracts VALUES(3301,1,7781,186,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(3301,1,4400,'hunterLevel186Boss4400');
INSERT INTO recurring_hunter_targets VALUES(3301,1,4260,'hunterLevel186Boss4260');
INSERT INTO recurring_hunter_targets VALUES(3301,1,4318,'hunterLevel186Boss4318');
INSERT INTO recurring_hunter_targets VALUES(3301,1,4327,'hunterLevel186Boss4327');
INSERT INTO recurring_hunter_targets VALUES(3301,1,4664,'hunterLevel186Boss4664');
INSERT INTO recurring_hunter_targets VALUES(3301,1,5052,'hunterLevel186Boss5052');
INSERT INTO recurring_hunter_targets VALUES(3301,1,5059,'hunterLevel186Boss5059');
INSERT INTO recurring_hunter_targets VALUES(3301,1,5137,'hunterLevel186Boss5137');
INSERT INTO recurring_hunter_rewards VALUES(3301,1,5589,6,NULL,261178422,false);
INSERT INTO recurring_hunter_rewards VALUES(3301,1,5588,5,21010,80,false);
INSERT INTO recurring_hunter_contracts VALUES(4786,1,9923,201,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5170,'hunterLevel201Boss5170');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5176,'hunterLevel201Boss5176');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5182,'hunterLevel201Boss5182');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5188,'hunterLevel201Boss5188');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5235,'hunterLevel201Boss5235');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5241,'hunterLevel201Boss5241');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5247,'hunterLevel201Boss5247');
INSERT INTO recurring_hunter_targets VALUES(4786,1,5229,'hunterLevel216Boss5229');
INSERT INTO recurring_hunter_rewards VALUES(4786,1,8980,6,NULL,392886372,false);
INSERT INTO recurring_hunter_rewards VALUES(4786,1,8979,5,27888,80,false);
INSERT INTO recurring_hunter_contracts VALUES(4983,1,10249,216,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5277,'hunterLevel216Boss5277');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5283,'hunterLevel216Boss5283');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5289,'hunterLevel216Boss5289');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5295,'hunterLevel216Boss5295');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5301,'hunterLevel216Boss5301');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5394,'hunterLevel216Boss5394');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5400,'hunterLevel216Boss5400');
INSERT INTO recurring_hunter_targets VALUES(4983,1,5589,'hunterLevel216Boss5589');
INSERT INTO recurring_hunter_rewards VALUES(4983,1,9327,6,NULL,598552902,false);
INSERT INTO recurring_hunter_rewards VALUES(4983,1,9328,5,29023,80,false);
INSERT INTO recurring_hunter_contracts VALUES(5401,1,11111,231,4,1347235200000,604800000,0,'wakemu.hunter-weekly-distinct-boss-source-v1','native-achievements:csv-sha256:2a0ea6b81c1bf96ef498aba4e56b2131cc0a973350f5baa6439f0b22c6905fc8:weekly-variable-sum');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5626,'hunterLevel231Boss5626');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5632,'hunterLevel231Boss5632');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5638,'hunterLevel231Boss5638');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5644,'hunterLevel231Boss5644');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5650,'hunterLevel231Boss5650');
INSERT INTO recurring_hunter_targets VALUES(5401,1,5718,'hunterLevel231Boss5718');
INSERT INTO recurring_hunter_rewards VALUES(5401,1,10091,6,NULL,598552902,false);
INSERT INTO recurring_hunter_rewards VALUES(5401,1,10092,5,32303,80,false);
