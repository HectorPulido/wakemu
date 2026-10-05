# Diferencias y portabilidad: Dofus → Wakfu

## Qué significa reutilizar

No partir de cero: conservar el pipeline de capacidades → intenciones → candidatos → planes → score → coordinación. Refactorizar dependencias para que `planner` no importe directamente un Board ni fórmulas particulares. Reutilización de algoritmos y contratos, no compatibilidad de snapshots o números de efecto. No hay aún una medición que permita prometer un porcentaje de código reutilizado.

| Aspecto | Dofus leído | Wakfu actual | Trabajo concreto |
|---|---|---|---|
| Identidad de celda | Board, enteros, width/height, índices de tablero isométrico | Tuplas XYZ y aristas dirigidas | Adaptador Position/Topology; eliminar aritmética de índices en algoritmos comunes |
| Movimiento | `apply_action` recorre neighbors y resta un PM por paso | `server_move`, geometría nativa y proveedor opcional de eventos de área | Evaluar ruta con callbacks/recursos de Wakfu; no puntuar solo destino |
| LOS | Board y transparent/ocupación | Rayos Sf, topología/alturas y footprints de actores | Adaptador de LOS llama a autoridad Wakfu; ausencia de topología es desconocido, no visible |
| Costes | `_legal_cast` y `apply_action` modelan principalmente coste AP del rank | PA/PM/PW, modificadores, condiciones y límites nativos | Recursos completos por acción/estado; recalcular después de buffs/debuffs |
| Habilidades | spellModel ranks + catálogo enriquecido | Propiedad csd y nivel -1/valor explícito, tablas fyP | Resolver propiedad/tabla desde NPC; no usar deck de jugador ni catálogo loot |
| Efectos | `_semantic_effects` clasifica IDs Dofus y aproxima algunos; otros opacos | Familias/runners, árboles de estado, criterios y variantes | Extraer semántica Wakfu; etiquetas sirven para priorizar, no para ejecutar |
| Daño previsto | Simulador separado con medias de tiradas y subconjunto de efectos | Dispatcher de efectos y preview con características/armadura/reacciones | Usar evaluador barato para shortlist y preview real para decisión final |
| Orientación | No modelo equivalente en `_legal_cast/apply_action` inspeccionados | `native_facing` y DamageExecutionContext | Extender score/estado de búsqueda con dirección del objetivo y propia |
| Altura | Board de celdas 2D; no cotas XYZ en esa representación | Z, altura de LOS, aristas y huellas | No colapsar Z; evaluar accesibilidad y tiro desde cada altura |
| Estado/turnos | Arrays y simulador detached, buffs/expiración aproximados | Estados con UID, propietarios, contenedores, eventos/reacciones | Claves de transposición completas; no deduplicar por HP/celda solamente |
| Azar | Valor esperado/modelo TinyPolicy opcional | RNG transaccional y flags/ramas nativas | Previsión separada de RNG live; control explícito de confianza/escenarios |
| Coordinación | TeamCoordinator con focus/reservations/recent | Servicio actual sin memoria de equipo | Portar concepto y modificadores; confirmar memoria después del commit world |
| Retorno del servicio | Plan de strings cast/move/walk | Protocolo 1 solo path y ataque null | Protocolo 2 tipado, validación/ACK por acción y cancelación por revisión |
| Dificultad | Perfiles/heurísticas/política | Movimiento determinista único | Perfiles en DB; sin cambiar costes, alcance o daño para hacer IA «más inteligente» |

## Componentes portables y modificaciones necesarias

**Busqueda de turnos (`complete_turn`, `bounded_turn_plans`):** conservar beam, límite de nodos, deduplicación, diversidad y deadline. Cambiar llamadas a `apply_action`, `generate_actions` y `evaluate` por interfaces inyectadas. `complete_turn` trabaja con estados y reglas Dofus concretas: no es un módulo plug-and-play hoy. En la primera versión planificar solo el actor actual; búsqueda de turnos rivales añade coste y errores si sus operaciones no están soportadas.

**Intenciones (`IntentDecision`):** conservar conceptos de rematar, desgastar, curar, proteger, invocar, trabar, aproximar y retirada. Sustituir helpers de distancia, resistencias, inmunidad, tacleo y efectos especiales. Separar generación de opciones de la selección Laya: su eliminación debe retirar imports y dependencias, no solo poner `LAYA_ENABLED=false`.

**Memoria de equipo:** conservar foco, roles/afinidades y anti-oscilación. La reserva debe incluir ruta/corredor/tiro si afecta a aliados, no solo celda final. En turnos secuenciales no debe prohibir para siempre una posición que otro ya abandonó. Varios workers requieren estado compartido o afinidad por encuentro; un singleton Python no coordina réplicas.

**Memoria de intención (`TurnStrategyCache`):** conservar intención y objetivo con revisión de turno; no reutilizar casillas o hechizos ilegales. Al morir objetivo, cambiar estados, actor o turno, invalidar/reelegir. Su denominación «neural» no obliga a usar una red: puede servir igual al selector determinista.

**Política TinyPolicy:** opcional; no cargar `model/policy.bin` Dofus en Wakfu. Dimensiones y significado de features, distribución de posiciones y recompensas difieren. Primero generar corpus Wakfu y baseline determinista; solo entrenar si mejora resultados/latencia sobre el mismo corpus. Laya queda totalmente fuera.

## Orientación y elevaciones: regla existente versus mejora de IA

`combat_ordinary_authority.native_facing(source,target)` usa la dirección autoritativa del objetivo, ocho vectores y normalización float32. Devuelve FRONT con dot≤−0.7, BACK con dot≥0.72 y SIDE en medio. Conserva semántica de enteros Java; ignora Z después de comparar igualdad XYZ. La IA debe **llamar a esta función**, no recodificar los umbrales ni convertir a una regla visual de cuatro direcciones.

`ordinary_cast_authority.damage` obtiene esa localización. `combat_damage_handler` la usa solo si `native_localization_enabled`; si está desactivado fuerza FRONT. Por tanto, «ir a la espalda» no da beneficio universal: depende del efecto y del estado. El valor adicional debe salir de la diferencia de previews. Una condición de backstab puede además usar `combat_condition_facing.native_backstabbed`; no confundir geometría de daño y condición de hechizo.

`combat_los.authoritative_visible` y `combat_native_los_ray.cast_rays` usan alturas nativas de origen/destino y huellas dinámicas. La tabla de altura de una casilla no basta para determinar tiro libre. `topology_columns(map_id)` necesita archivo exportado del mapa: una nueva mazmorra puede carecer de geometría aunque sus monstruos tengan hechizos. El planificador debe devolver límite de evidencia y fallback legal, no jugar con un raycast plano inventado.

No incorporar un multiplicador automático por elevación. Puede ser buena por LOS, cobertura, alcance efectivo o acceso restringido; también puede ser una trampa sin salida. Esas consecuencias deben medirse por la misma topología/preview que usa ejecución.
