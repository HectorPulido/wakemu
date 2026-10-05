# Solución propuesta — 24

Eliminar nación heredada en personaje y lugares mientras la mecánica nacional no esté implementada.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Identificar cada superficie

Listar nación del personaje, pasaporte como objeto/estado, selector de personaje, territorial/clan y nombre visual. El usuario añadió neutralidad de lugares: no basta tocar nación propia. Leer secciones de fixture/replay y caches antes de atribuir Amakna a item inicial.

## 2. Localizar carriers heredados

Decodificar bytes nativos de selección/entidad/mundo, comparar personajes nuevos y antiguos con perfil limpio. Buscar referencias a nación en datos del mapa/clan; wire ya limpia algunas secciones. No reemplazar todas las apariciones del número de Amakna en buffers: puede ser otro campo.

## 3. Modelar neutralidad explícita

Definir IDs/status nativos de sin nación para personaje y zona; persistir o resolver neutral mientras no haya mecánica. Un valor 0 no acredita neutral en todos los codecs. Guardar procedencia/version, separar nación de geografía/nombre de la capital y ciudadanía/pasaporte.

## 4. Sustituir cada sección por estado propio

Bootstrap/selección/contexto territorial deben emitir lo mismo y no replay de otra cuenta. Configurar territorios neutrales como exige el usuario sin romper acciones de ecosistema/transporte ni catálogos visuales. Migrar solo valores heredados probados, sin borrar progreso legítimo.

## 5. Verificar reload y futuras naciones

Probar dos cuentas en regiones con nación distinta de catálogo, reconnect y transición de mapa. Cuando se implemente ciudadanía, la misma autoridad debe poder activar nación real sin mantener hardcode neutral en ramas ocultas.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Ni personaje ni lugar reciben alineamiento de otra cuenta o captura; neutralidad es explícita y consistente.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
