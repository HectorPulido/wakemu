# 26. No se pueden añadir merkagemas

## Live r55 corrections — source verified, deployment pending

Hector reported gem recovery blocked, exterior actors retained and furniture
inventory use rejected as a seed. The corrected native flow learns furniture
through 12-byte generic item actions, persists account knowledge (migration083),
then places virtual collection furniture; packing does not refund the learning
item. Gem serialization now fixes only the entrance primary, and bag transitions
clear the previous map actors. **50 focused tests passed with zero skips**, plus
real-client Java packet oracles. No visual acceptance or deployment is claimed
here; use the complete acceptance guide linked below after integration.

## Haven Bag extension — source status, 2026-10-09

Hector confirmed decorative gem assignment, but explicitly reports that persistence
is missing or not accepted. Do not mark gem persistence accepted. Inventory-backed decoration placement,
packing, private garden planting/harvesting and portable native crafting are now
implemented in the shared checkout, pending complete-image integration and
publication of `haven-bag-furniture-catalog.json`. This is not a deployment or
visual acceptance claim. Selling remains lower priority and outside this scope.
See the [complete acceptance journey](../26-insertar-y-retirar-merkagemas/HAVEN-BAG-SYSTEM-ACCEPTANCE.md)
for exact item grants, expected results and current limits.
Focused source verification: **67 tests passed, zero failures/skips**, including
real PostgreSQL ownership, garden lifecycle and gem rearrangement persistence.
The current deployed image and reported visual persistence defect remain unaccepted.

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

## Public guest policy audit — 2026-10-11

Hector reports the bag generally works and requests unrestricted guest access. The current source already allows every nearby visitor into a published bag and sends unlocked/public room rights, while preserving owner authority over chest, furniture, gems and configuration. Guest gardens and portable crafting use the visitor's inventory and the visited layout. No additional gameplay edit was needed in this audit. The owner's active connection must publish the exterior bag; this is not offline discovery. See [public guest authority and complete acceptance](../../reports/HAVEN-BAG-PUBLIC-GUEST-AUDIT-20261011.md). A dedicated bag Zaap is not implemented: map9 and portable furniture contain no verified native Zaap source; see [native inventory](../../reports/HAVEN-BAG-ZAAP-AUDIT-20261011.md). Keep that scope distinct from working bag exit.
