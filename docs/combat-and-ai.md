# Combat and AI

[Wiki home](README.md) · Related: [Characters and items](characters-and-items.md)

## From the world to a fight

A fight creates its own actors, teams, placement area, and turn order. Arena selection uses the map's terrain and valid cells. Placement lets participants choose positions before the active turn sequence begins. Joining, spectating, and returning to the world have their own synchronization paths.

During a turn, world checks ownership, available resources, movement, range, targeting, and line of sight. Client animation acknowledgements are part of action sequencing: a successful calculation alone does not mean every participant has finished displaying it.

## Spells are shared building blocks

The main spell path prepares a transaction on a copy of the fight. It validates costs and executes ordered effects on that preview before committing the result and publishing packets. An unsupported eligible effect rejects that transaction rather than leaving earlier damage or costs partly applied.

The effect dispatcher handles reusable operations such as damage, healing, displacement, resource changes, states, and summons. Conditions decide when an operation is eligible; triggers react to events such as movement, damage, or turn boundaries. States can retain effects beyond the original cast. Player and monster spells use these shared foundations, although some specialized paths remain.

Catalog definitions describe spell behavior; code supplies the supported operations. Having a spell in a catalog does not prove that its complete behavior is executable.

## Monster decisions

The separate AI service evaluates movement and spell choices using the fight context and previews from the combat engine. It searches within a time budget, then returns a proposed action. World keeps final authority over execution and synchronization.

This is a tactical planner, not a conversational AI service. Missing monster casting prerequisites can restrict an actor to movement; a visible monster is not proof that its attacks are supported.

## Ending and recovering fights

Death, withdrawal, surrender, rewards, and world return are distinct steps. Checkpoints support recovery, while reward ownership and delivery records help prevent duplicate settlement. Changes must preserve multiplayer views, summons, reconnect behavior, and the same shared spell rules used by AI.
