# 34. Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta

Completar desbloqueo, hojas, guardado, activación autoritativa, estadísticas/deck y persistencia de builds.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado parcialmente.** El usuario verificó creación, apertura, activación, alternancia, edición y borrado de builds, con cambio de personaje y reinicio. E10 también quedó confirmado: equipo propio de cada build, persistencia y borrado sin pérdida ni duplicación. Issue17 acredita aptitudes +5/+10, alternancia sin acumulación y reset persistente.

Pendientes: cruce del umbral de desbloqueo49/50/51, capacidad completa24, modulación/salud y consumo del deck seleccionado en combate. Este último permanece coordinado con la sesión de hechizos; no se cambia su semántica para cerrar el issue.

## Dependencias

9, 17, 22 y E04–E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Metadata, equipo, aptitudes, deck y selección comparten índice y revisión; el check visual Activa no prueba autoridad del servidor.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
