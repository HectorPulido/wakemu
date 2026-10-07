# 8. No aumenta la experiencia de los oficios

Persistir XP de oficio, calcular nivel y notificar progreso por acción confirmada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**✅ Solucionado totalmente.** El usuario confirmó XP y subida de nivel en recolección, plantación, Peletero y fabricación. Adael fabricó 10 Pólvoras (2.000 XP) y 100 Bombas (20.000 XP), alcanzando Minero nivel 16; captura y recibos PostgreSQL coinciden. Crafting se desplegó inicialmente en `3523a0a5` y sigue incluido en la versión activa `1ed06b10`, con validación automática de consumo, premio único, cancelación y reconexión.

La carga dinámica de mesas sigue abierta en los issues 30 y 35. Los apartados siguientes conservan evidencia histórica; sus estados anteriores no sustituyen este estado vigente.

## Dependencias

5, 6, 30. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

XP total y nivel son coherentes; una acción confirmada no concede dos premios por reconexión.

## XP visual confirmada en cosecha — 6 de octubre

Con el personaje Prueba Oficios, el cliente mostró+50XP de Herbolario por Cardo60 (acción1475, producto11447) y+50XP de Leñador por Fresno139 (acción930, producto11438). Recibos, productos y XP quedaron confirmados en PostgreSQL: Herbolario110 y Leñador50 tras estas pruebas. Los recursos se prepararon como fixtures; no acredita fabricación, recetas ni todas las actividades de oficio. Esta evidencia histórica precede a la confirmación de fabricación que completa el issue.

## Confirmación de fabricación del usuario

Adael: receta2227 lote10 completed,2000XP; receta2475 lote100 completed,20000XP. Usuario confirma100Bombas y Minero nivel16; captura muestra producto100 y delta20000XP. Las mesas fabrican correctamente tras cargar. Se investiga por separado la carga dinámica de los interactivos al transportar/caminar: faltan objetos y reaparecen al recargar, patrón relacionado con35Zaap.
