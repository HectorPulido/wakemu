# E10. Registro de equipo de nuevas builds

El servidor ya no depende de `equipment_set`, helper sin callers que solo recorría entradas antiguas. El flujo actual publica un registro derivado del catálogo común mediante `equipment_registry`, y las respuestas de guardado incluyen ACK, carrier12393, aptitudes12103 y snapshot de estadísticas13046. Las pruebas verifican la nueva entrada, índices dispersos y persistencia/reapertura.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md)

## Estado y límites

**Solucionado totalmente.** El gate PostgreSQL de aptitudes/builds/equipo pasó 54 pruebas. Comprueba guardado, reapertura, emisión del registro con una nueva build y conservación de otros índices/personajes. La aceptación nativa previa confirma el carrier12393 y reemplazo del registro del personaje en el modelo Java. El6 de octubre el usuario completó los seis pasos con Audiluna: creación y activación, panel/equipo visibles, guardado, alternancia con equipo propio de cada build, cambio de personaje y reinicio del cliente conservando el equipo; borrado y reentrada sin pérdidas ni duplicaciones.

No se modificó el motor de hechizos en esta revalidación.
