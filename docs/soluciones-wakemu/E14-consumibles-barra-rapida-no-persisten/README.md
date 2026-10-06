# E14 — Consumibles en barra rápida no persisten

Reporte del usuario: al poner un consumible (semillas, pan u otros) en accesos rápidos, cerrar y volver a entrar, el acceso no se conserva. Es un problema de persistencia de la barra, distinto de consumo o refresco del inventario.

[Investigación y solución](REVISION-RESPUESTAS.md). Estado: resuelto; asignación, salida normal y restauración reales verificadas con Audiluna.

[Esquema y transacciones propuestos para el servidor](PERSISTENCIA-SERVIDOR.md), derivados del contrato nativo y separados de las pruebas funcionales pendientes.

## Implementación actual

Guardado12091, validación de propiedad y restauración WORLD implementados y cargados en Docker sobre PostgreSQL. Dieciocho pruebas de codecs/bootstrap/persistencia pasan; la reconexión visual conserva Semilla de trigo ×5 y coincide con la fila PostgreSQL. Ver [evidencia](IMPLEMENTACION.md).
