-- Paid native bonus84 may provision the same explicit Wakemu starter world.
-- Existing assignments and their administrator origin remain unchanged.
ALTER TABLE guild_haven_worlds
    DROP CONSTRAINT guild_haven_worlds_assignment_origin_check;
ALTER TABLE guild_haven_worlds
    ADD CONSTRAINT guild_haven_worlds_assignment_origin_check
    CHECK (assignment_origin IN (
        'wakemu_explicit_private_assignment_v1',
        'explicit_native_bonus84_base_world_v1'
    ));
