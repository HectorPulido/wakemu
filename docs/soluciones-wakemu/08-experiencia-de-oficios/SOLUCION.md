# Solución propuesta — 8

Persistir XP de oficio, calcular nivel y notificar progreso por acción confirmada.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Extraer curva y reglas de recompensa

Inventariar IDs de oficio/acción y curvas disponibles en el cliente/catálogos. La profesión actual conserva nivel pero no XP; no usar la curva de combate ni +100 de una captura como fórmula universal. Definir éxito/fallo, receta, dificultad y nivel efectivo.

## 2. Diseñar migración coherente

Añadir XP total y revisión a profesión, con invariante nivel=curva(XP). Para niveles existentes sin XP elegir mínimo de su nivel u otra política explícita y preservar datos. Una profesión no aprendida no se crea automáticamente por paquete malicioso.

## 3. Conceder una vez por operación

Integrar recibo en plantación, cosecha y crafting. Consumir/crear productos y otorgar XP juntos; registrar start/end nivel/XP para notificar delta sin recalcular en retry. Aplicar multiplicador solo si se define para oficios, separado del XP de combate.

## 4. Sincronizar delta y total

Verificar 12916 y bootstrap de oficio con el parser nativo. Emitir delta antes del snapshot absoluto si el cliente lo suma, evitando doble incremento. Actualizar nivel, nuevas acciones y presupuesto de desbloqueos sin exigir reconexión.

## 5. Validar progreso y recovery

Probar umbral exacto, varios niveles por recompensa, cap y migración. Reabrir journal con recibo confirmado; no volver a premiar ni reducir nivel. Documentar resultados por oficio, no una sola acción genérica.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

XP total y nivel son coherentes; una acción confirmada no concede dos premios por reconexión.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
