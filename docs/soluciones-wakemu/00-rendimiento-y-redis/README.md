# 0. Retrasos al iniciar combates y lanzar hechizos

Reducir retrasos reales de entrada, inicio y hechizos; cumplir Redis primero y flush a 20 minutos sin pérdida de autoridad.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

19, 20, 32, 34 y almacenamiento adicional. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una solicitud de valor se aplica una vez; ninguna revisión nueva se borra por un flush antiguo; optimizar no cambia geometría legal, daños, orden de acciones o autoridad.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
