-- Explicit encounter reconstruction. Native fcE16/47 remain filters; no global
-- native replay behavior is inferred from either bit. Only this immutable
-- original descriptor is admitted in the reviewed frozen encounter scope.
ALTER TABLE encounter_group_population_effects
    DROP CONSTRAINT encounter_group_population_effects_selector_mask_check;
ALTER TABLE encounter_group_population_effects
    ADD CONSTRAINT encounter_group_population_effects_selector_mask_check
    CHECK(selector_mask >= 0 AND (selector_mask & 1) = 0);

INSERT INTO encounter_group_population_versions VALUES
('wakemu-nox-faille-player-population-v1',
 'wakemu-reconstructed-native-positive-player-applicator',
 1435,ARRAY[5664],ARRAY[402197]);
INSERT INTO encounter_group_population_effects VALUES
('wakemu-nox-faille-player-population-v1',402197,304,140737488355344,3,
 'IsPlayer("target")',ARRAY[9028.0,0.0,1.0,0.0,-1.0,0.0]::double precision[]);
INSERT INTO encounter_group_population_active VALUES
(1435,ARRAY[5664],'wakemu-nox-faille-player-population-v1');
