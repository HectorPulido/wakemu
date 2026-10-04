# Inicialización exhaustiva de pasivas

Fecha: 2026-10-04T04:20:54.898830+00:00

339 pasivas nativas probadas individualmente con las innatas propias: primer nivel legal (máximo entre 10 y desbloqueo) y nivel 200. Catálogos cargados una vez, instantáneas completas y autoridad ordinary real.

796 casos: 678 individuales y 118 combinaciones representativas. 761 inicializados; 35 bloqueados (18 individuales y 17 combinaciones). 330/339 pasivas inicializan individualmente en ambos niveles; nueve conservan un bloqueo explícito.

Hashes estables durante la ejecución; los 796 combates originales se conservan intactos. No se emiten eventos de turno, no se prueba todo el espacio de combinaciones y estos resultados no equivalen a funcionalidad verificada jugando.

| Clase | Pasiva | ID | Primer efecto/familia bloqueado | Motivo |
|---|---|---:|---|---|
| 6 | Impacto Felino | 5249 | 359836 / 400 | Subscribed effect requires native event delivery |
| 8 | Agrupación | 5102 | 398149 / 400 | Unaudited effect area: any/crossRing-1-3 |
| 9 | Tiro Divergente | 6962 | 348490 / 912 | Subscribed effect requires native event delivery |
| 10 | Empuje Silvestre | 8150 | 379582 / 949 | Subscribed effect requires native event delivery |
| 11 | Pacto de Wakfu | 7217 | 353414 / 912 | Subscribed effect requires native event delivery |
| 14 | Colisiones Regenerativas | 7106 | 308144 / 910 | Subscribed effect requires native event delivery |
| 15 | Veda Abierta | 7554 | 345698 / 1202 | No handler for native effect class 1202 |
| 15 | Furor | 7557 | 345699 / 1201 | No handler for native effect class 1201 |
| 16 | Revestimiento Absoluto | 6936 | 344011 / 999 | Relative class330 probability requires native candidate targeting and RNG |

Evidencia reproducible: `server/tools/audit_passive_initialization.py`, `passive-initialization-audit.json` (trazas, criterios, fuentes y hashes), `passive-initialization-audit.csv`. Dos pruebas del workload verifican cobertura exacta, niveles/decks legales y muestras deterministas.

Prioridades: acreditar admisión y entrega de listeners 400/912/949/910; interpretar 1201/1202; extender targeting nativo crossRing y probabilidad relativa sin inventar objetivos.
