# Solución propuesta — E02

Reemplazar el contrato de recuperación mal serializado para todos sus consumidores.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Listar todos los callsites

Buscar synchronization y 13713, catalogar éxito/rechazo y formato esperado. Una prueba de bolsos no cubre transferencias, equipamiento o otros consumidores; cada callsite debe contar con caso de fallo y estado previo.

## 2. Probar parser byte por byte

Construir payload actual mínimo y reproducir con el JAR fuera de UI; validar consumo completo y secciones de entidad. Documentar cwY/chK/biB.as y orden/niveles. Identidad correcta no valida que el resto sean bolsas compatibles.

## 3. Elegir carrier correcto

Si 13713 exige entidad usar serializer completo canónico de esta cuenta; si existe carrier específico de inventario, verificar opcode/handler/orden y usarlo. No añadir byte/header por intuición ni reutilizar captura de otro jugador. Revisar seguridad de reaplicar equipo/XP/mapa sobre entidad ya cargada.

## 4. Generar snapshot después del rechazo

No confirmar mutación optimista inválida; cargar estado actual de la lease/owner y resolver journal pendiente. Serializar inventario y características canónicas sin doble bonus. Enviar error y rollback en el orden probado para liberar bloqueos del cliente.

## 5. Regresión transversal

Decodificar cada respuesta y luego pruebas UI de rechazo en stacks, slots ocupados, UID ajeno y capacidad. Comparar SQL/journal/cantidad antes/después, PdV y mapa; negative ACK no basta si el mensaje posterior corrompe representación.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Toda respuesta se valida por su parser nativo; un rechazo no altera el estado visual de otros dominios.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
