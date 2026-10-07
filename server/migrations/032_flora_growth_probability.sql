-- Local emulator policy: late Cardo/Fresno variants are optional maturity.
-- Probability is configurable and is not asserted as an official drop rate.
ALTER TABLE resource_growth_transitions ADD COLUMN probability double precision
 NOT NULL DEFAULT 1 CHECK(probability>=0 AND probability<=1);
UPDATE resource_growth_transitions SET probability=0.01
 WHERE resource_reference IN (60,139) AND from_stage=3 AND to_stage=4;
CREATE TABLE resource_growth_decisions (
 resource_uid bigint NOT NULL CHECK(resource_uid>0),
 from_stage smallint NOT NULL CHECK(from_stage BETWEEN 1 AND 127 AND from_stage<>16),
 to_stage smallint NOT NULL CHECK(to_stage BETWEEN 1 AND 127 AND to_stage<>16),
 probability double precision NOT NULL CHECK(probability>=0 AND probability<=1),
 draw double precision NOT NULL CHECK(draw>=0 AND draw<1),
 accepted boolean NOT NULL CHECK(accepted=(draw<probability)),
 CHECK(to_stage>from_stage),
 PRIMARY KEY(resource_uid,from_stage)
);
