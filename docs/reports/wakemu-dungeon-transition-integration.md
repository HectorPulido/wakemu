# Dungeon transition integration contract

The domain APIs do not mutate live socket or combat registries.

## Entry

Intercept configured native `12296` routes with `dungeon_transport.enter`
before the unconditional generic transport resolver. The entry transaction
already moves the complete authorized party and writes one durable outbox
event per selected member. Do not subsequently call `Store.transition_map`.
The optional trusted `initialize_instance(db, session)` callback initializes
frozen room state and first encounter intent inside that same transaction;
an exception rolls back entry, locations and outbox together.

## Delivery

Each selected worker polls `dungeon_transition_delivery`. Its callback first
calls `dungeon_hydration.prepare_transition`, which reads the actual persisted
destination and prepares the complete native map bootstrap. Only then apply
the existing transition sequence: cancel crafting, leave WORLD, replace the
worker character, attach POSITIONS, rebuild Movement, send planned packets,
join WORLD and schedule static/current-map replay. Return true only after the
entire delivery sequence. The consumer acknowledges with a second database
lease/membership/location check. Reconnection uses persisted location.

## Internal doors

`dungeon_doors.advance` validates the native route and approved source path.
Bind its `room_for_position` callback to `dungeon_sections.derive_sections`
cells; never derive room order from teleporter IDs. Forward travel requires a
committed victory receipt for the source room and an unlocked destination.
Reverse travel is restricted to already unlocked adjacent rooms. Every active
run member must have a current selected session and be outside combat. The
transaction preserves the private instance and writes durable `door` events
for all active members. Returned members are excluded.

## Exterior exit

`dungeon_exit.leave` validates a native free exterior return to the run's
entry map. It returns one member to instance zero and marks that membership
returned. Other members retain their private run. The last return closes the
run; its exit event remains deliverable. Migration072 distinguishes enter,
door and exit destinations. Exit hydration clears ProtoDungeon only after
checking the corresponding pending durable exit and returned membership.

## Verification state

The pure identity/hydration/approach/door-resolution gate passes12 tests.
Luna's isolated PostgreSQL gate through072 passes48 existing entry/context/
delivery/exit tests and9 progression tests. Initializer rollback and internal
door transactional cases subsequently passed:3 exterior/initializer cases and4
door cases, including pre-victory rejection, private party movement, durable
delivery, combat blocking, reverse travel and stale-source rejection.
These source changes do not establish runtime or visual acceptance.

## Reconnection

After selecting the owned character, call `dungeon_recovery.resume_member`
before the first13974 bootstrap. It validates the selected live lease, actual
persisted private map/run and active social/run membership. Only that member's
generation changes. Old-generation transition intents are superseded because
the initial bootstrap hydrates the persisted destination. It does not repeat
travel. Two isolated PostgreSQL recovery cases pass through migration073.

All private-world13974 paths need the pinned context, including initial replay,
fallback map loading, combat return and transport rejection. Replaying a default
non-dungeon context at any of those points clears the native dungeon UI state.
