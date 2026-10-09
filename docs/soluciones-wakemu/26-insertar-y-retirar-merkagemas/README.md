# 26. No se pueden añadir merkagemas

Transferir gemas propias entre inventario y ranuras del merkasaco sin duplicarlas.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Cambio hecho no confirmado.** Inserción y retirada están desplegadas en imagen78e8ae29 con migración051. Pilas, transferencia primaria/secundaria, rechazo de sala protegida, reintentos y reconexión pasaron pruebas PostgreSQL y TLS. Gate de imagen conjunto80/80; combate e inventario verificados sin modificar sus208 módulos.

Falta la aceptación visual de la [prueba completa](PRUEBAS.md). No se declara resuelto por las pruebas automáticas solamente.

## Dependencias

22, 23, 30 y 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Una UID está en inventario o slot, nunca ambos; retirada no elimina contenido ni concede gema nueva.

[Contratos ejecutados de inserción y retirada](REVISION-RESPUESTAS.md).

## Versión desplegada — 7 de octubre

Imagen78e8ae29 (`wakfu-local-world:item-options-verified`), world healthy y HTTP200, migraciones049–051 aplicadas. Gate imagen80/80 y TLS elementos12487/13766, inserción/retirada de gemas con pilas, reintentos y reconexión aprobados. Smoke combate y recompensas aprobado;208 módulos de combate idénticos a la versión anterior. Backup previo comprobado754 entradas.

Aceptación visual pendiente. La identificación/sorteo13787 y la autoridad de combate compartido052 siguen fuera de la imagen activa. Los apartados anteriores reflejan etapas históricas.

## Contexto oficial — 8 de octubre de 2026

El usuario abrió Merkamundo y un cofre durante la captura oficial. Merkamundo y Merkasaco son sistemas distintos: verificar el destino y objeto exactos antes de reutilizar paquetes. El nuevo issue41 cubre el cofre de Merkasaco; mantener transferencias, capacidad, pertenencia y persistencia separadas de inserción/retirada de merkagemas. Referencia privada: `.runtime/official-dungeon-capture/`, con manifiestos y contratos de versión registrados. No se declara aceptación ni cambio desplegado por esta captura.
