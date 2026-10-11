# Steamer special passive qualification

Scope: PostgreSQL-native class definitions and actual owned casting, Ready and turn lifecycle. This report does not equate Ready registration with completed passive behavior. No deployment or catalog activation is included.

## Qualified execution

The five methods in `test_combat_steamer_passive_semantics_runtime.py` passed individually: turret range/LOS/linearity/WP variants (6928/6932/7810), Motor MP reduction (6934), Reinforced Armor maximum HP and actual form turn loss (6936), Stasis Reservoir SP maximum/stat87 (6941), and near/far regeneration fallback (6927).

The three methods in `test_combat_steamer_conditional_followups_runtime.py` passed together. They cover eight actual full-WP Microbot conditional variants, actual created turret HP/stat87, and disabled/passive-marker branches. Full-WP Microbot range is3–9 without6930 and3–5 with6930; range is modifiable only with6926 and without6930. Initial range variants must not be reused blindly for the full-WP table.

Turret HP starts from its actual fresh1HP. Native1047 computes float32 maximum-HP scaling with nearest rounding: owner2050 yields615 at30%,923 at45%, then family20 gives created maxima616/924. The stat87 loss344137→344139 belongs to player Cannoner state7648, not the turret constructor;6941's player bonus is inherited by the fresh turret in the tested creation context.

## Native-disabled branches

7810 root350970 has literal criterion `False`. Its descendants350971→350972→350973 include the post-cast swap and are consequently disabled in this definition. They are not independent enabled post-cast listeners. The actual test confirms their absence while the casting-table LOS/linearity changes remain active.

6938 root344024 also has literal `False`; its damage child344025 must remain absent. Its separate1037 marker395184→395185 executes. Marker execution does not prove an active damage bonus.

## Execution pending

| Passive | Remaining semantic qualification | Exact native boundary |
|---|---|---|
|6929|Positive turret damage-to-heal response|346193 reverse damage2 requires active7698/7699/7700; ordinary turret7697 does not satisfy it|
|6931|PASS: owned elemental cast creates real companion; negative baseline|344157 event1024 requires6912–6916 and fewer than3 own6288; actual cast positive/negative passed|
|6937|PASS: actual turret upgrades stop at2 with passive and exceed2 without; alternate-target branches pending|346150/345881 stop adding7649 at level2 with passive; actual upgrade targets required|
|6940|PASS: SP-sensitive Microbot execution after natural7677 threshold; enemy-on-Microbot turn branch pending|3439961005/1037→343998 requires area385/978 at target;343859 additionally requires7677|
|6942|Actual Ambush specialization scaling versus baseline|1083 growth0.5 versus1 without form7647; new special-passive test queued|
|6943|Real incoming direct damage reduction with negative control|344028 damage2→3440291093−30, excluding indirect effect and6500|

No pending row above is certified complete. In particular, a matched Microbot conditional table does not by itself qualify6940's numeric/event consumers, and a registered turret does not qualify its upgrade or damage-to-heal behavior.

Follow-up execution candidates are frozen in `test_combat_steamer_special_passives_runtime.py` (6929 actual earth-turret damage/healing,6937 repeated legal owned turret upgrades,6942 native-eligible empty Ambush cell). Incoming direct damage is isolated in `test_combat_steamer_incoming_damage_runtime.py`, using real turn transitions and actual owned NPC spells. These new candidates have no acceptance claim until their delegated execution is terminal.

## Latest terminal follow-up and corrections

The six-method special/incoming batch completed with6931,6940 SP context and6937 real upgrade controls passing. Three contexts remained failing and were not certified:

- Initial Ambush6920 only creates area1773 and subscribes343431 to1005; its damage expectation at initial placement was wrong. The corrected fixture creates a turret first and advances the actual turn after placement.
-6929 earth-turret source7698 was armed, but the fresh turret had no7649 upgrade level for the native844 target loop. The corrected fixture upgrades the real turret once through7700 before arming it.
-6943 actual NPC7962 dealt5 damage with and without the passive;344029 was absent. A diagnostic run captures the actual registered344028 subscription and damage phase metadata. This remains an unresolved execution result, not a certified source bug or a permitted numeric expectation change.

Latest terminal log: `.runtime/remaining-six-refresh-20261010/steamer-special-incoming-final.log`. Corrected execution is queued serially with the catalog validator.
