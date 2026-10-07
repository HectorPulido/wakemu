# Información pendiente — 28

La fórmula y el stacking del cálculo implementado ya tienen evidencia nativa y pruebas: estados1915/1916/1917; rangos inclusivos; XP territorial antes del multiplicador global; Sabiduría/Prospección temporales sin acumulación. No requieren una decisión del usuario.

## Pendientes concretos

- Acreditar el carrier nativo que actualiza Sabiduría/Prospección y la presentación de los efectos al entrar/salir de región fuera de combate.
- Verificar por TLS una transición regional completa y las recompensas resultantes; las pruebas de dominio no sustituyen ese recorrido.
- Preparar aceptación manual completa una vez confirmado el carrier; no declarar todo el sistema cerrado por el cálculo numérico.

## Evidencia actual

El contenedor único `wakfu-local-world-1`, imagen r9, contiene el módulo territorial con SHA256 `e2ca8accb94ffb03f21bf144259a7725ce82fe55ba0d77f93f2f6e9bd5f567e9`, idéntico a fuente. Inspección de la aplicación activa confirma attachment territorial en dispatcher y modificadores XP en plantación/cosecha. El 7 de octubre: `PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_territory_bonuses -q` aprueba12/12. Esto acredita despliegue del cálculo, no aceptación visual.

### Cotejo de carriers nativos (2026-10-07)

Se comprobó el catálogo de mensajes y consumidores JAR, sin fabricar opcode:

- `12789` / `cuE` es la actualización de ecosistema territorial (`region_id` y dos blobs). El consumidor `chl` actualiza el manager ecológico y propiedades UI `protectorSatisfaction*`; este es el carrier acreditado para datos/presentación de satisfacción regional, no para aplicar stats al personaje.
- `12847` / `cvb` inicia el combate (`ckf`/`ckP`) y construye el snapshot de actores de pelea; no es un refresh de stats de mundo.
- `13912` / `cuV` se enruta a `cjW`, que busca un combatiente en el fight actual y sincroniza sus efectos. No aplica a un personaje fuera de pelea.
- `13613` / `cvu` lleva un `fCs` y el consumer `ckr` más `aVf/aVr` lo trata como ganancia de XP/hechizos; no es una delta de Sabiduría/Prospección.
- `13713` / `cwY` es sincronización de bolsas del personaje. No actualiza stats ni estados.

Los IDs de estado `1915/1916/1917` tienen definiciones y efectos en el catálogo de estados, pero no se localizó un producer/consumer world que los ponga/retire al propietario como modificación visible fuera de combate. No se implementó un carrier. Para cerrar esta brecha hace falta evidencia de la rutina servidor de entrada/salida de zona que produce el estado o una captura nativa completa de esa transición, junto con el mensaje que actualiza el panel de características.
