# Open ultimate-boss arenas — 2026-10-10

Read-only preparation; this report does not claim runtime activation. The previous open_geometry_no_separator classification was too restrictive for native single-encounter boss arenas. A door sequence is unnecessary when native arrival, encounter engagement and literal exterior exit are all reachable in the same directed native component.

The generalized preparer requires native ULTIMATE_BOSS type and a singleton installed species pool, disallows internal transports and reviewed preliminary encounters, validates a complete one-boss formation with six player slots, and records directed encounter and exterior-exit paths. The one-boss quantity is explicit local policy, not a claim of verified official summons, phases, timers or initial adds. It replaces the old generated eight-duplicate-boss encounter in these candidate configurations. No combat or spell implementation is changed.

Ten arenas pass offline configuration, placement and sequence checks. They still require isolated PostgreSQL lifecycle acceptance and activation by the parent workflow. Boss mechanics remain unverified; prioritize Ogrest, Nox and Rushu for manual review because timer/score/phase semantics are not implemented by this preparation.

| Arena | Result |
|---|---|
| Antro de Excarnus | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Antro de Nogord, el Alado | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Antro de Jálrog | Reviewed guide has preliminary encounters; singleton arena cannot erase them |
| Antro del Cuervo Negro | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Antro del Dragocerdo | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Antro de Maxilubo | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Castillo del Wey Wabbit | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Cima del Gran Tótem | Missing compiled route configuration |
| Cire Momore | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Corazón del Reloj de Nox | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Dimensión-Objeto de Sombría | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Fosa del Atormentador | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Relojeros | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Arena Danzante | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| La Torre Mineral | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| La Torre Mineral | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Torre Mineral | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Neoantro del Cuervo Negro | Missing compiled route configuration |
| Neocastillo del Wey Wabbit | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Neopico del Monte Zinit | Missing compiled route configuration |
| Palacio de Rushu | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Meseta de los Altos Vuelos | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Pico del Monte Zinit | Prepared: one boss; native entry, six-player formation, engagement and exit proved |
| Guarida de Kali | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Rushu | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Santuario de Mihmol | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Teatro Intemporal | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Tumba de Tal Kasha | Missing compiled route configuration |
| Toross | Open multi-species/arcade arena needs reviewed initial encounter and progression |
| Torre de las Miss Adefesio | Open multi-species/arcade arena needs reviewed initial encounter and progression |

Magmog/Jálrog is deliberately blocked: its reviewed guide includes a preliminary Boufrog encounter. Treating the reachable map as a single boss room would erase progression. The four missing compiled-route bases (Ful Moon, Neocuervo Negro, Neoogrest and Tal Kasha) are preparation/registration gaps, not evidence of inaccessible terrain. They need safe route compilation and registration before activation.

Verification: `PYTHONPATH=server:server/tools .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_open_boss_dungeons.py` — six tests passed. The candidate JSON records complete placement and path witnesses.
