# Prueba completa de intercambio entre dos clientes

**Prueba ya realizada por el usuario — 2026-10-07.** Confirmó cancelar/rechazar invitaciones, kamas actualizadas de inmediato, cancelar intercambio activo y persistencia tras selector/reinicio. El retiro parcial del paso4 sigue fallando; se retira toda la pila. El usuario difiere ese detalle como no grave. No volver a solicitar toda esta prueba por ese detalle; el protocolo y su encoder no sustituyen el resultado visual observado. Los pasos siguientes se conservan como protocolo de regresión, no como nueva petición de prueba.

Imagen probada `3b80ca96`,333 pruebas aprobadas. Cancelación del iniciador12997/result1 y refresco de saldo12753. Anotar saldos iniciales, sin presuponer100 kamas.

Usar Audiluna y Prueba Oficios en clientes distintos, en el mismo mapa, fuera de combate y con espacio libre en inventario.

Preparación en Audiluna: Esc → Opciones → desplazar la página hasta «Varios» → activar «División automática de montones de objetos». Con esta opción activa, hacer los arrastres siguientes sin mantener Shift; Shift invierte la opción y envía la pila completa. Conservar abierto el inventario al confirmar para comprobar el saldo inmediatamente.

1. Con Audiluna, en General, escribe `!item 4275 6`. Esperado: recibe seis semillas de cardo. Anota el total de esas semillas y kamas de ambos personajes; serán los valores iniciales para comparar.
2. Desde el menú del otro personaje, selecciona Intercambiar. Rechaza la invitación en el segundo cliente. Esperado: la invitación desaparece y ningún objeto ni kama cambia de dueño.
   Repite la invitación y esta vez cancela desde el iniciador. Esperado: ambos diálogos desaparecen; el destinatario ya no puede aceptar y no se crea intercambio.
3. Repite y acepta. Esperado: ambos clientes abren el mismo intercambio, con los dos participantes y ofertas vacías.
4. Audiluna ofrece cuatro semillas. Para retirar solo una, arrastra la pila ofrecida a una casilla vacía del inventario sin mantener Shift; debe abrirse el selector de cantidad. Selecciona1 y confirma con el check. El botón directo de quitar retira toda la pila. Esperado: ambas pantallas muestran tres semillas ofrecidas. Audiluna ofrece10 kamas; Prueba Oficios ofrece3. Esperado: ambas pantallas muestran las mismas cantidades, sin descontar definitivamente los saldos.
5. Confirma solamente con Audiluna. Esperado: queda marcada su confirmación y el intercambio sigue abierto. Añade otra semilla desde Audiluna. Esperado: ahora hay cuatro semillas y se desactiva la confirmación anterior en ambas pantallas.
6. Confirma con ambos personajes. Esperado: se cierra el intercambio; el inventario que estaba abierto muestra inmediatamente cuatro semillas y7 kamas menos en Audiluna, cuatro semillas y7 kamas más en Prueba Oficios. No cerrar/reabrir inventario ni reconectar para que se actualice. Ningún objeto ajeno al intercambio desaparece ni se duplica.
7. Abre otro intercambio. Audiluna ofrece dos semillas y un kama; cancela sin completar ambas confirmaciones. Esperado: se cierra en ambas pantallas y conservan exactamente los inventarios y saldos del paso6.
8. Abre otro intercambio y devuelve dos semillas desde Prueba Oficios a Audiluna; confirma con ambos. Esperado: respecto al inicio, Audiluna tiene dos semillas menos y Prueba Oficios dos más. Los kamas siguen como en el paso6.
9. Cambia de personaje y vuelve en ambos clientes; después reinicia los clientes y vuelve a entrar. Esperado: se conservan los resultados del paso8, no quedan ventanas de intercambio abiertas y pueden caminar, abrir inventario e iniciar un nuevo intercambio.

Reportar el primer paso que difiera, qué aparece en cada cliente y si cambia la cantidad de semillas o kamas. No repetir transferencias si una pantalla queda abierta inesperadamente: el agente debe revisar el recibo SQL antes.

Peletero aceptado: el usuario confirma que ya recibe XP. No repetir esa rama por los fallos de intercambio.
