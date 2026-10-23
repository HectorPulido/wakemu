-- Original reusable diary fragment: one self-contained reading scenario event.
CREATE TABLE native_reading_scenario_item_actions (
 item_ref integer PRIMARY KEY CHECK(item_ref=30723),
 action_id integer NOT NULL UNIQUE CHECK(action_id=14933),
 scenario_id integer NOT NULL CHECK(scenario_id=2704),
 event_id integer NOT NULL CHECK(event_id=24072),
 consumes_source boolean NOT NULL CHECK(NOT consumes_source),
 script_sha256 text NOT NULL CHECK(script_sha256='ecb63a5f6b301229d8c7887f7c2339c5b3d7bc9791c97ec12286d86c1b849710')
);
INSERT INTO native_reading_scenario_item_actions VALUES
(30723,14933,2704,24072,false,'ecb63a5f6b301229d8c7887f7c2339c5b3d7bc9791c97ec12286d86c1b849710');
