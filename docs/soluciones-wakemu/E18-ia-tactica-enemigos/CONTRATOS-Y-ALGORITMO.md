# Contratos y algoritmo detallado

## Modelo interno propuesto

Interfaces conceptuales del diseño. La implementación actual usa
`NativeProvider` en world y `ForecastAdapter`/búsqueda acotada en ai-service;
no existe una clase única con todas estas firmas:

```python
class TacticalAdapter:
    def capabilities(self, snapshot, actor_id): ...
    def reachable(self, snapshot, actor_id, budget): ...
    def legal_casts(self, snapshot, actor_id, origin): ...
    def preview(self, snapshot, action, forecast_seed): ...
    def threat(self, snapshot, actor_id, positions, budget): ...
    def terminal(self, snapshot): ...
```

`reachable` devuelve posición, ruta, coste PA/PM/PW, dirección resultante y consecuencias del trayecto; puede conservar varias rutas a igual destino si sus reacciones difieren. `legal_casts` usa propiedad, tabla condicional, límites de uso y target selector reales; un UNKNOWN se registra y no equivale a legal. `preview` devuelve estado nuevo, afectados, deltas y confianza, sin paquetes enviados ni escrituras de mundo. Un delta incluye salud/armadura, recursos, estado, muerte, posición/dirección, summons/zonas y disponibilidad futura.

Una alternativa guarda `actions`, `intent`, `target`, `final_position/direction`, `outcome_features`, `score_components`, `unknown_dependencies` y `source_revision`. Una etiqueta HEAL/DAMAGE no basta: conservar efecto, objetivos, condiciones, tipo de duración y restricciones para filtrar correctamente.

## Pipeline por decisión

1. World fija actor actual, revisión y catálogo/policy. Si espera ACK de una acción, no inicia otra decisión para ese actor.
2. Resolver habilidades propias/estados que las otorgan y separar ejecutables de bloqueadas. Clasificar capacidades según el estado actual, no solo catálogo estático.
3. Generar opciones desde la posición actual y rutas alcanzables relevantes: melee/alcance mínimo, tiro, espalda/lateral, ayuda a aliado, salida de zona, retirada. Evitar todas las celdas×todos los hechizos×todos los blancos sin poda.
4. Estimación barata prioriza candidatos, conserva alternativas por intención/blanco y protege acciones de bajo daño pero alto control. No eliminar el único heal o escape porque su daño sea cero.
5. Preview real del shortlist. Expandir secuencias legalmente desde cada estado intermedio. Recalcular habilidades/alcance/costes si una acción los modifica.
6. Evaluar beneficio inmediato, riesgo del siguiente turno rival y coordinación. Deduplicar con clave que incluya posiciones/direcciones, recursos, estados/revisiones, usage y ocupación; no fusionar estados con distinto cooldown.
7. Elegir mejor plan legal dentro del deadline. Empates: menor riesgo/coste; desempate estable por ID, o variación reproducible por semilla de combate configurada. Siempre admitir end_turn.
8. World valida plan contra revisión y ejecuta primera acción mediante transición transaccional existente. Confirma resultado y sincroniza; solo entonces actualiza memoria de equipo.
9. Recalcular si hubo consecuencias distintas, estado cambió o plan ya no es legal. Terminar con límite total de acciones/nodos/tiempo, incluso si un hechizo cuesta cero.

No presupuestar solo por PA: WP, PM, límites por blanco/turno, cooldown, estado y duración impiden loops. `combat_spell_usage.validate_usage/consume_usage` ya ofrece parte de esa autoridad; debe usarse desde la transición NPC.

## Valor de una posición y del plan

Modelo propuesto:

`score = beneficio_equipo − coste_recursos − amenaza_rival − interferencia_aliados − incertidumbre`

