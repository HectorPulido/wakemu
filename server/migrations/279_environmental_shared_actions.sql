-- One physical action may credit several participants, but advances the world once.
CREATE TABLE environmental_shared_actions (
 instance_id bigint NOT NULL REFERENCES environmental_event_instances(instance_id),
 objective_key text NOT NULL,receipt_key text NOT NULL,
 entity_kind text NOT NULL,entity_id bigint NOT NULL,
 fact_digest text NOT NULL CHECK(length(fact_digest)=64),
 quantity bigint NOT NULL CHECK(quantity>0),occurred_at_ms bigint NOT NULL CHECK(occurred_at_ms>=0),
 PRIMARY KEY(instance_id,objective_key,receipt_key,entity_kind,entity_id)
);
CREATE INDEX environmental_shared_actions_objective ON environmental_shared_actions(instance_id,objective_key);
