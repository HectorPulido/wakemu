# 32. Permiso `is_admin` para comandos `!` del chat

Autorizar comandos por cuenta y cerrar rutas alternativas antes de exponer el servidor.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** Backend y chat real verificados. El6 de octubre el usuario confirmó la prueba completa desde una cuenta nueva con `is_admin=false`: `!mob 4 8 1` rechazado sin crear monstruo, `!pos` permitido y continuidad de movimiento/inventario. [Implementación, pruebas, operación y límites](IMPLEMENTACION.md).

## Dependencias

13, 21 y E03. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Autenticación, rol, ownership y lease se comprueban separadamente antes de cualquier mutación.
