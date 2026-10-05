# Motor propuesto: reutilización amplia con adaptadores Wakfu

## 1. Contrato y responsabilidad

Mantener servicio separado `/v1/decide`, evolucionando explícitamente a protocolo 2. World genera snapshot y candidatos legales; IA puntúa y devuelve un plan indicativo. World revalida y ejecuta **una acción por vez**, espera sincronización y vuelve a planificar si cambió el estado. Nunca confiar en daño/costes calculados por el servicio.

Petición: `requestId`, `fightInstanceId` estable, `mapId/instanceId`, `turnId`, `stateRevision/stateKey`, `catalogVersion`, `policyVersion`, actor actual, equipos, posición XYZ, dirección, HP/maxHP/armadura/barrera, PA/PM/PW, características relevantes, estados/propiedades, control/visibilidad y límites de uso; geometría por hash inmutable, ocupación/restricciones dinámicas y candidatos/preview. El hash debe cubrir todos los datos de legalidad/evaluación, no solo posiciones y HP.

Respuesta: intención, objetivo, lista tipada de acciones `move(path)`, `cast(spellId, level, targetXYZ/actor)`, `face(direction)` únicamente si hay transición legal acreditada, o `end_turn`; revisión de origen, score desglosado, coste estimado, tiempo/nodos y razón. Rechazar IDs ajenos, acciones futuras inválidas o snapshot obsoleto. No introducir giro gratuito: la orientación final depende de los contratos nativos de movimiento/lanzamiento.

## 2. Adaptadores antes del ranking

Implementar módulos de servidor/IA con separación explícita:

- `npc_spell_authority`: habilidades propias desde csd, nivel efectivo, límites y condiciones; reutilizar tablas nativas y dispatcher común. Reemplaza whitelist Wonejo, sin modificar hechizos individuales de la otra sesión.
- `wakfu_tactical_adapter`: `legal_actions(snapshot)`, `preview(action)` y `outcome_features(before,after)`. La ruta de jugador actualmente exige su deck/propiedad; crear autoridad NPC, no simular un monstruo como jugador ni regalarle el deck de clase.
- `spell_semantics`: recorre raíces/hijos/estados con prevención de ciclos y condiciones. Clasifica DAMAGE, HEAL, ARMOR, BUFF/DEBUFF, RESOURCE_CONTROL, PUSH/PULL/SWAP/TELEPORT, SUMMON, AREA, SPECIAL/UNKNOWN. Las familias de daño actuales son 1/2/3/4/5/917/1083; curación 24/25/251/253/258/259/1084. Validar control y estados contra handlers, no inferir beneficio del nombre o del ID aislado. Un hechizo puede tener varias etiquetas y ramas condicionadas.
- `terrain_adapter`: aristas dirigidas XYZ reales, ocupación, alcance/LOS nativos, elegibilidad de celdas y callbacks de zonas. Cachear topología inmutable; no convertir a celdas diagonales de Dofus ni usar solo distancia Manhattan para aprobar un lanzamiento.

Preview debe usar copia aislada, catálogo compilado compartido y RNG sin efectos externos. No reservar UID durables ni consumir RNG real para comparar alternativas. Consecuencias probabilísticas se evalúan por estimación declarada o muestras reproducibles independientes; ejecución conserva su RNG autoritativo. Registrar incertidumbre y excluir candidatos con ramas obligatorias sin soporte; fallback conserva acciones legales conocidas.

## 3. Posiciones: espalda, lateral, altura y retirada

Generar primero casillas alcanzables dentro del presupuesto real; para cada posición probar blancos/hechizos legales. Incluir casilla actual: no mover por obligación. Comparar atacar ahora, acercarse para atacar, rodear hacia espalda/lateral, y atacar→retirarse. Eliminar rutas que bloqueen aliados sin compensación, repitan posiciones inútiles o gasten recursos sin mejorar el resultado.

**Espalda/lateral:** usar dirección del objetivo y geometría nativa para clasificar posiciones; valorar daño neto de preview desde cada una, con bonus/reglas del motor. Costear PM/PA perdidos, reacciones al moverse y exposición final. Con varios enemigos, evitar buscar espalda de uno exponiendo la propia a los demás. Considerar la orientación final del NPC y el siguiente turno rival; el caller actual de dirección 3 debe sustituirse por el resultado legal real. Verificar dónde el motor actual aplica orientación: no asumir que un comentario sobre daño acredita todos los bonus geométricos.

