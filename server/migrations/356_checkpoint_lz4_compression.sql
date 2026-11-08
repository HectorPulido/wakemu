-- Compress future checkpoint writes with LZ4. Existing JSONB values remain
-- readable without a table rewrite; revision and lease checks are unchanged.
ALTER TABLE fight_checkpoints ALTER COLUMN snapshot SET COMPRESSION lz4;
