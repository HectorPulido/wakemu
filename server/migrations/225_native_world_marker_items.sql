-- Pure native compass validation. This does not enable guild operations.
CREATE TABLE native_world_marker_item_actions (
 item_ref integer PRIMARY KEY,
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
 marker_map_id integer NOT NULL CHECK(marker_map_id>0),
 marker_x integer NOT NULL,
 marker_y integer NOT NULL,
 marker_z smallint NOT NULL,
 consumes_source boolean NOT NULL CHECK(NOT consumes_source)
);
INSERT INTO native_world_marker_item_actions VALUES
(16942,10384,'fa22f0ec458c41cbab5d38d9717a0fe70787660f45b711f0dab0c2bec35b56ee',527,71,-13,0,false),
(25100,10385,'fa22f0ec458c41cbab5d38d9717a0fe70787660f45b711f0dab0c2bec35b56ee',527,71,-13,0,false),
(25101,10386,'fa22f0ec458c41cbab5d38d9717a0fe70787660f45b711f0dab0c2bec35b56ee',527,71,-13,0,false);
