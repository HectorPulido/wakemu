-- Reviewed original Crow phase producers. Ordinary AI must not directly
-- hide/reveal/transform before the original7325/1037/1001 callbacks authorize it.
-- The native book, queued426 execution, paid counterplay and alternate forms
-- remain unchanged. Each row seals its original constructor/effect/spell path.
CREATE TABLE encounter_scripted_phase_spells (
    policy TEXT NOT NULL CHECK (btrim(policy) <> ''),
    map_id INTEGER NOT NULL CHECK (map_id > 0),
    layout_policy TEXT NOT NULL CHECK (btrim(layout_policy) <> ''),
    layout_authority TEXT NOT NULL CHECK (btrim(layout_authority) <> ''),
    actor_reference INTEGER NOT NULL CHECK (actor_reference > 0),
    initial_state INTEGER NOT NULL CHECK (initial_state > 0),
    spell_reference INTEGER NOT NULL CHECK (spell_reference > 0),
    source_effect_path INTEGER[] NOT NULL CHECK (
        array_ndims(source_effect_path) = 1
        AND cardinality(source_effect_path) BETWEEN 1 AND 30
        AND 0 < ALL(source_effect_path)
    ),
    native_revision TEXT NOT NULL CHECK (native_revision ~ '^[0-9a-f]{64}$'),
    source_closure_sha256 TEXT NOT NULL CHECK (source_closure_sha256 ~ '^[0-9a-f]{64}$'),
    authority TEXT NOT NULL CHECK (authority = 'authorized_wakemu_native_content_reconstruction'),
    PRIMARY KEY (policy, spell_reference),
    UNIQUE (map_id, layout_policy, actor_reference, spell_reference)
);
INSERT INTO encounter_scripted_phase_spells
    (policy,map_id,layout_policy,layout_authority,actor_reference,initial_state,
     spell_reference,source_effect_path,native_revision,source_closure_sha256,authority)
VALUES
    ('wakemu-crow-original-scripted-phase-v1',363,'wakemu.crow.observed_native_aerial_platform.v1','reconstructed_world_coordinates_from_observed_platform_layout',1988,7325,7501,ARRAY[332478,332536,332565],'0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde','f22de4ebcf0ab66daf93c5c6ce8bf904bdfe81d53baceee081b4388a54b97ca8','authorized_wakemu_native_content_reconstruction'),
    ('wakemu-crow-original-scripted-phase-v1',363,'wakemu.crow.observed_native_aerial_platform.v1','reconstructed_world_coordinates_from_observed_platform_layout',1988,7325,7502,ARRAY[332478,332536,332566,332567],'0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde','54ec297cf71883954e88bc748ed7564876e466acaed91d2c10f0290ca3bfd1dd','authorized_wakemu_native_content_reconstruction'),
    ('wakemu-crow-original-scripted-phase-v1',363,'wakemu.crow.observed_native_aerial_platform.v1','reconstructed_world_coordinates_from_observed_platform_layout',1988,7325,7508,ARRAY[332478,332536,332566,332725],'0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde','46f220554219a0cb7b08a93374309a8cdc01c203827d133467e027e8be1da034','authorized_wakemu_native_content_reconstruction');
