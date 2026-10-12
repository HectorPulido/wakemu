# Characters and items

[Wiki home](README.md) · Related: [World and ecology](world-and-ecology.md)

## Identity and progression

A local account owns characters. A session identifies the active character and connection generation, allowing the server to reject stale requests after reconnecting or switching characters. Character state includes appearance, position, health, experience, spells, and supported social data.

Progression changes persistent values and publishes updates to the client. Combat experience and profession experience are separate reward paths. Achievements consume accepted server events; custom tasks use a separate server-owned system rather than pretending to be official journal entries. Coverage is still evolving.

## Inventory and equipment

Inventory records distinguish item definitions from owned instances. Bags and slots have capacity and placement rules; transfers must preserve quantities and item identity. Equipment contributes supported statistics and effects, and inventory changes must update both storage and the client's view.

Builds keep equipment, spell decks, and other supported selections together. Selecting an active build matters: editing an inactive build should not silently change the configuration used in combat. Level modulation has its own stat and deck publication rules.

## Crafting and exchanges

Crafting resolves a recipe, checks materials and station requirements, then applies item consumption, output, and profession rewards. Trading between players checks both inventories before transferring ownership. These operations need server-side validation even when the client already displays an apparently valid recipe or trade.

## Personal spaces and social systems

Haven Bags have dedicated handling for entry, storage, furniture, gardens, and guest interaction. Mounts, cosmetics, recycling, enchantment, and related item features also have specialized modules; implementation depth varies.

Groups manage invitations, membership, leadership, and group chat. Contacts, guilds, chat channels, duels, and fight invitations use separate services and protocol handlers. A working group or inventory does not imply full compatibility across every social or item subsystem.

Durable state lives in PostgreSQL. After changing a system, reconnect to verify persistence as well as immediate client updates.
