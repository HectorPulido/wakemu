# Información pendiente — 16

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Construcción de `cva/12044` desde un encuentro activo y publicación/retirada de marcador `13753`. | Integrar snapshot de actores/topología/timeline actual y verificar consumidor de escena externa | Impide certificar entrada TLS; `13753` no está resuelto como marcador simplificado |
| 2 | Política global de privacidad y respuesta ante entrada no permitida. | Conectar una política del servidor y comprobar rechazo/ocultamiento con el cliente | El registro exige autorización literal `True`, pero aún no hay handler ni respuesta de rechazo probada |
| 3 | Entrega ordenada de eventos posteriores al snapshot y retorno al mundo al salir o terminar. | Conectar fanout a batches compartidos, `12154`, desconexión y cierre de combate; probar con dos clientes | La cola aislada está probada; no hay fanout ni restauración en el dispatcher |

Decisión del usuario para 3: al entrar se debe ver el estado actual completo; después, solo actualizaciones en tiempo real, sin replay desde el inicio.

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
