# 32. Permiso `is_admin` para comandos `!` del chat

Autorizar comandos por cuenta y cerrar rutas alternativas antes de exponer el servidor.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

13, 21 y E03. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Autenticación, rol, ownership y lease se comprueban separadamente antes de cualquier mutación.
