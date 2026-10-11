# Ordinary NPC spell-book authority

Representative: Mamá bwork (5641), spell 8314 at level 239. Trigger execution lacked an actual owned native spell book even though the native NPC ability producer already exposes the owned spells and their clamped levels.

`ordinary_npc_spellbook` reuses `monsters.native_abilities` for the actual roster actor and source reference. The ordinary authority accepts an optional producer, wired by the server runtime. Existing explicit books take precedence. Player books and registered summon authorities retain their existing paths. Invalid identities, duplicate spells and invalid native short levels fail closed; an actual empty native book remains empty.

Six new focused tests pass independently. The combined ordinary-book/constructor regression gate passed 32 methods and encountered one original fixture error: the isolated catalog lacks `native-class-summon-effect-closure.json`. That error is not reported as a pass. Original test assertions were not changed. The actual 5641 native replay remains pending; this source fix does not establish activation readiness.
