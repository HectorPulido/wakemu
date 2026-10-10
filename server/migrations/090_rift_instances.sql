-- Explicit local DEV rift policy. Native pools are exact; balancing is not official.
INSERT INTO settings(name,value) VALUES ('rift_policy', '{"enabled":true,"ultimate_enabled":false,"policy_kind":"local_dev_not_official","turn_budget":40,"max_members":4,"classic_wave_size":4,"ultimate_wave_size":2,"starting_wave":1,"selection":"uniform_with_replacement","scaling":"native_base_grade","quest_requirements":false,"key_requirements":false,"rewards":"callback_only"}'::jsonb) ON CONFLICT(name) DO NOTHING;
INSERT INTO settings(name,value) VALUES ('rift_catalog', '{"19":{"wave_id":19,"dungeon_id":174,"map_id":1329,"level":111,"type":"INFINITE_WAVE","species_refs":[1169,1167,1166,2078,2083,2076,4723,4724,4725,2350,2351,2353,2344,2345,2347],"entrances":[{"map_id":1134,"object_id":33130,"x":64.0,"y":56.0,"z":0.0,"kind":"native_InfiniteWaves","wave_id":19,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1329,"id":33132,"type":"GenericActivableInteractiveElement","x":-2.0,"y":0.0,"z":0.0},{"map_id":1329,"id":33131,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]},"20":{"wave_id":20,"dungeon_id":175,"map_id":1330,"level":201,"type":"INFINITE_WAVE","species_refs":[4324,4325,4326,4208,4209,4210,5173,5174,5175,5169,5168,5167,5186,5185,5187],"entrances":[{"map_id":1276,"object_id":33135,"x":22.0,"y":-160.0,"z":1.0,"kind":"native_InfiniteWaves","wave_id":20,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1330,"id":33133,"type":"GenericActivableInteractiveElement","x":-1.0,"y":1.0,"z":0.0},{"map_id":1330,"id":33134,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]},"6":{"wave_id":6,"dungeon_id":171,"map_id":1320,"level":141,"type":"INFINITE_WAVE","species_refs":[2973,2974,2975,3078,3079,3090,5036,5037,3092,4886,4887,3093,5035,3076,4888],"entrances":[{"map_id":1136,"object_id":33027,"x":120.0,"y":-45.0,"z":-80.0,"kind":"native_InfiniteWaves","wave_id":6,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1320,"id":33020,"type":"GenericActivableInteractiveElement","x":4.0,"y":5.0,"z":9.0},{"map_id":1320,"id":33019,"type":"Teleporter","x":2.0,"y":2.0,"z":9.0}]},"5":{"wave_id":5,"dungeon_id":170,"map_id":1318,"level":111,"type":"ULTIMATE_INFINITE_WAVE","species_refs":[2343,2368,2469,2100,2972,2464,4520,4720,4231,4913],"entrances":[{"map_id":508,"object_id":33026,"x":-16.0,"y":-13.0,"z":0.0,"kind":"native_InfiniteWaves","wave_id":5,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1318,"id":33017,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0},{"map_id":1318,"id":33018,"type":"GenericActivableInteractiveElement","x":2.0,"y":2.0,"z":0.0}]},"25":{"wave_id":25,"dungeon_id":182,"map_id":1345,"level":216,"type":"INFINITE_WAVE","species_refs":[4205,4203,4204,5053,5054,5055,5056,5234,5232,5233,5180,5179,5181,5281,5282,5280,5288,5287,5286,5292,5293,5294,5298,5299,5300,5274,5275,5276],"entrances":[{"map_id":1342,"object_id":33266,"x":0.0,"y":36.0,"z":-12.0,"kind":"native_InfiniteWaves","wave_id":25,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1345,"id":33268,"type":"GenericActivableInteractiveElement","x":-2.0,"y":0.0,"z":0.0},{"map_id":1345,"id":33267,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]},"7":{"wave_id":7,"dungeon_id":172,"map_id":1322,"level":171,"type":"INFINITE_WAVE","species_refs":[3970,3395,3397,3855,3857,4921,3859,3860,3396,3856,3858,3968,3969,4920,4922],"entrances":[{"map_id":999,"object_id":33028,"x":-38.0,"y":-133.0,"z":-80.0,"kind":"native_InfiniteWaves","wave_id":7,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1322,"id":33021,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0},{"map_id":1322,"id":33022,"type":"GenericActivableInteractiveElement","x":2.0,"y":2.0,"z":0.0}]},"4":{"wave_id":4,"dungeon_id":169,"map_id":1316,"level":66,"type":"INFINITE_WAVE","species_refs":[4750,4751,4761,5104,4762,4766,4237,5105,5106,4238,4239,1152,1155,4749,1784],"entrances":[{"map_id":1135,"object_id":33025,"x":87.0,"y":-85.0,"z":-60.0,"kind":"native_InfiniteWaves","wave_id":4,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1316,"id":33013,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0},{"map_id":1316,"id":33014,"type":"GenericActivableInteractiveElement","x":2.0,"y":1.0,"z":0.0}]},"3":{"wave_id":3,"dungeon_id":168,"map_id":1314,"level":21,"type":"INFINITE_WAVE","species_refs":[4,4076,3214,3215,4077,4079,3212,5,41,704,3,1],"entrances":[{"map_id":527,"object_id":33010,"x":-192.0,"y":-30.0,"z":0.0,"kind":"native_InfiniteWaves","wave_id":3,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1314,"id":33012,"type":"GenericActivableInteractiveElement","x":-2.0,"y":2.0,"z":0.0},{"map_id":1314,"id":33011,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]},"8":{"wave_id":8,"dungeon_id":173,"map_id":1324,"level":201,"type":"ULTIMATE_INFINITE_WAVE","species_refs":[3864,3866,5059,5247,5182,5131,4318,5176,5188,5137],"entrances":[{"map_id":1124,"object_id":33029,"x":14.0,"y":-134.0,"z":20.0,"kind":"native_InfiniteWaves","wave_id":8,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1324,"id":33024,"type":"GenericActivableInteractiveElement","x":-1.0,"y":2.0,"z":0.0},{"map_id":1324,"id":33023,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]},"37":{"wave_id":37,"dungeon_id":183,"map_id":1347,"level":216,"type":"ULTIMATE_INFINITE_WAVE","species_refs":[4211,5289,5295,5301,4327,5170,5241,5277,5283],"entrances":[{"map_id":1342,"object_id":33269,"x":-18.0,"y":49.0,"z":-12.0,"kind":"native_InfiniteWaves","wave_id":37,"parameter_evidence":"length-prefixed decimal suffix; native consumer still needs end-to-end proof"}],"objects":[{"map_id":1347,"id":33271,"type":"GenericActivableInteractiveElement","x":-3.0,"y":1.0,"z":0.0},{"map_id":1347,"id":33270,"type":"Teleporter","x":0.0,"y":-1.0,"z":0.0}]}}'::jsonb) ON CONFLICT(name) DO NOTHING;
CREATE TABLE rift_instances (
 instance_id bigint GENERATED ALWAYS AS IDENTITY (START WITH 288230376151711745) PRIMARY KEY,
 wave_definition_id integer NOT NULL CHECK(wave_definition_id>0),
 owner_character_id bigint NOT NULL REFERENCES characters(id),
 members jsonb NOT NULL CHECK(jsonb_typeof(members)='array'),
 catalog jsonb NOT NULL CHECK(jsonb_typeof(catalog)='object'),
 policy jsonb NOT NULL CHECK(jsonb_typeof(policy)='object'),
 seed text NOT NULL CHECK(length(seed)>0),
 status text NOT NULL DEFAULT 'entered' CHECK(status IN('entered','running','won','lost','closed')),
 fight_id integer UNIQUE REFERENCES combat_fights(id),
 wave integer NOT NULL DEFAULT 1 CHECK(wave>0),
 completed_waves integer NOT NULL DEFAULT 0 CHECK(completed_waves>=0),
 defeated_monsters integer NOT NULL DEFAULT 0 CHECK(defeated_monsters>=0),
 last_turn integer NOT NULL DEFAULT 0 CHECK(last_turn>=0),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 ended_at timestamptz,
 CHECK((status IN('entered','running'))=(ended_at IS NULL))
);
CREATE TABLE rift_wave_receipts (
 instance_id bigint NOT NULL REFERENCES rift_instances(instance_id),
 wave integer NOT NULL CHECK(wave>0),
 actor_ids jsonb NOT NULL,
 defeated_monsters integer NOT NULL CHECK(defeated_monsters>0),
 roster jsonb NOT NULL,
 PRIMARY KEY(instance_id,wave)
);
CREATE TABLE rift_settlement_receipts (
 instance_id bigint PRIMARY KEY REFERENCES rift_instances(instance_id),
 fight_id integer NOT NULL UNIQUE REFERENCES combat_fights(id),
 outcome text NOT NULL CHECK(outcome IN('won','lost','closed')),
 result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rift_wave_rosters (
 instance_id bigint NOT NULL REFERENCES rift_instances(instance_id),
 wave integer NOT NULL CHECK(wave>0),
 actor_ids jsonb NOT NULL CHECK(jsonb_typeof(actor_ids)='array'),
 species_refs jsonb NOT NULL CHECK(jsonb_typeof(species_refs)='array'),
 PRIMARY KEY(instance_id,wave)
);

INSERT INTO settings(name,value) VALUES ('rift_reward_policy','{"kind":"disabled","xp":0,"kamas":0}'::jsonb) ON CONFLICT(name) DO NOTHING;
