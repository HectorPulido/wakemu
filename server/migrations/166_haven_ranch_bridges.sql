-- Original BUILD_RANCH_BRIDGE actions only; slots3/4 have no installed activator.
CREATE TABLE haven_ranch_bridges (
    owner_character_id bigint NOT NULL REFERENCES haven_bags(character_id) ON DELETE CASCADE,
    slot_id integer NOT NULL CHECK (slot_id BETWEEN 1 AND 4),
    present boolean NOT NULL,
    consumed_uid bigint NOT NULL CHECK (consumed_uid>0),
    consumed_ref integer NOT NULL CHECK (consumed_ref>0),
    actor_id bigint NOT NULL REFERENCES characters(id),
    built_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(owner_character_id,slot_id)
);
INSERT INTO settings(name,value) VALUES ('haven_ranch_bridge_policy',
'{"schema_version":1,"map_id":1440,"biome_id":1,"slots":[{"native_default_wire":0,"available_states":["PRESENT"],"footprint":[[-9,9],[-8,9],[-7,9]],"native_default":"ABSENT","y":8,"id":1,"x":-10},{"native_default_wire":0,"available_states":["PRESENT"],"footprint":[[-27,-28],[-27,-26],[-27,-27]],"native_default":"ABSENT","y":-29,"id":3,"x":-28},{"native_default_wire":0,"available_states":["PRESENT"],"footprint":[[9,-11],[9,-10],[9,-9]],"native_default":"ABSENT","y":-12,"id":2,"x":8},{"native_default_wire":0,"available_states":["PRESENT"],"footprint":[[-9,-46],[-8,-46],[-7,-46]],"native_default":"ABSENT","y":-47,"id":4,"x":-10}],"activators":[{"object_id":36068,"definition_id":1596,"action_id":2040,"slot_id":1,"selector":0,"item_ref":32883,"quantity":1,"consumed":true,"x":-6,"y":8,"z":0,"effect":{"cnZ":15,"awM":3601,"params":["1"],"kind":"BUILD_RANCH_BRIDGE","gdP":false,"criteria":"CanBuildBridge(1)"}},{"object_id":36069,"definition_id":1597,"action_id":2041,"slot_id":2,"selector":0,"item_ref":33215,"quantity":1,"consumed":true,"x":8,"y":-8,"z":0,"effect":{"cnZ":15,"awM":3602,"params":["2"],"kind":"BUILD_RANCH_BRIDGE","gdP":false,"criteria":"CanBuildBridge(2)"}}],"provenance":{"native_client_sha256":"e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd","slots_sha256":"2e32e18a286c8a1121d96cbdd2ad83594764b17be8171520bd7d998ac4144227","actions_sha256":"094eb37bed59c154978d844d64f10c7074893a29147129d63892dc3ab4f1292a"}}'::jsonb);