Separar componentes para explicar decisiones. Beneficio usa daño neto y bajas, curación realmente restaurada, protección que evita daño probable, control que impide acciones y posición útil. No sumar HP curado fuera de déficit, ni daño sobre muerto, ni armadura que vence antes de amenaza. Penalizar daños propios/friendly fire; sacrificio solo se acepta si el resultado de equipo compensa y la operación está soportada.

Amenaza: para cada rival relevante generar su mejor ataque legal desde sus posiciones alcanzables con presupuesto pequeño. Evaluar cantidad de rivales capaces de golpear y daño neto, incluyendo espalda propia, AoE y control. No sumar todos sus hechizos como si pudiera lanzarlos sin presupuesto. Usar proyección aproximada explícita si no hay soporte; una mecánica de tipo puzzle puede requerir un adaptador explícito de esa mecánica. Las conductas normales se resuelven con arquetipos/capacidades, sin reglas por monstruo.

El servicio ya admite `rivalForecasts`: compara secuencias certificadas desde
una proyección inicial del turno de cada rival y toma su mejor respuesta.
Valida cobertura consistente entre alternativas, rosters, pasos tipados y
cotas globales; expone modo/dependencias y plan elegido en la traza. La suma
de mejores respuestas independientes es una estimación de riesgo, no una
simulación conjunta de la iniciativa. El productor world todavía debe
conectar esas proyecciones; no confundir este contrato con amenaza activa
en los encuentros desplegados. Véase el README de `server/ai-service`.

Roles no sustituyen utilidad: ranged no huye si puede rematar sin riesgo; healer no desperdicia turno curando a alguien full HP; melee no busca el foco lejano si tiene blanco útil alcanzable. El foco compartido es una preferencia, no un mandato.

## Ejemplos concretos de decisiones

**Melee/espalda:** comparar A=cast desde frente, B=rodear dos pasos y cast desde BACK, C=retirada. Si el efecto ignora localización, B no recibe premio ficticio. Si B mejora daño pero activa zona peligrosa/expone al segundo rival, contabilizarlo. Registrar `facingGain`, `movementCost`, `reactionLoss`, `enemyThreat`.

**Ranged/altura:** comparar casilla baja con tiro bloqueado, plataforma alcanzable con tiro válido y posición lejana sin salida. La plataforma vence por ataque legal/menor amenaza, no por bonus abstracto de altura. Si faltan aristas o topología, no inventar acceso/LOS.

**Equipo:** melee ocupa frente para contener; ranged conserva corredor de tiro; soporte cura al aliado en mayor riesgo. Tras primer NPC matar al foco, el siguiente recibe snapshot nuevo y elige otro blanco. Si el plan de cura deja de ser útil por una cura anterior, invalida reserva. No ejecutar todos los NPC en paralelo saltándose iniciativa.

## Configuración y almacenamiento

Tablas propuestas: `ai_policy_versions` (versión/hash/esquema), `ai_profiles` (pesos y límites), `monster_ai_profiles` (ref/familia→perfil), `ai_semantic_overrides` (condición y justificación exclusivamente para mecánicas de tipo puzzle). Las referencias/familias solo asignan arquetipos reutilizables; no definen árboles de reglas específicos por monstruo. Validar pesos/rangos al cargar y conservar versión por combate; un cambio en DB no altera silenciosamente un plan pendiente. Perfil normal sin script específico usa capacidades del repertorio.

Memoria operativa de equipo en Redis o en runtime del encuentro: UUID/equipo/revisión, foco, reservas, historial acotado y TTL. Configuración es durable; reservas son temporales/reconstruibles. No hace falta almacenar un plan SQL por cada nodo. Si una reserva ayuda a coordinar workers, commit compare-and-set con revisión; no compartir solo por ID numérico de pelea.

Snapshots completos: caché immutable por hash para topología y catálogos; delta dinámico por revisión para actores/estados. `source_snapshot` es candidato de integridad, pero puede ser demasiado voluminoso para enviar: definir DTO mínimo **completo para decisiones** y probar que cambiar cualquier campo relevante cambia stateKey.
