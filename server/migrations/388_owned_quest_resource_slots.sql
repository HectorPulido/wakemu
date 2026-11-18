-- Reuse pinned story-resource slots for authenticated private story instances.
ALTER TABLE quest_resource_slots
 DROP CONSTRAINT quest_resource_slots_instance_id_check;
ALTER TABLE quest_resource_slots
 ADD CONSTRAINT quest_resource_slots_instance_id_check CHECK(instance_id>=0);
