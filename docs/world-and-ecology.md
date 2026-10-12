# World and ecology

[Wiki home](README.md) · Related: [Combat and AI](combat-and-ai.md)

## Maps and interactions

Maps combine static terrain with live players, monsters, resources, and interactive objects. Movement and destinations are checked against geometry. Prepared geometry and line-of-sight artifacts reduce repeated work without replacing the underlying map rules.

Transports have discovery, access, and destination checks. A map change includes saving the old position and sending the destination scene; changing coordinates alone is not enough. Doors, seats, boats, and other objects have separate interaction handlers, with support depending on available definitions.

## Resources and professions

Planting checks the item, cell, profession requirements, and applicable probability before consuming seeds and creating a resource. Resources progress through growth stages. Harvesting grants supported products and profession experience; depleted fishing and mining locations follow their own recovery rules.

Wakfu/Stasis progression reflects supported ecological actions. Weather and territory context can affect the world, but a displayed client percentage is not always the actual server-side planting probability.

## The ecology worker

Ecology runs in a separate service so background planning does not sit inside a player's critical gameplay path. It prepares changes for plants, monsters, population, and weather, then submits durable proposals to world.

World checks whether each proposal still matches current state before applying it. Proposal identity and state checks protect against repeated delivery. Failed delivery has bounded retries and recorded outcomes. A single-worker database lock prevents two planners from owning the same simulation at once.

Monster population includes initial placement, wandering, maturation, reproduction, and removal. These are related systems; a visible group does not imply complete combat support for every species.

## Dungeons, NPCs, and stories

Dungeons maintain instance membership, room progress, encounter state, difficulty, and transitions. Rewards use the encounter context as well as ordinary combat results.

NPC placement, initial dialogue, dialogue branches, quest conditions, and rewards are separate pieces. Some interactions are implemented; the presence of dialogue or quest definitions does not make every storyline playable. See [Limitations](limitations.md).
