# 24. Pasaporte de Amakna por defecto

Eliminar nación heredada en personaje y lugares mientras la mecánica nacional no esté implementada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**En revisión, con una brecha de serialización corregida en fuente.** Los serializadores publican `NATION_ID=0`; además, `PASSEPORT_INFO` ahora se reemplaza explícitamente por su default nativo `00`, en vez de copiar ese byte de la plantilla. La neutralidad visual del pasaporte y la neutralidad de territorios aún no tienen aceptación en cliente. No existe ciudadanía configurable persistida en el modelo actual.

## Dependencias

13, 28, 32. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Ni personaje ni lugar reciben alineamiento de otra cuenta o captura; neutralidad es explícita y consistente.

[Pasaporte nativo y carriers actuales](REVISION-RESPUESTAS.md) · [Prueba manual general](PRUEBA-GENERAL.md).

## Auditoría de fuente y r19 — 7 de octubre de 2026

Gate local dirigido: `PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 .runtime/local/verification-venv/bin/python -m unittest test_wire test_social -q` — **39/39 OK**. Se verifica la serialización neutral de nación, `PASSEPORT_INFO=00` y la adaptación acotada de los carriers sociales. Es un gate de codecs/serializadores; no sustituye la comprobación visual de `/passport`.

El manifiesto disponible para r19 indica base r18, 354 módulos de aplicación sin cambio y un único módulo cambiado (`wakfu_server/api.py`). Por tanto, el alcance documentado de r19 no incluye un cambio de nación en `wire.py`, `characters/social.py` ni en los catálogos de layouts/defaults. No se atribuye a r19 una corrección visual del pasaporte.

La siguiente evidencia que cerraría la brecha es una aceptación con un personaje actual: abrir `/passport`, comprobar `pvpLadderEntry.nationId == 0` y el texto Neutral; salir a selección, volver a entrar y repetir. La nación de territorios sigue abierta: los catálogos inspeccionados no acreditan un carrier mapa→nación, así que no se asigna ni borra ownership por inferencia.
