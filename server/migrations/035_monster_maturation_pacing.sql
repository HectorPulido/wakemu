-- Emulator pacing: preserve probabilistic stages, with 15 active minutes
-- between attempts. Existing timers start a full interval, including pending
-- attempts; committed transformations and receipt identities remain intact.
UPDATE settings
SET value=jsonb_set(value,'{interval_ms}','900000'::jsonb)
WHERE name='monster_maturation';

UPDATE monster_maturation_timers
SET remaining_ms=900000,last_active_ms=NULL,observer_generation=NULL,due=false;
