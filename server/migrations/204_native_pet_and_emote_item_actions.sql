-- Original installed bHX pet-level rewards and bHY single-use emote actions.
CREATE TABLE native_pet_xp_actions (
 item_ref integer PRIMARY KEY CHECK(item_ref>0), action_id integer NOT NULL CHECK(action_id>0),
 levels integer NOT NULL CHECK(levels>0 AND levels<=32767), has_criteria boolean NOT NULL,
 source_sha256 text NOT NULL
);
CREATE TABLE native_emote_item_actions (
 item_ref integer PRIMARY KEY CHECK(item_ref>0), action_id integer NOT NULL CHECK(action_id>0),
 emote_id integer NOT NULL CHECK(emote_id>0), has_criteria boolean NOT NULL,
 use_criteria text NOT NULL,
 source_sha256 text NOT NULL
);
INSERT INTO native_pet_xp_actions(item_ref,action_id,levels,has_criteria,source_sha256) VALUES
(18376,5670,2,false,'dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(18431,5672,50,false,'dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(27578,11576,1,false,'dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6');
INSERT INTO native_emote_item_actions(item_ref,action_id,emote_id,has_criteria,use_criteria,source_sha256) VALUES
(19023,7138,20146,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(19025,7139,20147,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(19110,7178,20149,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(19595,7447,20145,false,'','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(20432,8063,20003,false,'','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(20484,8159,20186,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(20534,8220,20189,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6'),
(24280,10107,20227,false,'not #(IsBattleground() or HasState(531) or HasState(949) or HasState(980) or HasState(1404) or HasState(1453) or HasState(1454) or HasState(1578) or HasState(1776) or HasState(1807) or HasState(1986) or HasState(2003) or HasState(3151) or HasState(3312) or HasState(3313) or HasState(3314) or HasState(3504) or HasState(4878) or HasState(4878) or HasState(9258) or HasState(9259) or HasState(9260) or HasState(9261) or HasState(9262) or HasState(9263) or HasState(9264) or HasState(9265) or HasState(9266) or HasState(9267) or HasState(9268) or HasState(9269))#','dc603a869e54c84da4537bf8837fc4c324043270ccf5e439f83b4297dc3b58c6');

-- Same bounded retry policy as ordinary pet feeding; requests have no nonce.
CREATE TABLE pet_feeding_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 character_id bigint NOT NULL, pet_uid bigint NOT NULL CHECK(pet_uid>0),
 food_uid bigint NOT NULL CHECK(food_uid>0), quantity smallint NOT NULL CHECK(quantity>0),
 request_sha256 bytea NOT NULL CHECK(octet_length(request_sha256)=32),
 after_revision bigint NOT NULL CHECK(after_revision>0),
 applied_at_ms bigint NOT NULL CHECK(applied_at_ms>0),
 xp_delta integer NOT NULL CHECK(xp_delta>0),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id) ON DELETE CASCADE,
 UNIQUE(pet_uid,after_revision)
);
CREATE INDEX pet_feeding_replay_lookup ON pet_feeding_receipts(pet_uid,request_sha256,after_revision DESC);
