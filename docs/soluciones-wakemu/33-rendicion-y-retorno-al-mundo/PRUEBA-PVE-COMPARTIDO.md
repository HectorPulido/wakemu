# Aceptación completa: rendición PvE compartida

Estado: source integrado y pruebas automáticas aprobadas; pendiente desplegar y probar cliente. No ejecutar como confirmación de la imagen r14.

Usa dos clientes con Wayo y Krozz, en el mismo mapa, fuera de combate. Anota XP, kamas y objetos de ambos. No necesitas objetos adicionales.

1. Con Wayo escribe en General `!mob 4196 1 1`. Ataca al Mimic dulce; todavía no pulses **Listo**.
2. Con Krozz haz clic derecho en la espada del equipo de Wayo y selecciona **Unirse**. Ambos deben aparecer en el mismo combate, en el mismo equipo.
3. Pulsa **Listo** en ambos. Wayo y Krozz deben poder moverse y atacar durante su turno. Deja al cofre vivo.
4. Wayo pulsa la bandera de rendición y confirma. Wayo debe volver al mapa, poder caminar y abrir el inventario. Krozz debe conservar la pelea, con el Mimic vivo; sus turnos siguen avanzando. Wayo no gana XP, kamas ni botín por rendirse; conserva el daño recibido.
5. Con Wayo inicia otro combate usando `!mob 4196 1 1`, ataca al nuevo cofre y ríndete. Debe poder iniciar y abandonar sin «Fight/actor already registered», mientras Krozz continúa su pelea anterior.
6. Krozz derrota al primer cofre. Solamente Krozz recibe las recompensas. El inventario y saldo de Wayo no deben aumentar por esta victoria.
7. Repite pasos 1–2, sin pulsar **Listo**. Wayo se rinde durante colocación. Krozz permanece en colocación; pulsa **Listo**, ataca y ríndete. Ambos vuelven a caminar y pueden iniciar otro combate.
8. Repite pasos 1–3. Wayo cambia de personaje desde el menú mientras Krozz continúa. Vuelve a seleccionar Wayo. Debe entrar al mapa, sin reaparecer dentro de la pelea. Krozz conserva su turno y puede rendirse.
9. Repite pasos 1–3. Wayo se rinde y Krozz también inmediatamente. Ambos vuelven al mapa y pueden caminar, abrir inventario y combatir.
10. Cierra y abre ambos clientes. Entra con los mismos personajes: heridas, XP, kamas y objetos se conservan; no hay ventanas de combate residuales ni reservas que impidan atacar.

Si no aparece la espada o **Unirse**, detén la prueba en el paso 2 e informa ese resultado: es requisito del sistema de unión/marcadores, no confirmación del retiro compartido.

Automatización: 87 casos del dominio/checkpoints/recompensas y 4 del dispatcher. Incluyen interrupción antes del terminal, reemplazo de sesión, regreso sin registry después de reinicio, ACK tardío tras abandono del último compañero y rechazo de ACK de una sesión vieja.
