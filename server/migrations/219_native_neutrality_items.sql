-- Five original neutrality scrolls; current real PvP balances remain native zero.
CREATE TABLE native_neutrality_item_actions (
 item_ref integer PRIMARY KEY CHECK(item_ref IN (16979,16980,16981,16982,24836)),
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 scenario_id integer NOT NULL CHECK(scenario_id=2318),
 event_id integer NOT NULL CHECK(event_id=19332),
 consumes_source boolean NOT NULL CHECK(consumes_source),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$')
);
INSERT INTO native_neutrality_item_actions VALUES
(16979,4280,2318,19332,true,'6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63'),
(16980,4278,2318,19332,true,'6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63'),
(16981,4279,2318,19332,true,'6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63'),
(16982,4238,2318,19332,true,'6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63'),
(24836,10234,2318,19332,true,'6de10a893e07743ae3b8168ff9f50988a768e26a4bcc4c7c7c5b5d71c86a1a63');
