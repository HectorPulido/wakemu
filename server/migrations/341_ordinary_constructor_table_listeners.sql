-- Explicit Wakemu per-table publication for source-proven native constructor roots.
-- Native criteria, state ownership, event counts and child effects remain authoritative.
CREATE TABLE native_npc_constructor_table_listeners (
    monster_reference integer NOT NULL CHECK (monster_reference > 0),
    state_id integer NOT NULL CHECK (state_id > 0),
    root_id integer NOT NULL CHECK (root_id > 0),
    source_sha256 text NOT NULL CHECK (length(source_sha256) = 64),
    metadata_sha256 text NOT NULL CHECK (length(metadata_sha256) = 64),
    authority text NOT NULL CHECK (length(authority) > 0),
    source_uri text NOT NULL CHECK (length(source_uri) > 0),
    PRIMARY KEY (monster_reference, state_id, root_id)
);

-- 5606 renews its native odd-table player mechanic only with multiple enemies;
-- 5745 adds its native state grade from table two when action90 is absent;
-- 5770 renews native armor on odd tables. No conditions are relaxed.
INSERT INTO native_npc_constructor_table_listeners
    (monster_reference,state_id,root_id,source_sha256,metadata_sha256,authority,source_uri)
VALUES
    (4756,5606,265135,'87c02e12045b7c9a36114d8e402e8bc30e3c396572d3001bc0f68233401550d8','de80a754be325ce7de93edfb1889d1cded378177442134617a73fe24e6f5e8a8',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5606/effect/265135'),
    (4757,5606,265135,'87c02e12045b7c9a36114d8e402e8bc30e3c396572d3001bc0f68233401550d8','de80a754be325ce7de93edfb1889d1cded378177442134617a73fe24e6f5e8a8',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5606/effect/265135'),
    (4758,5606,265135,'87c02e12045b7c9a36114d8e402e8bc30e3c396572d3001bc0f68233401550d8','de80a754be325ce7de93edfb1889d1cded378177442134617a73fe24e6f5e8a8',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5606/effect/265135'),
    (4534,5745,270355,'25a886e27f6a3c624e9239e53a96c09db2f894dff657f516f4582b602b8284b1','6156f2c930312ac08e398951ffb20309ee620d249234c6996b63a7fa1aea3000',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5745/effect/270355'),
    (4535,5745,270355,'25a886e27f6a3c624e9239e53a96c09db2f894dff657f516f4582b602b8284b1','6156f2c930312ac08e398951ffb20309ee620d249234c6996b63a7fa1aea3000',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5745/effect/270355'),
    (4536,5745,270355,'25a886e27f6a3c624e9239e53a96c09db2f894dff657f516f4582b602b8284b1','6156f2c930312ac08e398951ffb20309ee620d249234c6996b63a7fa1aea3000',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5745/effect/270355'),
    (4537,5745,270355,'25a886e27f6a3c624e9239e53a96c09db2f894dff657f516f4582b602b8284b1','6156f2c930312ac08e398951ffb20309ee620d249234c6996b63a7fa1aea3000',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5745/effect/270355'),
    (4886,5770,270723,'a4b497076ac4fc364df3732bee25c95c5c51359e07eaec72e4fb61b3ea25ddfb','0a3378dbd13292521c4e1466b4c06911350dee574f8705b7d6ad95a03b2a87fe',
     'wakemu-reviewed-native-periodic-constructor-global1003',
     'native0793:state/5770/effect/270723');
