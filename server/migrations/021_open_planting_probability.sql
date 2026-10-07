-- Explicit local open-planting policy. The installed open client profile
-- displays1% regardless of native ground; use that same chance server-side.
INSERT INTO settings(name,value) VALUES ('open_planting_probability','0.01'::jsonb);
