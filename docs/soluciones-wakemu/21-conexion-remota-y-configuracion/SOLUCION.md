# Solución propuesta — 21

Documentar contrato de endpoints y acceso externo del servidor; conservar fuera de scope cualquier cambio de cliente.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar bind de dirección anunciada

Documentar bind 0.0.0.0 dentro del proceso/contenedor frente a host/ruta que reciben jugadores.0.0.0.0 no es dirección destino del cliente;127.0.0.1 apunta al equipo de cada usuario salvo túnel. Identificar dispatcher, world, API, chat y puertos publicados actuales.

## 2. Definir contrato de configuración

Proponer variables de servidor host/puertos/bind y valores anunciados coherentes. Acordar nombre de archivo/precedencia entorno>.env>default y validación; no implementar cargador en/client porque el usuario limita mejoras al servidor. Documentar requisitos para herramientas propias redistribuibles futuras fuera de/client.

## 3. Corregir superficie de autorización primero

Antes de escuchar desde exterior resolver 32/E03 en chat/API/test tasks. Separar interfaz de administración de transporte de juego; no publicar inspector, Redis o DB. La autorización previa para instancia aislada no implica publicar servicios compartidos a internet.

## 4. Preparar exposición revisable

Diseñar bind/port mapping y direcciones anunciadas para LAN/remoto, firewall/TLS donde corresponda y autenticación verificada. Registrar configuración efectiva y un plan de aplicación/rollback, sin reiniciar ni desplegar ahora. No copiar assets/binarios protegidos al repositorio.

## 5. Verificar desde dos ubicaciones

Con cliente compatible autorizado comprobar descubrimiento, token, world y chat desde LAN/remoto, no solo curl localhost. Probar IP/hostname inválido y errores por endpoint con mensajes precisos; distinguir puerto abierto de handshake/auth exitosos.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Bind y anuncio son distintos; acceso de red nunca reemplaza autenticación ni autoriza publicar assets del cliente.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