**Elevación:** evaluar desde `(x,y,z)` real; probar aristas, obstáculos y alturas de LOS. Premiar una altura si mejora disparo, protección, control o movilidad futura; no introducir bonus de daño por Z sin regla nativa. Dos casillas con mismo XY/diferente Z no se fusionan. Caminos cortos en XY pueden estar desconectados por altura. Aplicar áreas/reacciones de terreno al recorrido, no solo al destino.

**Roles:** derivar afinidades del repertorio, no del nombre del monstruo. Melee busca alcance y presión; ranged conserva distancia útil y retirada; soporte cura déficit real y evita sobrecuración; controlador prioriza pérdida de recursos/posición útil; invocador solo invoca si el motor autoriza creación/cupo. Afinidades combinables y overrides de boss versionados. Un NPC con curación y daño no debe quedar encerrado en una etiqueta exclusiva.

## 4. Evaluación y coordinación

Score común sobre cambios de preview: bajas, daño efectivo, curación útil, prevención/armadura útil, recursos/control, exposición, posición, coste y coordinación. Pesos en DB por perfil/dificultad. No asignar valores numéricos definitivos sin medir: daño bruto, armadura y curación no tienen automáticamente el mismo valor. Una muerte o cambio de estado puede volver mejor otro plan.

Buscar secuencias con beam/poda y límites de nodos/tiempo, como Dofus; conservar alternativas para distintos objetivos. Primero candidatos baratos y luego preview exacto del shortlist; medir latencia/coste antes de simular cada spell en cada celda. Replanificar tras cast, muerte, desplazamiento, reacción o cambio de cooldown; no ejecutar a ciegas la cola del plan.

Blackboard por `fightInstanceId/team`: foco compartido, daño ya comprometido, destinatarios de cura, reservas de casillas/corredores e historial breve. Evitar overkill, sobrecuración, bloquear LOS de ranged y encerrar aliados. Foco cambia si murió, se hizo inmune o quedó inaccesible. Turnos independientes coordinados, sin mover todo el equipo simultáneamente. Solo world confirma reservas tras commit; expiran por revisión/turno y se eliminan al terminar encuentro. Ante reinicio, reconstruir desde checkpoint; memoria táctica no debe ser una segunda autoridad de combate.

## 5. Configuración, rendimiento y etapas

DB: perfiles/roles y overrides por referencia/familia, pesos, presupuesto de búsqueda, máximo de candidatos/acciones, cooldowns de decisión y reglas de dificultad, todos con versión. Infraestructura (URL, timeouts de transporte, credenciales) sigue en configuración de servicio. Catálogos compilados en memoria por hash; no consultar DB por nodo. Geometría registrada por hash para evitar reenviar miles de aristas por decisión. Limitar concurrencia y cancelación por encuentro; separar HTTP/búsqueda del hilo crítico del combate. Ante timeout elegir acción legal simple o terminar, con límite total de turno.

Orden concreto:

1. Autoridad de habilidades NPC y contrato completo; conservar Wonejo como regresión.
2. Intenciones/ranking deterministas con daño/curación/armadura/movimiento ya soportados, usando preview real.
3. Planes mover→cast→retirada; espalda/lateral/altura y orientación, con medición de rendimiento.
4. Coordinación: foco, reservas, soportes y casos multienemigo/multijugador.
5. Invocaciones, glifos y scripts de boss cuando el motor soporte sus operaciones; no simular soporte inexistente.
6. Balance por perfiles y corpus reproducible; TinyPolicy solo después, si aporta valor, entrenada con features Wakfu. No requiere Laya.

Trazas por decisión: candidatos, intención/rol, motivos de descarte, componentes de score, plan elegido, revisión, acción realmente confirmada y latencia. No guardar secretos ni datos ajenos al combate. Criterio de avance es resultado del combate y tiempos medidos, no porcentaje de habilidades con catálogo.

## Detalle de implementación

La arquitectura anterior se desarrolla en [contratos y algoritmo](CONTRATOS-Y-ALGORITMO.md), [diferencias técnicas](DIFERENCIAS-Y-PORTABILIDAD.md) y [plan por etapas](PLAN-DE-IMPLEMENTACION.md). El cotejo ampliado confirma `native_facing` y su uso condicionado por `native_localization_enabled` en el cálculo de daño.
