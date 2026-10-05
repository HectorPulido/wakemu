# Solución propuesta — 18

Permitir elegir dirección legal durante colocación, sin consumir recursos ni exigir turno activo.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Capturar solicitud en colocación

Registrar 13655, actor/dirección, fase y readonly state. El códigoapply exige active/turno/ACK libre y por ello rechaza placement. Los cardinales actuales 1/3/5/7 no acreditan permitir direcciones arbitrarias.

## 2. Separar autorización por fase

Mantener ruta activa con turno y ACK; crear rama placement que requiere actor propio en su celda/equipo y fase abierta. Decidir si ready bloquea edición; carrera listo/orientación se valida contra revisión. No eliminar globalmente todas las comprobaciones existentes.

## 3. Definir respuesta nativa de colocación

Comprobar si 13494 acción activa puede usarse antes del scheduler o si hay carrier específico de fase. Validar parser y secuencia/callback antes de enviar. No gastar AP/MP, avanzar turno ni abrir un ACK de acción incompatible con placement.

## 4. Persistir facing en encuentro

Guardar dirección del actor y versión; ambos participantes y bootstrap de reconnect usan ese valor. Inicio de combate conserva facing en vez de regenerarlo desde snapshot base. World-facing y fight-facing son estados separados.

## 5. Probar frontera de inicio

Elegir todos los cardinales, listo/start y reconnect; orientación tardía se aplica a una fase o se rechaza limpiamente, nunca queda pending atascado. Un actor ajeno no cambia facing ni consumos.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Girar en colocación cambia solo facing de actor propio y no debita AP/MP ni inicia un turno.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
