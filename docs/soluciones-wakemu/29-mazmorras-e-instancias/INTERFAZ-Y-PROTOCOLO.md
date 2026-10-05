# Interfaz de mazmorra: contrato acreditado

## Contexto enviado al entrar y volver del combate

`eVa.b(eUZ)` serializa `ProtoDungeon`; `eVa.eD` lo decodifica. Se inspeccionó el descriptor y se ejecutó un roundtrip con valores sintéticos.

| Campo protobuf | Nombre nativo | Autoridad necesaria del servidor |
| --- | --- | --- |
| 1 | maxLevel | Límite de nivel de instancia; selecciona modo competitivo mediante `GetInstanceLevelMax()` |
| 2 | difficultyLevel | Dificultad vigente, congelada durante encuentro |
| 3 | isDifficultyAvailable | Disponibilidad acreditada para esa instancia |
| 4 | canIncreaseDifficulty | Permiso de cambiar dificultad |
| 5 | isfightInProgress | Estado autoritativo de combate |
| 6 | isCompetitiveCancelled | Cancelación competitiva; consumidor final aún por cotejar |
| 7 | allowedIds | Lista de identidades autorizadas; política exacta pendiente |
| 8 | minLevel | Límite mínimo de nivel del contexto |

Fixture: `08641003180120002800300038b9604055` devuelve máximo 100, mínimo 85, dificultad 3, disponible, aumento deshabilitado e ID autorizado 12345. Son valores de prueba, no reglas oficiales de Jalató.

El bootstrap actual de `native_transports` inserta `0800100218002001280030004000` en 13974, bloque de contexto: máximo/mínimo cero, dificultad 2, disponibilidad falsa, aumento verdadero, sin IDs autorizados. Ese contexto no procede de una sesión de mazmorra. Al retornar del combate, el dispatcher vuelve a usarlo. La solución del servidor debe proporcionar el contexto de la instancia tanto al entrar como después del combate; cambiar solo el mapa no lo resuelve.

## Progreso personal frente a avance de sala

`ProtoDungeonProgression`/`eUV` mantiene pares enteros. `bpU` consulta el valor por definición de mazmorra y lo usa para coronas de dificultad. **No debe reutilizarse como contador de sala actual.** El avance de una sesión necesita autoridad separada, ligada al encuentro y a la instancia viva.

Se acreditó un mensaje de actualización: **12520 (`cuD`)**, cuerpo big endian `i64 personaje + i32 definición de mazmorra + i32 dificultad`. `cja` busca al personaje y ejecuta `dtI().fS(definición,dificultad)` cuando tiene contexto válido. Fixture 12345/90/3: `00000000000030390000005a00000003`; decodificación correcta. El control truncado de 15 bytes lanza `BufferUnderflowException`. `cuD.dp` devuelve `false` aun habiendo decodificado; no es un código de rechazo.

Este mensaje no aparece en el dispatcher actual y no acredita por sí solo la política de actualización de récord: aún se debe cotejar cuándo se comunica y si se conserva el máximo. Tampoco identifica un mensaje para puertas o progreso de sala.

## Cierre de combate probado y límite

Pasaron diez pruebas existentes de `combat_lifecycle`, `combat_health`, `player_death` y `combat_abandon`: resultado/retorno, pérdida sin premio, salud cero sin resurrección implícita, abandono y callbacks repetidos sin sobrescribir estado posterior. El servidor ya tiene recibos idempotentes de salud y premio; deben conservarse al integrar mazmorras.

No se probó una victoria/derrota real dentro de mazmorra, ni retorno con varios personajes ni apertura de puerta. Falta cotejar petición/respuesta del selector de dificultad, mensaje para contexto actualizado y acceso por party. [Fixtures, comando ejecutado y hashes del código](probe-contexto-ui-y-retorno.json).
