-- Explicit Wakemu reconstruction; original predicates do not prove debit/output quantities.
CREATE TABLE configured_scenario_assembly_actions (
 item_ref integer PRIMARY KEY,
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 policy text NOT NULL,
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
 descriptor jsonb NOT NULL
);
CREATE TABLE scenario_assembly_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id),
 source_uid bigint NOT NULL,
 definition_id integer NOT NULL,
 objective_id integer NOT NULL,
 policy text NOT NULL,
 fact jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(character_id,definition_id,objective_id)
);
INSERT INTO configured_scenario_assembly_actions VALUES (20440,8071,'wakemu_reconstructed_native_binding_assembly_v1','52791b14e46913ebde9267b5b14c4484b8f291827694a99a982d89279ee91af1','{"schema_version":1,"policy":"wakemu_reconstructed_native_binding_assembly_v1","native":{"item_ref":20440,"action_id":8071,"native_class":"bIn","type":"START_SCENARIO","type_id":7,"item_level":178,"action_criterion":"GetItemQuantity(20440) >=1 && IsAchievementRunning(2909) && IsAchievementObjectiveComplete(5914) && IsAchievementObjectiveComplete(5915) && IsAchievementObjectiveComplete(5916) && IsAchievementObjectiveComplete(5917) && IsAchievementObjectiveComplete(5918) && !IsAchievementObjectiveComplete(5919) && GetItemQuantity(19147) >= 5 && GetItemQuantity(19791) >= 2 && GetItemQuantity(20148) >= 2 && GetItemQuantity(19798) >= 2 && GetItemQuantity(20196) >= 2","action_parameters":["2119"],"raw_item_criteria":[],"generic_criteria":{},"use_criterion":"","use_in_fight_criterion":"","native_use_class":null,"native_fight_use_class":null,"flag_cqc":false,"consume_flag_cqa":false,"flag_cqb":true,"flag_cmW":false,"extra_parameters":[]},"item_ref":20440,"action_id":8071,"scenario_id":2119,"event_id":17017,"definition_id":2909,"objective_id":5919,"minimum_real_level":178,"required_objectives":[5914,5915,5916,5917,5918],"preserve_source":true,"materials":{"19147":5,"19791":2,"20148":2,"19798":2,"20196":2},"products":{"20441":1},"reward":{"aeV":6,"ckk":false,"ckl":[200000000],"d":4490},"policy_inferences":["native_possession_minima_are_debit_amounts","unique_compatible_quest_journal_20441_quantity_one","source_preserved_without_proven_server_kit_debit"]}'::jsonb);
