# Información pendiente — 12

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Integrar opcodes12117/13520 y respuestas13179/12708 al dispatcher. | Handler con leases + prueba TLS/GUI | El contrato de bytes ya está cotejado; falta el recorrido vivo |
| 2 | Resultado nativo y retorno a mundo del duelo. | Cotejar presentation carrier y probar ambos clientes | El resultado persistente ya excluye XP/kamas/drops y restaura HP |
| 3 | Expiración visible, invitaciones tardías y política multi-control. | Cotejar cliente y probar carreras/reconexión | La autoridad actual expira localmente tras60s y exige dos cuentas |

1. Revisa todo. Nada que decidir
2. en los desafios al salir se te rellena la vida, no hay teletransportacion, xp o duelo
3. el que se desconecta pierde, pero queda en el mismo mapa, posicion etc. estos desafios son amistosos

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
