# Identificadores y valor del efecto disparador

`eII.aU` consulta primero `eZR.fSd`; si no existe, toma `eVt.fLP`. `eZR.I(source)` instala temporalmente `fSd` mientras evalúa el criterio del listener y lo limpia después. El contexto corresponde al efecto fuente; nunca al caster, a la definición del listener o al último estado del actor.

- `GetTriggeringContainerStateId` token172/claseeLI: sin fuente, contenedor nulo o contenedor no`fyW` devuelve0; para `fyW` devuelve `guI()` como short firmado.
- `GetTriggeringEffectActionId` token174/claseeLK: sin fuente devuelve-1; con fuente devuelve `source.baZ().awM()`, la familia de acción, distinta de `aZE()` (reference del efecto). Acepta profundidad integral constante, default1. El bytecode repite `eII.aU` sobre el mismo contexto, sin recorrer ancestros: profundidad positiva2 devuelve la misma fuente; no positiva devuelve-1.
- `GetTriggeringEffectValue` token180/claseeLP: sin fuente devuelve0; con fuente devuelve `eZR.getValue()` como int firmado. No es el nivel del hechizo ni un daño inferido del HP.

`combat_trigger_identifiers` extrae el contenedor auténtico mediante `NativeRetainedRuntime.container`, incluyendo el scope de `fyW` vigente durante sus hijos. Los productores ordinarios de daño/curación adjuntan el descriptor y `effect_class` al `NativeEventSource`; replay preserva esos campos mediante `asdict`. El adaptador sólo publica hechos acreditados. Una fuente presente sin metadata mantiene el resultado desconocido; no se confunde con fuente o contenedor ausente.

`ProbeNativeTriggerIdentifiers.java` ejecuta los getters reales: fuente nula, `fLP`, prioridad`fSd`, referencia short negativa, acción400 frente definición987654, profundidad0/2 y valor firmado-25. PASS. Cinco pruebas del evaluador verifican esas distinciones y roundtrip del evento. No se agregaron eventos de inicio de combate por inferencia.

`GetTriggeringEffectId` token/classeeLM devuelve `source.eZR.aZE()` (reference de definición). No devuelveUID ni familiaawM. El parámetro de profundidad comparte semánticaeLK: default1, positiva consulta la misma fuente, no positiva-1. NativeEventSource.generic_effect ya contiene lareference auditada; se publica mediante campo explícito triggering_effect_reference_id. Prueba Java contrasta definición987654/acción400 y verifica profundidad1/2/0/-1/fuenteausente; una sexta prueba Python cubre datos desconocidos y separación deUID123. PASS.
