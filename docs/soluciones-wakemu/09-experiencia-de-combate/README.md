# 9. No hay experiencia ni subida de nivel por combate

Conceder XP no nula según política configurable y refrescar todos los desbloqueos al subir nivel.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

🧪 **Solucionado totalmente — máxima prioridad por instrucción del usuario.** La configuración anterior concedía0XP por victoria; la autoridad SQL activa ahora calcula recompensas positivas. Se implementa la fórmula del proyecto Dofus de referencia con parámetros SQL versionados, conservando la curva Wakfu y sin copiar la excepción artificial del nivel199. Migración041:17 pruebas de política aprobadas y37 pruebas combinadas de contexto/cierre/recompensas. Catálogo SQL cubre200 niveles mediante una política local derivada del export Dofus, con overrides por monstruo/nivel. Resolver conectado al cierre en la misma transacción; smoke completo aislado aprobado (cruce de nivel, XP/kamas, drop, overflow, reclamación y reconexión). Imagend990b252 desplegada y saludable,43 migraciones y259 pruebas de imagen aprobadas. Pendiente [aceptación manual](PRUEBA-GENERAL-RECOMPENSAS.md).

## Dependencias

10, 17, 33, 34 y E06. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

El recibo fija recompensa y versión; el nivel visible, XP y hojas nunca quedan parcialmente actualizados.

## XP cero en la ventana del personaje

[Diagnóstico específico y cálculo nativo](XP-CERO-EN-VENTANA.md): el total persistido de «Prueba Yopuka» coincide con el umbral del nivel 200; la barra muestra el avance dentro del nivel. Esto no cierra el problema de recompensas por combate.

## Confirmación manual del merge

El usuario confirma «Todo funciona bien» tras la prueba general de recompensas e inventario, incluida persistencia tras reentrada/reinicio. XP y subida de nivel quedan confirmadas; imagen9af0658c,200 pruebas automatizadas y smoke nativo de combate/retorno/reconexión.
