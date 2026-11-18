-- Existing bindings retain their previous range policy. Reviewed bindings may
-- instead specify the exact native QV approach cells as flat XYZ triples.
ALTER TABLE quest_interactive_bindings
    ADD COLUMN approach_cells integer[] NOT NULL DEFAULT '{}' CHECK (cardinality(approach_cells) % 3 = 0);
UPDATE quest_interactive_bindings SET approach_cells = ARRAY[-20, y, 0]
WHERE map_id = 1387 AND quest_id = 5163 AND action_id = 0 AND parameter = 0
  AND (object_id, objective_id) IN ((26731, 10628), (26732, 10629), (26733, 10630));
