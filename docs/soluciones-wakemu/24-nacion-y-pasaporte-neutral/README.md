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
