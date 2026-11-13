#!/usr/bin/env python3
import json, pathlib, psycopg2


def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# DB connection details
pwd = pathlib.Path(".database/secrets/postgres-password").read_text().strip()
conn = psycopg2.connect(
    host="127.0.0.1", port=15432, dbname="wakemu_runtime", user="wakemu", password=pwd
)
cur = conn.cursor()

# Interactive DB bindings
cur.execute("SELECT quest_id, objective_id FROM quest_interactive_bindings")
interactive_db = set(tuple(row) for row in cur.fetchall())

# Combat DB bindings
cur.execute("SELECT value FROM settings WHERE name='combat_mission_bindings_v1'")
row = cur.fetchone()
combat_db = set()
if row:
    val = row[0]
    for b in val.get("bindings", []):
        q = b.get("quest_id")
        o = b.get("objective_id")
        if q is not None and o is not None:
            combat_db.add((q, o))

# Native quest conversation contracts
cur.execute(
    "SELECT value FROM settings WHERE name='native_quest_conversation_contracts'"
)
row = cur.fetchone()
turnins_db = set()
bindings_db = set()
if row:
    val = row[0]
    for t in val.get("turnins", []):
        q = t.get("quest_id")
        o = t.get("objective_id")
        if q is not None and o is not None:
            turnins_db.add((q, o))
    for b in val.get("bindings", []):
        q = b.get("quest_id")
        o = b.get("objective_id")
        if q is not None and o is not None:
            bindings_db.add((q, o))

# Load candidate JSONs
named = load_json(".runtime/quest-reconstruction/named-combat-bindings.json")
dungeon = load_json(".runtime/quest-reconstruction/dungeon-combat-bindings.json")
combat_candidates = set()
for src in (named, dungeon):
    for b in src.get("bindings", []):
        if "quest_id" in b and "objective_id" in b:
            combat_candidates.add((b["quest_id"], b["objective_id"]))

interactive = load_json(".runtime/quest-reconstruction/interactive-candidates.json")
interactive_candidates = set()
for ref in interactive.get("references", []):
    q = ref.get("quest_id")
    o = ref.get("objective_id") or ref.get("referenced_objective_id")
    if q is not None and o is not None:
        interactive_candidates.add((q, o))

rec_turnins = load_json(".runtime/quest-reconstruction/recurring-turnins.json")
turnin_candidates = set()
for qobj in rec_turnins.get("candidates", []):
    quest_id = qobj.get("id")
    # each turnin refers to an objective through the native definition; we approximate by using the first turnin's item_thresholds objective? Not available.
    # Instead, we consider that presence of a turnin implies an objective exists; we will mark missing by quest_id alone.
    turnin_candidates.add(quest_id)

conversation = load_json(".runtime/quest-reconstruction/dialogue-references.json")
conversation_candidates = set()
for ref in conversation.get("references", []):
    # Dialogue references refer to achievements; we map achievement id to quest via native definitions (not trivial). We'll record as (id, None).
    conversation_candidates.add(ref.get("id"))

# Compute missing sets
missing_combat = combat_candidates - combat_db
missing_interactive = interactive_candidates - interactive_db
missing_turnins = turnin_candidates - {q for q, o in turnins_db}
missing_conversation = conversation_candidates - {q for q, _ in bindings_db}

print("=== Summary ===")
print(
    f"Combat bindings: candidates {len(combat_candidates)}, in DB {len(combat_db)}, missing {len(missing_combat)}"
)
print(
    f"Interactive bindings: candidates {len(interactive_candidates)}, in DB {len(interactive_db)}, missing {len(missing_interactive)}"
)
print(
    f"Turnins: candidate quests {len(turnin_candidates)}, in DB {len(turnins_db)}, missing quests {len(missing_turnins)}"
)
print(
    f"Conversation contracts: candidate ids {len(conversation_candidates)}, in DB bindings {len(bindings_db)}, missing ids {len(missing_conversation)}"
)

# Output detailed missing lists (truncated for brevity)
if missing_combat:
    print("\nMissing combat bindings (quest_id, objective_id):")
    for item in sorted(missing_combat)[:20]:
        print(item)
if missing_interactive:
    print("\nMissing interactive bindings (quest_id, objective_id):")
    for item in sorted(missing_interactive)[:20]:
        print(item)
if missing_turnins:
    print("\nMissing turnins (quest_id):")
    for q in sorted(missing_turnins)[:20]:
        print(q)
if missing_conversation:
    print("\nMissing conversation contracts (achievement id):")
    for aid in sorted(missing_conversation)[:20]:
        print(aid)

cur.close()
conn.close()
