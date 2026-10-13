-- New characters start at the native central Astrub zaap.
-- Existing characters retain their current location.
ALTER TABLE characters ALTER COLUMN map_id SET DEFAULT 527;
ALTER TABLE characters ALTER COLUMN instance_id SET DEFAULT 0;
ALTER TABLE characters ALTER COLUMN x SET DEFAULT 0;
ALTER TABLE characters ALTER COLUMN y SET DEFAULT 32;
ALTER TABLE characters ALTER COLUMN z SET DEFAULT 0;
